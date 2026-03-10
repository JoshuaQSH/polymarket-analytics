# CLAUDE.md — Polymarket Analytics Project

## Core Behaviour

- Think from first principles. Do not assume the user knows exactly what they
  want or how to get there. Reason from the original problem, not from the
  most obvious path.
- If motivation or goal is unclear, **stop and ask** before writing any code.
- If the goal is clear but a shorter path exists, **say so and recommend it**
  before proceeding.

---

## Development Rules (apply to every task in this project)

### 1. Test Before Claiming Success
Never say something "works" unless you have run a test and seen it pass.
- After writing any new function, immediately write a `pytest` test and run it.
- If you cannot run a test (e.g. network is unavailable in the sandbox), state
  this explicitly: *"I cannot run this test here because X. You should run:
  `pytest tests/test_foo.py -v`"*

### 2. Modular Progress
Complete one module at a time. After each module:
1. State exactly what was built.
2. Show the test output (pass/fail + output).
3. Wait for user confirmation before starting the next module.

### 3. Self-Healing
Run your code. If it fails, fix it yourself before reporting results.
Do not ask the user "did you get an error?" — run the code and find out.

### 4. Explicit Unknowns
If uncertain about an API response shape, an algorithm detail, or a library
behaviour, say so. Do not guess silently.

### 5. Python Environment
- Use `uv` to manage the virtualenv and dependencies.
- `pyproject.toml` must be complete and reproducible.
- If a package cannot be installed via `uv`, fall back to `pip3` and document
  why.

```bash
# Standard setup
uv venv
uv pip install -e ".[dev]"
uv run pytest -v
```

### 6. Test Coverage
Every module must have a corresponding `tests/test_<module>.py` file.
All tests must pass before you move to the next module.
Provide a small end-to-end demo test at `tests/test_demo.py`.

### 7. Docker
Every deliverable must run in Docker.

```bash
docker build -t polymarket-backend ./backend
docker run --rm polymarket-backend uv run pytest -v
docker compose up --build
```

Run the container yourself and confirm all tests pass before presenting it.

### 8. GitHub Actions CI
`.github/workflows/ci.yml` must:
- Trigger on `push` and `pull_request` to `main`.
- Run `uv run pytest -v` in the backend container.
- Run `npm test` (or `npm run build`) in the frontend.

### 9. REPO_STRUCTURE.md
Maintain `REPO_STRUCTURE.md` after every module. It must include:
- A directory tree.
- A table of every file/directory with its purpose.
- A "Core Algorithms" section listing where each key piece of logic lives.

### 10. Git Workflow
**Never commit directly to `main`.** Every change goes through a PR.

```bash
# Per-module flow
git checkout main && git pull origin main
git checkout -b feature/<N>-<short-description>

# ... write code, run tests ...

git add <explicit file list>   # never `git add .` blindly
git commit -m "feat(module-NN): <description>"
git push -u origin feature/<N>-<short-description>
gh pr create --title "..." --body "$(cat .github/pr_template.md)" --base main
```

Rules:
- Branch naming: `feature/`, `fix/`, `chore/`, `docs/` prefixes.
- Commit messages: follow Conventional Commits (feat/fix/test/chore/docs/refactor).
- PRs must pass all three CI jobs (backend tests, frontend build, Docker test)
  before the user merges.
- Claude Code **opens** PRs; the **user merges** them.
- Never commit `.env`, `data/cache/`, or `data/finetune/` — `.gitignore` must
  exist from the very first commit.

Full Git workflow spec is in `SKILL.md` Section 12.

---

## Project-Specific Context

### What This Project Is
An analytical website for Polymarket that:
1. Lists events sorted descending by participant count.
2. Prioritises events with probability ≈ 50% and low participant counts
   ("minor incidents" focus — **avoid hot topics**).
3. Shows a Yes/No price-history line chart per event.
4. Runs lightweight quantitative strategies (mean-reversion baseline) and
   estimates returns on a dedicated Strategy page.
5. Exports data as Hugging Face SFT JSONL for local LLM fine-tuning (Qwen,
   Llama, etc.).
6. Optionally pipes local model inference back to the deployed page via a cache
   + API endpoint.

### Deployment Target
- Frontend → GitHub Pages at `<username>.github.io/polymarket`
- Backend → external host (Render / Railway / Fly.io); URL in `VITE_API_BASE`
- Local-first: everything must run with `docker compose up` before deployment.

### API Keys / Auth
The Polymarket Gamma API and CLOB read endpoints are public (no key needed).
Do not hardcode credentials anywhere. Use `.env` files and `python-dotenv`.
Add `.env` to `.gitignore` immediately.

### LLM Integration
- Local models are assumed to be available via Ollama (`http://localhost:11434`)
  or a compatible OpenAI-compatible endpoint.
- Strategy results are cached in `data/cache/llm_results.json` (TTL 1 hour).
- For remote display of local inference: push results to a GitHub Gist via the
  GitHub API (token stored in `.env`) and have the frontend poll the Gist URL.

---

## Communication Style
- Be concise. Report what you did, show test output, state next step.
- Use tables and code blocks for clarity.
- Never produce a wall of prose. Structure output as: **Built → Tested → Next**.
