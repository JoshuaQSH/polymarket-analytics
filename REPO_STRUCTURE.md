# Repository Structure — Polymarket Analytics

> **Keep this file up to date.** After every module, add new files/dirs to
> the table below and update the Core Algorithms section.

---

## Directory Tree

```
polymarket-analytics/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── events.py          # GET /events, GET /events/{id}
│   │   │   ├── prices.py          # GET /prices/{market_id}
│   │   │   ├── strategies.py      # GET /strategies
│   │   │   └── llm_strategy.py    # GET /llm-strategy (cached local inference)
│   │   ├── core/
│   │   │   ├── config.py          # Pydantic Settings (env vars)
│   │   │   └── logging.py
│   │   ├── services/
│   │   │   ├── gamma_client.py    # Gamma API HTTP client
│   │   │   └── clob_client.py     # CLOB API HTTP client
│   │   ├── strategies/
│   │   │   ├── base.py            # Abstract Strategy interface
│   │   │   ├── mean_reversion.py  # Mean-reversion signal generator
│   │   │   └── llm_strategy.py    # Local LLM inference wrapper
│   │   ├── exporters/
│   │   │   └── finetune_exporter.py  # JSONL SFT dataset writer
│   │   └── main.py                # FastAPI app factory
│   ├── tests/
│   │   ├── test_gamma_client.py
│   │   ├── test_event_ranker.py
│   │   ├── test_price_history.py
│   │   ├── test_strategies.py
│   │   ├── test_exporter.py
│   │   ├── test_api_routes.py
│   │   └── test_demo.py           # End-to-end smoke test
│   ├── data/
│   │   ├── cache/                 # Runtime cache (gitignored)
│   │   └── finetune/              # Exported JSONL datasets
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── EventList.tsx      # Main landing page
│   │   │   ├── EventDetail.tsx    # Chart + analysis per event
│   │   │   └── StrategyPage.tsx   # Quant strategy table
│   │   ├── components/
│   │   │   ├── EventCard.tsx
│   │   │   ├── PriceChart.tsx     # Recharts Yes/No line chart
│   │   │   └── StrategyTable.tsx
│   │   ├── hooks/
│   │   │   ├── useEvents.ts
│   │   │   └── usePriceHistory.ts
│   │   ├── api/
│   │   │   └── client.ts          # Axios/fetch wrapper (reads VITE_API_BASE)
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
├── docker-compose.yml
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                 # Tests on every push + PR (backend, frontend, Docker)
│   │   └── deploy.yml             # Deploy frontend to GitHub Pages on push to main
│   └── pr_template.md             # Auto-fills PR body in the GitHub UI
├── .gitignore                     # Excludes .env, cache/, node_modules/, dist/
├── CLAUDE.md
├── SKILL.md
└── REPO_STRUCTURE.md              # ← this file
```

---

## File / Directory Reference

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app factory; mounts all routers |
| `backend/app/api/events.py` | Lists + filters Polymarket events |
| `backend/app/api/prices.py` | Returns price-history arrays for charting |
| `backend/app/api/strategies.py` | Returns strategy signals + sim returns |
| `backend/app/api/llm_strategy.py` | Serves cached local LLM inference results |
| `backend/app/services/gamma_client.py` | Async HTTP client for Gamma API |
| `backend/app/services/clob_client.py` | Async HTTP client for CLOB API |
| `backend/app/strategies/mean_reversion.py` | Core quant strategy logic |
| `backend/app/strategies/llm_strategy.py` | Prompts local Ollama model |
| `backend/app/exporters/finetune_exporter.py` | Writes HF SFT JSONL |
| `backend/tests/` | All pytest tests (one file per service/module) |
| `backend/pyproject.toml` | Python deps + build config (uv-managed) |
| `backend/Dockerfile` | Container: Python 3.11-slim + uv |
| `frontend/src/pages/EventList.tsx` | Table sorted by participants; 50% badge |
| `frontend/src/pages/EventDetail.tsx` | Yes/No line chart + analysis panel |
| `frontend/src/pages/StrategyPage.tsx` | Strategy signals + estimated returns |
| `frontend/src/components/PriceChart.tsx` | Recharts LineChart wrapper |
| `frontend/src/api/client.ts` | Base URL config + typed fetch helpers |
| `docker-compose.yml` | Wires backend + frontend for local dev |
| `.github/workflows/ci.yml` | Runs pytest + frontend build + Docker test on every push/PR |
| `.github/workflows/deploy.yml` | Publishes `frontend/dist` to GitHub Pages on push to `main` |
| `.github/pr_template.md` | Pre-fills PR description with checklist (tests, Docker, secrets) |
| `.gitignore` | Excludes `.env`, `data/cache/`, `data/finetune/`, build artefacts |

---

## Core Algorithms

### 1. Event Ranking + Minor-Incident Filter
**File:** `backend/app/api/events.py` (function `rank_events`)

- Sort events by `numTraders` descending.
- Apply bonus weight to events where `abs(bestBid - 0.5) < 0.10`.
- Filter out events with `numTraders > 500` for the "minor incidents" view.

### 2. Mean-Reversion Strategy
**File:** `backend/app/strategies/mean_reversion.py` (class `MeanReversionStrategy`)

- Compute 7-day rolling mean of Yes price.
- Signal = `buy_yes` if current price < mean − 1σ; `buy_no` if > mean + 1σ.
- Backtest: simulate daily entries/exits over last 30d; compute net return %.
- Only emit for events passing the minor-incident filter.

### 3. LLM Fine-Tuning Exporter
**File:** `backend/app/exporters/finetune_exporter.py` (function `export_jsonl`)

- For each ranked event, build a `messages` list in HF SFT format.
- System prompt: prediction market analyst role.
- User turn: full event JSON (title, description, 30d price history, tags).
- Assistant turn: strategy signal JSON.
- Write to `data/finetune/events_YYYYMMDD.jsonl`.

### 4. Local LLM Inference Bridge
**File:** `backend/app/strategies/llm_strategy.py` (function `run_local_inference`)

- POST to `http://localhost:11434/api/generate` (Ollama).
- Cache response in `data/cache/llm_results.json` with 1h TTL.
- Optionally push cache to GitHub Gist for remote frontend consumption.
