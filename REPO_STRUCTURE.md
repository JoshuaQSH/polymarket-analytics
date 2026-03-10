# Repository Structure — Polymarket Analytics

> Keep this file up to date after each module.

## Directory Tree

```text
polymarket-analytics/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── events.py
│   │   │   ├── prices.py
│   │   │   ├── strategies.py
│   │   │   └── llm_strategy.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── gamma_client.py
│   │   │   └── clob_client.py
│   │   ├── strategies/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── mean_reversion.py
│   │   │   └── llm_strategy.py
│   │   ├── exporters/
│   │   │   ├── __init__.py
│   │   │   └── finetune_exporter.py
│   │   ├── __init__.py
│   │   └── main.py
│   ├── data/
│   │   ├── cache/
│   │   └── finetune/
│   ├── tests/
│   │   ├── test_api_routes.py
│   │   ├── test_demo.py
│   │   ├── test_event_ranker.py
│   │   ├── test_exporter.py
│   │   ├── test_gamma_client.py
│   │   ├── test_llm_strategy.py
│   │   ├── test_price_history.py
│   │   └── test_strategies.py
│   ├── .env.example
│   ├── .dockerignore
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── EventCard.tsx
│   │   │   ├── PriceChart.tsx
│   │   │   └── StrategyTable.tsx
│   │   ├── hooks/
│   │   │   ├── useEvents.ts
│   │   │   ├── usePriceHistory.ts
│   │   │   ├── useStrategySimulation.ts
│   │   │   └── useStrategies.ts
│   │   ├── pages/
│   │   │   ├── EventDetail.tsx
│   │   │   ├── EventList.tsx
│   │   │   └── StrategyPage.tsx
│   │   ├── styles/
│   │   │   └── app.css
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── .env.example
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.app.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
├── .gitignore
├── AGENT.md
├── GUIDE.md
├── REPO_STRUCTURE.md
├── STRATEGY.md
└── skills/
    └── SKILL.md
```

## File / Directory Reference

| Path | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Module 10 CI workflow: backend pytest, frontend build, and Docker image verification on push/PR to `master` |
| `.github/workflows/deploy.yml` | Module 11 GitHub Pages deployment workflow for frontend artifact publish on `master` |
| `backend/app/services/gamma_client.py` | Async Gamma API client (events + markets) |
| `backend/app/services/clob_client.py` | Async CLOB API client (price history) |
| `backend/app/api/events.py` | Event fetch/rank logic plus `GET /events` and `GET /events/{id}` |
| `backend/app/api/prices.py` | Price-history normalize/fetch logic plus `GET /prices/{condition_id}` |
| `backend/app/api/strategies.py` | Strategy routes: baseline `GET /strategies` plus timed `POST /strategies/simulate` for mean-reversion or LLM simulation |
| `backend/app/api/llm_strategy.py` | LLM inference routes for local, OpenAI, and Claude providers (`/llm/infer/local|remote|claude`) |
| `backend/app/strategies/mean_reversion.py` | Mean-reversion strategy engine and event-level strategy generation |
| `backend/app/strategies/base.py` | Base strategy abstractions and canonical result schema |
| `backend/app/strategies/llm_strategy.py` | Local/OpenAI/Claude inference clients, output parser, and LLM strategy result generation with earnings-rate fields |
| `backend/app/exporters/finetune_exporter.py` | Module 9 fine-tune JSONL record builder and live export pipeline |
| `backend/app/main.py` | FastAPI app factory, CORS, `/health`, router mounting |
| `backend/tests/test_gamma_client.py` | Gamma client tests with `respx` mocks |
| `backend/tests/test_event_ranker.py` | Event ranking/fetch unit tests |
| `backend/tests/test_price_history.py` | CLOB and price-history normalization tests |
| `backend/tests/test_exporter.py` | Module 9 exporter schema and JSONL file generation tests |
| `backend/tests/test_llm_strategy.py` | Local/OpenAI/Claude LLM helper tests (HTTP mocks + caching) |
| `backend/tests/test_api_routes.py` | FastAPI route integration tests |
| `backend/tests/test_demo.py` | End-to-end demo test for the export pipeline |
| `backend/.dockerignore` | Excludes local virtualenv/cache/runtime data from backend Docker build context |
| `backend/Dockerfile` | Backend container image used for CI Docker verification (runs pytest in container) |
| `frontend/src/App.tsx` | Frontend router (`/`, `/event/:eventId`, `/strategies`) |
| `frontend/src/pages/EventList.tsx` | Module 5 EventList UI (ranked events + stats + loading/error states) |
| `frontend/src/pages/EventDetail.tsx` | Module 6 EventDetail page with market metadata and price-history visualization |
| `frontend/src/pages/StrategyPage.tsx` | Module 8 strategy results dashboard with return estimator |
| `frontend/src/hooks/useEvents.ts` | Frontend events data-fetch hook and summary metrics |
| `frontend/src/hooks/usePriceHistory.ts` | Fetches normalized price history for a market identifier |
| `frontend/src/hooks/useStrategySimulation.ts` | Timed strategy simulation hook with auto-run interval loop and countdown metadata |
| `frontend/src/hooks/useStrategies.ts` | Fetches strategy results and computes signal summary metrics |
| `frontend/src/api/client.ts` | Typed frontend API client (`events`, `event detail`, `price history`, `strategies`) using `VITE_API_BASE` |
| `frontend/src/components/EventCard.tsx` | Event card presentation component with near-50 badge |
| `frontend/src/components/PriceChart.tsx` | Recharts Yes/No line chart for EventDetail |
| `frontend/src/components/StrategyTable.tsx` | Tabular strategy result view with per-trade PnL estimate |
| `frontend/src/styles/app.css` | Module 5/6/8 layout, detail view, strategy table, and estimator styles |
| `frontend/package.json` | React + Vite frontend scripts and dependencies |
| `frontend/.dockerignore` | Excludes `node_modules`, build artifacts, and local env files from frontend Docker context |
| `frontend/Dockerfile` | Frontend container build definition used by CI Docker verification |
| `STRATEGY.md` | Strategy specification document with algorithm math, assumptions, and pros/cons |
| `GUIDE.md` | End-to-end local/deployment guide for Ollama, model lifecycle, and backend integration |

## Core Algorithms

### 1. Event Ranking + Minor-Incident Filter
**File:** `backend/app/api/events.py` (`rank_events`, `fetch_ranked_events`)

- Fetch Gamma events.
- Normalize participant/probability fields.
- Sort by participant count descending.
- For ties, prioritize events close to 50% probability.
- Filter out high-participant events for the minor-incident view.

### 2. Price-History Fetcher
**File:** `backend/app/api/prices.py` (`fetch_price_history`, `normalize_price_history`)

- Fetch CLOB price points for a condition id.
- Normalize mixed key shapes (`t|timestamp|time`, `p|price|value`).
- Drop invalid points and sort by timestamp ascending.

### 3. FastAPI Route Layer
**Files:** `backend/app/main.py`, `backend/app/api/events.py`, `backend/app/api/prices.py`, `backend/app/api/strategies.py`, `backend/app/api/llm_strategy.py`

- Expose `/health`, `/events`, `/events/{event_id}`, `/prices/{condition_id}`, `/strategies`, `/llm/infer/local`, `/llm/infer/remote`, `/llm/infer/claude`.
- Convert upstream service failures to consistent `502` responses.

### 4. Mean-Reversion Strategy Engine
**Files:** `backend/app/strategies/mean_reversion.py`, `backend/tests/test_strategies.py`

- Use a 7-day rolling mean and 10% deviation threshold to emit `buy_yes`, `buy_no`, or `hold`.
- Run a 30-day rolling backtest to estimate expected return percentage.
- Filter events to the minor-incident set (`participantCount < 500`, `abs(prob - 0.5) < 0.15`) before scoring.

### 5. EventList Frontend Flow
**Files:** `frontend/src/pages/EventList.tsx`, `frontend/src/hooks/useEvents.ts`, `frontend/src/api/client.ts`

- Fetch ranked events from backend using `VITE_API_BASE`.
- Compute dashboard stats (total events, near-50 count, average participants).
- Render responsive event cards with rank and probability metadata.

### 6. EventDetail Frontend Flow + Line Plot
**Files:** `frontend/src/pages/EventDetail.tsx`, `frontend/src/hooks/usePriceHistory.ts`, `frontend/src/components/PriceChart.tsx`

- Resolve route param (`/event/:eventId`) and fetch event detail from backend.
- Extract preferred market id (`clobTokenIds` first) and request normalized price history.
- Render a dual-line Yes/No probability chart (No = `1 - Yes`) for time-series inspection.

### 7. Strategy Results Page + Return Estimator
**Files:** `frontend/src/pages/StrategyPage.tsx`, `frontend/src/hooks/useStrategySimulation.ts`, `frontend/src/components/StrategyTable.tsx`, `backend/app/api/strategies.py`

- Run strategy simulations via `/strategies/simulate` with user-defined interval seconds.
- Support both mean-reversion and LLM modes (provider/model/api-key inputs for LLM mode).
- Display backend-reflected scheduling metadata (`executed_at`, `next_run_at`, interval) and earnings rate.

### 8. Fine-Tuning JSONL Exporter
**Files:** `backend/app/exporters/finetune_exporter.py`, `backend/tests/test_exporter.py`

- Build Hugging Face SFT-style `messages` records from event metadata, last-30-point price history, and strategy outputs.
- Serialize records to `backend/data/finetune/events_YYYYMMDD.jsonl`.
- Support live export by fetching events, strategies, and market price history in one async pipeline.

### 9. LLM Inference Options (Local + Remote)
**Files:** `backend/app/strategies/llm_strategy.py`, `backend/app/api/llm_strategy.py`, `backend/tests/test_llm_strategy.py`

- Local option: call Ollama-compatible `/api/generate` endpoint.
- OpenAI option: call `/chat/completions` endpoint with API key.
- Claude option: call Anthropic `/messages` endpoint with API key.
- Cache results in `backend/data/cache/llm_results.json` (TTL-aware reads).

### 10. CI + Docker Verification Pipeline
**Files:** `.github/workflows/ci.yml`, `backend/Dockerfile`, `frontend/Dockerfile`

- Trigger CI on `push` and `pull_request` to `main`.
- Run backend pytest with `uv` in CI host environment.
- Run frontend `npm run build`.
- Build backend and frontend Docker images.
- Execute backend pytest inside the backend container to catch Docker-specific breakages.

### 11. GitHub Pages Deployment Workflow
**Files:** `.github/workflows/deploy.yml`, `frontend/vite.config.ts`, `frontend/src/App.tsx`

- Build frontend for project-page base path (`/<repo-name>/`) via `VITE_BASE_PATH`.
- Inject deployed backend API URL via `VITE_API_BASE` repository variable.
- Upload `frontend/dist` as GitHub Pages artifact and deploy through `actions/deploy-pages`.
- Publish SPA fallback (`404.html`) so direct route reloads recover on Pages hosting.
