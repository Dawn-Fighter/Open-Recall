# Handover — OpenRecall

This repository ships the OpenRecall alert triage cockpit: the FastAPI
backend (`api.py`), the Next.js frontend (`frontend/`), the supporting
package code (`incident_agent/`), the synthetic demo data, and the test
suite. Live secrets (`.env`) and per-session retained memory
(`data/local_memory.json`, `data/decision_cache.json`) are intentionally
gitignored.

## Run It

Two processes, two terminals.

```bash
# Terminal 1 — FastAPI backend on http://127.0.0.1:8000
make install    # python -m venv .venv && pip install -r requirements.txt
cp .env.example .env  # then edit .env with your keys
make api        # uvicorn api:app --reload --port 8000

# Terminal 2 — Next.js cockpit on http://localhost:3000
make frontend   # cd frontend && npm run dev
```

Or fully manual:

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

uvicorn api:app --reload --port 8000

# in another shell
cd frontend && npm install && npm run dev
```

## Validate It

```bash
make compile  # python -m compileall api.py incident_agent ...
make pbt      # property-based tests under tests/property/
make smoke    # offline smoke + queue smoke + .env.example schema
```

The smoke test runs in deterministic offline mode (`HINDSIGHT_BASE_URL=
http://127.0.0.1:9`, `CASCADEFLOW_LIVE_GROQ=false`) and does not require
network access.

## Runtime State

- `.env` is **not tracked**. Copy `.env.example` and fill in keys.
- `data/local_memory.json` is **not tracked**. The local fallback persists
  retained triage decisions there during demos; the file is gitignored to
  prevent leaking analyst IDs, business-impact minutes, or fingerprint
  metadata into source control.
- `data/decision_cache.json` is **not tracked**. The API uses it as a
  process-local hash cache for repeat alerts.
- `frontend/.next/`, `frontend/node_modules/`, `.venv/`, `__pycache__/`,
  `.hypothesis/`, and other generated files are gitignored.

## Before Pushing Public

Rotate any keys that touched `.env` during local development, then push.
`SECURITY.md` documents the rotation steps.
