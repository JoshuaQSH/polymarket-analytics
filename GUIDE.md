# GUIDE.md - Ollama + LLM Deployment and Integration Guide

This guide documents the complete local/deployment workflow for the LLM-enabled strategy stack in this repository.

## 1. Current Architecture

- Frontend (`frontend/`, Vite + React) calls backend REST APIs.
- Backend (`backend/`, FastAPI) calls:
  - Polymarket Gamma API (events metadata)
  - Polymarket CLOB API (price history)
  - LLM providers:
    - Local (`Ollama`, `/api/generate`)
    - OpenAI-compatible remote API (`/v1/chat/completions`)
    - Anthropic Claude API (`/v1/messages`)
- Strategy endpoint used by UI:
  - `POST /strategies/simulate`

## 2. Prerequisites

- OS: Linux/macOS recommended
- Python `>=3.11`
- Node.js `>=20`
- `uv` installed
- Docker installed and daemon running (for container workflow)
- Optional but recommended: NVIDIA GPU + recent driver for fast local inference

Quick checks:

```bash
python3 --version
node --version
uv --version
docker --version
docker info >/dev/null && echo "docker daemon: running"
```

## 3. Project Bootstrap

### Backend

```bash
cd ~/polymarket-analytics/backend
uv sync --dev
```

### Frontend

```bash
cd ~/polymarket-analytics/frontend
npm install
```

## 4. Ollama Setup (Step-by-Step)

You have two install options.

### Option A: system-wide install

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

### Option B: user-local install (no system package changes)

```bash
mkdir -p ~/llm-related/ollama ~/llm-related/ollama-bin
curl -fL https://ollama.com/download/ollama-linux-amd64.tar.zst -o /tmp/ollama-linux-amd64.tar.zst
zstd -d -c /tmp/ollama-linux-amd64.tar.zst | tar -xf - -C ~/llm-related/ollama-bin
~/llm-related/ollama-bin/bin/ollama --version
```

### Start Ollama with a dedicated model directory

```bash
OLLAMA_MODELS=~/llm-related/ollama ~/llm-related/ollama-bin/bin/ollama serve
```

Run this in a dedicated terminal. For background service:

```bash
OLLAMA_MODELS=~/llm-related/ollama nohup ~/llm-related/ollama-bin/bin/ollama serve > ~/llm-related/ollama/ollama.log 2>&1 &
```

### Verify Ollama API is up

```bash
curl -sS http://127.0.0.1:11434/api/tags
```

## 5. Pull / Switch / Run Models in Ollama

### Pull model(s)

```bash
~/llm-related/ollama-bin/bin/ollama pull tinyllama
~/llm-related/ollama-bin/bin/ollama pull qwen2.5:3b
~/llm-related/ollama-bin/bin/ollama pull llama3.2:3b
```

### List models

```bash
~/llm-related/ollama-bin/bin/ollama list
```

### Run model directly

```bash
~/llm-related/ollama-bin/bin/ollama run tinyllama "Return JSON: {\"signal\":\"hold\"}"
```

### Switch model in this project

- Frontend Strategy page -> `LLM Provider = Local`
- Select `Model` from dropdown (`tinyllama`, `qwen2.5:3b`, `llama3.2:3b`)
- Click `Run Once` or `Start Auto Run`

No backend restart is required when switching model from the UI.

## 6. Integrate Ollama into Backend

Start backend:

```bash
cd ~/polymarket-analytics/backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Smoke test local inference API:

```bash
curl -sS -X POST "http://localhost:8000/llm/infer/local" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Return JSON with signal hold","model":"tinyllama","use_cache":false}'
```

Smoke test LLM strategy simulation:

```bash
curl -sS -X POST "http://localhost:8000/strategies/simulate" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_type":"llm",
    "provider":"local",
    "model":"tinyllama",
    "limit":200,
    "llm_max_events":5,
    "interval_seconds":60,
    "use_cache":false
  }'
```

Notes:

- The UI sends API key to backend for remote providers (`OpenAI`, `Claude`) via payload field `api_key`.
- Backend caches LLM outputs at `backend/data/cache/llm_results.json` (TTL default 1h).

## 7. Full Local Run (Dynamic Frontend + Backend)

Terminal 1 (Ollama):

```bash
OLLAMA_MODELS=~/llm-related/ollama ~/llm-related/ollama-bin/bin/ollama serve
```

Terminal 2 (Backend):

```bash
cd ~/polymarket-analytics/backend
uv sync --dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 3 (Frontend):

```bash
cd ~/polymarket-analytics/frontend
npm install
VITE_API_BASE=http://localhost:8000 npm run dev -- --host 0.0.0.0 --port 5173
```

Open:

- `http://localhost:5173`
- Go to Strategy page
- Choose `LLM Strategy`
- Choose provider/model
- Click `Run Once` or `Start Auto Run`

## 8. Remote Provider Integration (OpenAI / Claude)

### OpenAI-compatible

```bash
curl -sS -X POST "http://localhost:8000/llm/infer/remote" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Return JSON signal hold","model":"gpt-4o-mini","api_key":"<OPENAI_KEY>","use_cache":false}'
```

### Claude

```bash
curl -sS -X POST "http://localhost:8000/llm/infer/claude" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Return JSON signal hold","model":"claude-3-5-haiku-latest","api_key":"<ANTHROPIC_KEY>","use_cache":false}'
```

Do not commit keys. Use `.env` locally and secret managers in deployment.

## 9. Fine-Tuning Workflow (What Ollama Can and Cannot Do)

Important:

- Ollama is an inference/model-packaging runtime.
- Ollama does not do full SFT training by itself.
- Training is done externally (for example, LLaMA-Factory), then the trained model is packaged for Ollama.

### Step 1: Export training data from this project

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

Output file pattern:

- `backend/data/finetune/events_YYYYMMDD.jsonl`

### Step 2: Train externally

Recommended training stack:

- LLaMA-Factory (SFT / LoRA training)
- or equivalent trainer (Axolotl, Unsloth, etc.)

Train on the exported JSONL using Hugging Face chat/messages format.

### Step 3: Convert trained result to Ollama-loadable artifact

Common path:

1. Merge adapter with base model (if LoRA).
2. Convert to GGUF (typically via `llama.cpp` conversion tooling).
3. Quantize if needed (Q4/Q5/etc.).

### Step 4: Create custom Ollama model

Create a `Modelfile`:

```text
FROM /absolute/path/to/your-model.gguf
TEMPLATE """{{ .Prompt }}"""
PARAMETER temperature 0.2
```

Build model in Ollama:

```bash
ollama create polymarket-ft -f Modelfile
```

Run it:

```bash
ollama run polymarket-ft "Return JSON with signal, confidence, expected_return_pct, rationale."
```

Then select `polymarket-ft` in frontend Local model dropdown (or call backend with `"model":"polymarket-ft"`).

## 10. Docker Deployment Details

Current repository includes:

- `backend/Dockerfile`
- `frontend/Dockerfile`

### Backend container test run

```bash
cd ~/polymarket-analytics
docker build -t polymarket-backend ./backend
docker run --rm polymarket-backend uv run pytest tests/ -v
```

### Frontend container build

```bash
cd ~/polymarket-analytics
docker build -t polymarket-frontend ./frontend
```

### Compose pattern (recommended for full stack)

This repo currently does not ship a committed `docker-compose.yml`. A production-ready compose should include:

1. `frontend` service
2. `backend` service
3. `ollama` service (or external Ollama host)
4. Persistent volume for Ollama model blobs
5. Persistent volume for backend runtime data (`backend/data/cache`, `backend/data/finetune`)

If backend is containerized separately from Ollama, ensure backend can resolve Ollama endpoint and that local LLM URL is configurable in code/runtime.

## 11. Troubleshooting

### Error: `Request failed (502): LLM strategy failed: Local LLM inference request failed`

Check:

1. Ollama is running:
   ```bash
   curl -sS http://127.0.0.1:11434/api/tags
   ```
2. Model exists:
   ```bash
   ollama list
   ```
3. Model can generate:
   ```bash
   curl -sS http://127.0.0.1:11434/api/generate \
     -d '{"model":"tinyllama","prompt":"Return JSON signal hold","stream":false}'
   ```
4. Backend can hit Ollama from its own runtime context (host vs container networking mismatch is common).

### Error: `Remote LLM inference request failed (429)`

- Your API key is valid but quota/rate limit is exceeded.
- Fix by adding billing/quota, using a lower-cost model, or reducing call frequency.

### Strategy page shows no results

- `llm_max_events` may be too low and minor-incident filter can return empty set.
- Increase `limit` and/or `llm_max_events`.
- Confirm Gamma/CLOB endpoints are reachable.

## 12. Why Ollama over vLLM, SGLang, llama.cpp, and LLaMA-Factory

Short answer: Ollama is the best fit for this project stage (fast local setup, minimal ops, stable HTTP interface).

### Comparison

- Ollama
  - Strength: fastest path to local serving with simple `/api/generate`.
  - Best for: single-node local inference, developer productivity, lightweight deployment.
- vLLM
  - Strength: very high throughput and optimized batching.
  - Tradeoff: more infra and tuning overhead; overkill for current interactive strategy workflow.
- SGLang
  - Strength: strong high-performance structured inference/serving patterns.
  - Tradeoff: steeper operational complexity than needed for this stack now.
- `llama.cpp`
  - Strength: very flexible low-level local inference and quantized CPU/GPU usage.
  - Tradeoff: you manage more serving details yourself; Ollama wraps it with easier model lifecycle and API ergonomics.
- LLaMA-Factory
  - Strength: excellent fine-tuning/training pipeline.
  - Tradeoff: it is a trainer, not your runtime inference server for this app.

### Practical decision for this repository

Ollama was chosen because it gives:

1. Fastest end-to-end local integration with existing backend.
2. Clean model lifecycle (`pull`, `list`, `run`, `create`) without custom serving code.
3. Easy handoff between local and remote providers in one frontend/backend flow.
4. Lower operational burden while the product is still iterating quickly.

Use LLaMA-Factory (or similar) for training, then package the trained output back into Ollama for serving.

## 13. Security and Secrets

- Never commit raw API keys.
- Keep secrets in:
  - local `.env` (gitignored), or
  - deployment secret manager (Render/Railway/Fly/GitHub Actions secrets).
- Rotate any key that has been exposed in logs/chats.

