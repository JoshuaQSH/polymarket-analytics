---
name: polymarket-analytics
description: >
  Build and maintain the Polymarket Analytics web application — a full-stack
  Python/FastAPI + React dashboard that fetches live Polymarket data, renders
  event lists sorted by participant count, prioritises near-50% probability
  events, plots Yes/No price history, runs lightweight quantitative strategies,
  exports LLM-ready fine-tuning datasets, and deploys as a GitHub Pages
  sub-page. Use this skill whenever the user mentions Polymarket, prediction
  markets, quantitative strategy, fine-tuning data export, or wants to
  build/extend/debug any part of this project.
---

# Polymarket Analytics — Project Skill

## 1. Project Overview

```
polymarket-analytics/
├── backend/                  # FastAPI data-fetching & strategy engine
│   ├── app/
│   │   ├── api/              # Route handlers
│   │   ├── core/             # Config, logging
│   │   ├── services/         # Polymarket API clients
│   │   ├── strategies/       # Quant strategy modules
│   │   └── exporters/        # LLM fine-tuning data exporters
│   ├── tests/                # pytest test suite (one file per module)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                 # React + Vite SPA
│   ├── src/
│   │   ├── pages/            # EventList, EventDetail, Strategy
│   │   ├── components/
│   │   └── hooks/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .github/workflows/ci.yml
├── REPO_STRUCTURE.md
├── CLAUDE.md
└── SKILL.md
```

## 2. APIs Used

| Purpose | Base URL | Auth |
|---|---|---|
| Market discovery / metadata | `https://gamma-api.polymarket.com` | None (public) |
| Prices, orderbooks | `https://clob.polymarket.com` | None for reads |
| User positions / history | `https://data-api.polymarket.com` | None for reads |

Key Gamma endpoints:
- `GET /events?limit=100&order=volume&ascending=false` — events sorted by volume
- `GET /markets?event_id=<id>` — markets for an event
- `GET /prices-history?market=<conditionId>&interval=1d` — CLOB historical prices

## 3. Development Rules (NON-NEGOTIABLE)

1. **Never claim something works without running a test.** After any new code,
   immediately run the relevant `pytest` test. If tests cannot run (e.g., no
   network), say so explicitly.
2. **Work modularly.** One module at a time. After each module: report what was
   built, show test results, wait for confirmation.
3. **Self-fix errors.** Run code, observe output, fix before reporting.
4. **Explicit unknowns.** If uncertain, say so. No guessing.
5. **Use `uv` for the virtual environment.** `pyproject.toml` must be complete.
   Fall back to `pip3` only if `uv` cannot install a package.
6. **Full pytest coverage.** Every module has a corresponding test file.
   All tests must pass before moving on.
7. **Docker.** A working `Dockerfile` and `docker-compose.yml` are required.
   Run and pass tests inside the container before declaring done.
8. **GitHub Actions CI.** `.github/workflows/ci.yml` must run all tests on
   every PR and push to `master`.
9. **`REPO_STRUCTURE.md`** kept up-to-date with every module addition.
10. **`STRATEGY.md`** must be updated whenever a non-LLM strategy is added or
    changed. Include algorithm details, math notation, parameter defaults, and
    a pros/cons table.

## 4. Module Build Order

Build in this order, test after each:

```
Module 1  → Polymarket API client (gamma + clob)
Module 2  → Event fetcher + ranker (sort by participants, flag ~50% prob)
Module 3  → Price-history fetcher
Module 4  → FastAPI backend (REST endpoints for frontend)
Module 5  → React EventList page
Module 6  → React EventDetail page (line plot)
Module 7  → Strategy engine (mean-reversion baseline)
Module 8  → Strategy results page + return estimator
Module 9  → LLM fine-tuning data exporter (JSONL)
Module 10 → GitHub Actions CI + Dockerfile verification
Module 11 → GitHub Pages deployment workflow
```

After Module 7 and for every later strategy addition, update `STRATEGY.md` in
the same PR as code + tests.

## 5. Backend — Key Patterns

### 5.1 `pyproject.toml` Skeleton

```toml
[project]
name = "polymarket-analytics-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.29",
  "httpx>=0.27",
  "pydantic>=2.7",
  "pandas>=2.2",
  "numpy>=1.26",
  "pytest>=8",
  "pytest-asyncio>=0.23",
  "respx>=0.21",   # httpx mock for tests
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Run: `uv venv && uv pip install -e ".[dev]"`

### 5.2 Gamma API Client Pattern

```python
# backend/app/services/gamma_client.py
import httpx, asyncio
from typing import Any

BASE = "https://gamma-api.polymarket.com"

async def get_events(limit: int = 100) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{BASE}/events", params={"limit": limit})
        r.raise_for_status()
        return r.json()
```

Always wrap API calls in `try/except httpx.HTTPError` and log failures.

### 5.3 Event Ranking Logic

```python
def rank_events(events: list[dict]) -> list[dict]:
    """
    Sort by numTraders DESC; within equal rank, prioritise abs(prob - 0.5) < 0.1.
    """
    def key(e):
        prob = e.get("bestAsk", 0.5)   # proxy for Yes probability
        near50_bonus = 1 if abs(prob - 0.5) < 0.1 else 0
        return (-e.get("volume24hr", 0), -near50_bonus)
    return sorted(events, key=key)
```

### 5.4 Strategy Engine (Module 7)

Implement a **mean-reversion micro-strategy**:
- Signal: If Yes price deviates >10% from its 7-day rolling mean, flag as
  potential reversion opportunity.
- Simulated return: backtest on the last 30 days of price history.
- Output schema:
  ```json
  {
    "event_id": "...",
    "signal": "buy_yes | buy_no | hold",
    "confidence": 0.72,
    "expected_return_pct": 4.5,
    "rationale": "..."
  }
  ```

Only emit strategies for events with `numTraders < 500` and
`abs(prob - 0.5) < 0.15` (the "minor incidents" filter).

### 5.5 LLM Fine-Tuning Exporter (Module 9)

Export to `data/finetune/events_YYYYMMDD.jsonl` in the Hugging Face
Supervised Fine-Tuning format:

```jsonl
{"messages": [
  {"role": "system", "content": "You are a prediction market analyst."},
  {"role": "user",   "content": "Analyze this Polymarket event: <event JSON>"},
  {"role": "assistant", "content": "<strategy output JSON>"}
]}
```

Include: event title, description, probability history (last 30d), numTraders,
volume, tags, and the strategy signal with rationale.

## 6. Frontend — Key Patterns

- **Vite + React 18 + TypeScript + Tailwind CSS**
- Charting: **Recharts** (already available in Claude artifact env)
- Pages:
  - `/` — `EventList` sorted by participants, badges for ~50% events
  - `/event/:id` — `EventDetail` with Yes/No line chart + LLM analysis summary
  - `/strategies` — `StrategyPage` with table of signals and simulated returns
- Fetch from backend at `VITE_API_BASE` (env var, defaults to
  `http://localhost:8000`)

## 7. Deployment (GitHub Pages)

```yaml
# .github/workflows/deploy.yml
name: Deploy to GitHub Pages
on:
  push:
    branches: [master]
jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: cd frontend && npm ci && npm run build
        env:
          VITE_API_BASE: https://<your-backend-url>
      - uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: frontend/dist
          destination_dir: polymarket   # appears at username.github.io/polymarket
```

The backend must be separately deployed (e.g., Render, Railway, Fly.io) and
the `VITE_API_BASE` env var updated accordingly.

## 8. Local Inference Integration (Module 9+)

To pipe local model inference (Qwen/Llama) into the remote page:

1. Run a lightweight **local inference server**:
   ```bash
   # Using llama.cpp or Ollama
   ollama serve   # exposes http://localhost:11434
   ```
2. The strategy engine (`backend/app/strategies/llm_strategy.py`) calls
   `POST http://localhost:11434/api/generate` with the JSONL prompt.
3. Inference results are cached in `data/cache/llm_results.json` (TTL 1h).
4. A `/api/llm-strategy` FastAPI endpoint serves the cached results.
5. For remote display: set up a **ngrok / Cloudflare tunnel** or cron-push
   results to a GitHub Gist that the deployed frontend polls.

## 9. Testing Conventions

| Test file | What it covers |
|---|---|
| `tests/test_gamma_client.py` | Mock HTTP responses; verify parsing |
| `tests/test_event_ranker.py` | Unit tests for ranking + 50% filter |
| `tests/test_price_history.py` | Mock CLOB responses |
| `tests/test_strategies.py` | Strategy signal generation (deterministic) |
| `tests/test_exporter.py` | JSONL output schema validation |
| `tests/test_api_routes.py` | FastAPI TestClient integration tests |

Run all: `uv run pytest -v`

## 10. Docker Commands

```bash
# Build + test backend
docker build -t polymarket-backend ./backend
docker run --rm polymarket-backend uv run pytest -v

# Run full stack
docker compose up --build

# Verify tests inside container
docker compose run backend uv run pytest -v
```

## 11. REPO_STRUCTURE.md Template

When writing `REPO_STRUCTURE.md`, include:
1. Directory tree (generated via `tree -L 3 --gitignore`)
2. Table: File/Dir | Purpose | Core logic location
3. Section: "Key Algorithms" with file + line range for each

---

## 12. Git Workflow (Mandatory for Every Module)

All code changes must follow this branch-and-PR workflow. **Never commit
directly to `master`.**

### 12.1 Branch Naming Convention

```
feature/<module-number>-<short-description>
fix/<short-description>
chore/<short-description>

# Examples
feature/01-gamma-api-client
feature/07-mean-reversion-strategy
fix/clob-timeout-handling
chore/update-repo-structure
```

### 12.2 Per-Module Git Workflow

After completing and locally testing each module, Claude Code must:

```bash
# 1. Create a feature branch from master
git checkout master && git pull origin master
git checkout -b feature/<N>-<description>

# 2. Stage only relevant files (never use `git add .` blindly)
git add backend/app/services/gamma_client.py
git add backend/tests/test_gamma_client.py
# ... add other files explicitly

# 3. Commit with a conventional commit message
git commit -m "feat(module-01): add Gamma + CLOB API clients with tests"

# 4. Push the branch
git push -u origin feature/<N>-<description>

# 5. Open a Pull Request via GitHub CLI
gh pr create \
  --title "feat(module-01): Gamma + CLOB API clients" \
  --body "$(cat .github/pr_template.md)" \
  --base master \
  --head feature/<N>-<description>
```

The PR **must pass all CI checks** (see Section 12.3) before merging.
Claude Code must not merge the PR — the user confirms and merges.

### 12.3 Automatic PR Workflow (`.github/workflows/ci.yml`)

This workflow runs on every `push` to any branch and every `pull_request`
targeting `master`. A PR cannot be merged until all jobs are green.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [master]

jobs:
  backend-test:
    name: Backend Tests
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv pip install -e ".[dev]"

      - name: Run pytest
        run: uv run pytest -v --tb=short

  frontend-build:
    name: Frontend Build
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Type-check
        run: npm run type-check

      - name: Build
        run: npm run build
        env:
          VITE_API_BASE: http://localhost:8000

  docker-test:
    name: Docker Integration Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build backend image
        run: docker build -t polymarket-backend ./backend

      - name: Run tests inside container
        run: docker run --rm polymarket-backend uv run pytest -v --tb=short
```

### 12.4 Branch Protection Rules (set once in GitHub repo settings)

Instruct the user to configure these settings at
`Settings → Branches → Add rule` for the `master` branch:

| Setting | Value |
|---|---|
| Require a pull request before merging | ✅ |
| Require status checks to pass | ✅ |
| Required status checks | `Backend Tests`, `Frontend Build`, `Docker Integration Test` |
| Require branches to be up to date | ✅ |
| Do not allow bypassing the above settings | ✅ |
| Allow squash merging only | ✅ (keeps history clean) |

### 12.5 Pull Request Template (`.github/pr_template.md`)

Claude Code must create this file once during project initialisation:

```markdown
## Summary
<!-- What module / fix does this PR implement? -->

## Changes
- [ ] New files added
- [ ] Existing files modified
- [ ] Tests written and passing
- [ ] REPO_STRUCTURE.md updated
- [ ] No secrets or `.env` files committed

## Test Results
<!-- Paste `uv run pytest -v` output here -->

## Module Checklist
- [ ] All unit tests pass locally
- [ ] Docker build succeeds: `docker build -t polymarket-backend ./backend`
- [ ] Docker tests pass: `docker run --rm polymarket-backend uv run pytest -v`
- [ ] CI is green on this branch
```

### 12.6 Commit Message Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scope):   new feature
fix(scope):    bug fix
test(scope):   adding or correcting tests
chore(scope):  tooling, deps, CI changes
docs(scope):   documentation only
refactor(scope): code restructure, no behaviour change
```

Examples:
```
feat(module-02): add event ranker with near-50% priority filter
fix(clob-client): handle 429 rate-limit with exponential backoff
test(strategies): add deterministic backtest fixture
chore(ci): pin uv version to 0.4.x
docs(repo): update REPO_STRUCTURE.md after module 5
```

### 12.7 `.gitignore` (must be created at repo init)

```gitignore
# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
.pytest_cache/

# Environment
.env
.env.*
!.env.example

# Data (runtime, not source)
backend/data/cache/
backend/data/finetune/

# Frontend build
frontend/dist/
frontend/node_modules/

# Editor
.vscode/settings.json
.idea/

# OS
.DS_Store
Thumbs.db
```

### 12.8 Initial Repo Setup (run once)

```bash
# Inside the repo root
git init
git checkout -b master

# Create .gitignore first — before any other files
cat > .gitignore << 'EOF'
# (paste content from 12.7 above)
EOF

# Add scaffold files
git add CLAUDE.md SKILL.md REPO_STRUCTURE.md GETTING_STARTED.md .gitignore
git commit -m "chore: initial project scaffold"

# Push
git remote add origin git@github.com:<you>/polymarket-analytics.git
git push -u origin master

# Install GitHub CLI if not present, then authenticate
gh auth login

# Create the PR template directory
mkdir -p .github
cat > .github/pr_template.md << 'EOF'
# (paste content from 12.5 above)
EOF

git add .github/
git commit -m "chore(ci): add PR template and CI workflow"
git push
```

---

*Read `AGENT.md` for general behaviour rules that complement this skill.*
