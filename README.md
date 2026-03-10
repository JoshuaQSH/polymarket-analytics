# Run locally (to see dynamic results)

Backend
```bash
cd ~/polymarket-analytics/backend
uv sync --dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend
```bash
cd ~/polymarket-analytics/frontend
npm install
VITE_API_BASE=http://localhost:8000 npm run dev -- --host 0.0.0.0 --port 5173
```

Validate live endpoints
```bash
curl -s http://localhost:8000/health
curl -s "http://localhost:8000/events?limit=10" | jq '.[0] | {id,participantCount,yesProbability}'
curl -s "http://localhost:8000/strategies?limit=20" | jq '.[0:5]'
```

Open http://localhost:5173, check Event Radar and Strategy Engine pages.

## Module 9: Fine-Tune Export + LLM Inference Options

Export live JSONL dataset:
```bash
cd ~/polymarket-analytics/backend
uv run python - <<'PY'
import asyncio
from app.exporters.finetune_exporter import export_live_finetune_dataset

async def main():
    path = await export_live_finetune_dataset(limit=100)
    print(path)

asyncio.run(main())
PY
```

Option 1: local model inference (Ollama-compatible)
```bash
# Terminal A
ollama serve

# Terminal B
cd ~/polymarket-analytics/backend
curl -sS -X POST "http://localhost:8000/llm/infer/local" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Analyze event payload: {\"event_id\":\"demo\"}","model":"tinyllama"}'
```

Option 2: remote API inference (OpenAI-compatible)
```bash
cd ~/polymarket-analytics/backend
export OPENAI_API_KEY="<your-key>"
curl -sS -X POST "http://localhost:8000/llm/infer/remote" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Analyze event payload: {\"event_id\":\"demo\"}","model":"gpt-4o-mini"}'
```

Option 3: Claude API inference (Anthropic-compatible)
```bash
cd ~/polymarket-analytics/backend
export ANTHROPIC_API_KEY="<your-claude-key>"
curl -sS -X POST "http://localhost:8000/llm/infer/claude" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Analyze event payload: {\"event_id\":\"demo\"}","model":"claude-3-5-haiku-latest"}'
```

Strategy simulation endpoint (used by Strategy page auto-run):
```bash
curl -sS -X POST "http://localhost:8000/strategies/simulate" \
  -H "Content-Type: application/json" \
  -d '{"strategy_type":"llm","provider":"remote","model":"gpt-4o-mini","api_key":"<key>","interval_seconds":60,"limit":50}'
```

## Module 10: CI workflow

CI is defined in `.github/workflows/ci.yml` and runs on `push` + `pull_request` to `master`.

Jobs:

1. Backend pytest (`uv sync --dev` + `uv run pytest tests/ -v`)
2. Frontend build (`npm ci` + `npm run build`)
3. Docker verification (build backend/frontend images + run backend tests in container)

## Module 11: GitHub Pages deployment

Deployment workflow is in `.github/workflows/deploy.yml` and triggers on:

- `push` to `master`
- manual `workflow_dispatch`

### Required GitHub repository settings

1. Go to `Settings -> Pages`.
2. Set source to `GitHub Actions`.
3. In `Settings -> Secrets and variables -> Actions -> Variables`, create:
   - `VITE_API_BASE` = your deployed backend base URL (for example `https://your-backend.example.com`)

### Frontend base path for project pages

The deployment workflow builds with:

- `VITE_BASE_PATH=/<repo-name>/`

and the app router uses `import.meta.env.BASE_URL`, so project-page routing works under:

- `https://<username>.github.io/<repo-name>/`

The workflow also publishes `dist/404.html` (copied from `dist/index.html`) so SPA refreshes on nested routes can recover on GitHub Pages.

### Trigger deployment

Push to `master`:

```bash
git push origin master
```

Or run it manually from the Actions tab (`Deploy Frontend to GitHub Pages` workflow).
