# IT Ops — AI Computer Operator for IT Operations

IT Ops is an MVP AI computer operator that accepts a natural-language employee onboarding goal, operates a synthetic IT administration portal through a real Playwright browser, pauses for privileged-access approval, recovers from a controlled grant failure, independently verifies the final state, and produces local evidence.

This repository is the submission for the Hulchul AI Engineering build assignment (computer operator prototype).

## What it demonstrates

| Requirement | How IT Ops shows it |
|-------------|---------------------|
| Working execution | Playwright drives the real `/portal` UI to grant access |
| Adaptability | Same code, different goals: Alex (Marketing) vs Priya (Finance) |
| Recovery | CRM is seeded to fail once on grant; agent retries safely |
| Verified completion | Final state checks + screenshots / `result.json` under `evidence/` |
| Human control | Privileged Admin Console pauses for Approve / Reject |

## Architecture (high level)

- **Next.js** — IT Ops dashboard + synthetic IT portal (`/portal/*`)
- **FastAPI** — sole backend/API boundary (runs, HITL, SSE, portal APIs, evidence)
- **LangGraph** — single-agent workflow + SQLite checkpointer (`checkpoints.db`)
- **SQLite** — authoritative domain/action state (`it_ops.db`)
- **Playwright** — real UI interaction with the portal (never bypasses the UI for grants)
- **LangSmith** — optional tracing only (not required to run)

## Repository structure

```text
frontend/          Next.js dashboard + portal
backend/           FastAPI, LangGraph agent, tools, browser, db, events
scripts/           seed_db.py, reset_db.py
tests/             unit + API tests (source included; caches are gitignored)
evidence/          per-run screenshots + result.json (local only; gitignored)
data/              SQLite databases (gitignored)
ENGINEERING_NOTES.md   Choices, AI assistance, limitations, next steps
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key (required for the agent)
- Git

Optional: LangSmith account (tracing only)

## Quick start (clone → run)

```bash
git clone https://github.com/Souravmane3000/IT-Ops-.git
cd IT-Ops-
```

### 1) Python environment

```bash
python -m venv .venv

# Windows (PowerShell / CMD)
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 2) Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3) Environment

Copy the example env file and add your OpenAI key. **Do not commit `.env`.**

```bash
# Windows
copy .env.example .env

# macOS / Linux
# cp .env.example .env
```

Edit `.env` and set at least:

```env
OPENAI_API_KEY=your_key_here
PLAYWRIGHT_HEADLESS=false
NEXT_PUBLIC_API_URL=http://localhost:8000
PLAYWRIGHT_BASE_URL=http://localhost:3000
```

### 4) Seed demo data

```bash
python scripts/seed_db.py
```

### 5) Run (two terminals)

Terminal 1 — frontend:

```bash
cd frontend
npm run dev
```

Terminal 2 — backend (from repo root, venv active):

```bash
uvicorn backend.main:app --reload --port 8000
```

Then open:

- Dashboard: http://localhost:3000
- Portal: http://localhost:3000/portal
- API health: http://localhost:8000/health

## Clean demo startup (recommended for reviewers)

Use a **non-reload** backend and headed Playwright so the Chromium window is visible.

PowerShell:

```powershell
# 0) Stop leftover uvicorn / Playwright Chromium if needed
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'uvicorn backend.main|playwright|chrome-for-testing' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 1) Force headed browser (shell env can override .env)
Remove-Item Env:PLAYWRIGHT_HEADLESS -ErrorAction SilentlyContinue
$env:PLAYWRIGHT_HEADLESS = "false"

# 2) Reset (stop backend first if checkpoints.db is locked)
.\.venv\Scripts\python scripts\reset_db.py

# 3) Backend — NO --reload for demos
.\.venv\Scripts\uvicorn backend.main:app --port 8000

# 4) Frontend (separate terminal)
cd frontend
npm run dev
```

Open http://localhost:3000 and click **Start Run** once.

After each demo take: stop the backend if needed, run `python scripts/reset_db.py`, then restart.

## Demo workflow

1. Follow **Clean demo startup** above
2. Default goal (Alex / Marketing Manager) — Start Run
3. Watch Playwright operate `/portal`
4. When prompted, **Approve** or **Reject** Admin Console (privileged)
   - Reject is valid: Admin stays not granted; run status is still **complete**
5. Observe CRM controlled failure + one safe retry
6. Inspect verification + evidence on the run page
7. Reset DB, then run the variation (no code changes):

```text
Onboard Priya as a Finance Analyst and give her the applications required by policy.
```

Priya’s Finance policy grants **GitHub** and **Slack** only (no privileged Admin Console interrupt).

## Reset demo environment

```bash
python scripts/reset_db.py
```

Recreates `data/it_ops.db`, clears `data/checkpoints.db`, clears evidence run folders, and reseeds.

## Tests

Unit / API tests (no live browser required for most):

```bash
pytest
```

Optional browser integration tests:

```bash
# Windows PowerShell
$env:RUN_BROWSER_TESTS = "1"
$env:PLAYWRIGHT_HEADLESS = "true"
pytest
```

```bash
# macOS / Linux
# RUN_BROWSER_TESTS=1 PLAYWRIGHT_HEADLESS=true pytest
```

## Environment variables

See [`.env.example`](.env.example). Important keys:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | LLM calls (required) |
| `IT_OPS_DB_PATH` | Domain SQLite |
| `CHECKPOINT_DB_PATH` | LangGraph checkpoints |
| `NEXT_PUBLIC_API_URL` | Frontend → API |
| `PLAYWRIGHT_BASE_URL` | Browser target |
| `PLAYWRIGHT_HEADLESS` | `false` for demo, `true` for CI-style tests |
| `LANGCHAIN_*` | Optional LangSmith tracing |

## Model / account requirements

- OpenAI API access (default model `gpt-4o-mini`, overridable via `OPENAI_MODEL`)
- LangSmith optional

## What is intentionally not in git

These stay local (see `.gitignore`):

- `.env` / `frontend/.env.local` (secrets and machine-specific URLs)
- `.venv/`, `frontend/node_modules/`, `frontend/.next/`
- `data/*.db` and SQLite sidecars
- `evidence/run_*/` artifacts from local runs
- pytest / coverage caches, `__pycache__`, logs

Committed intentionally:

- Application source (`backend/`, `frontend/` without `node_modules`)
- `tests/` source
- `.env.example`, `scripts/`, docs (`README.md`, `ENGINEERING_NOTES.md`, `PRD.md`, architecture)

## Engineering note

See [`ENGINEERING_NOTES.md`](ENGINEERING_NOTES.md) for architecture choices, personal contribution, AI assistance disclosure (Cursor / Composer 2.5), limitations, and what I would build next.

## Notes

- Next.js never opens SQLite directly.
- The agent grants access only through Playwright → portal UI → FastAPI → SQLite.
- Source of truth for product/architecture: `PRD.md`, `Implementation Architecture.md`.
