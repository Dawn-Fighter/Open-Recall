# Handover — OpenRecall

This repository ships the OpenRecall alert triage cockpit, the supporting
package code, the synthetic demo data, and the test suite. Live secrets
(`.env`) and per-session retained memory (`data/local_memory.json`) are
intentionally gitignored.

## Run It

```bash
make install
make run
```

Or manually:

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows
# .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # then edit .env with your keys
streamlit run app.py
```

## Validate It

```bash
make compile  # python -m compileall ...
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
- `.venv/`, `__pycache__/`, `.hypothesis/`, and other generated files are
  gitignored.

## Before Pushing Public

Rotate any keys that touched `.env` during local development, then push.
`SECURITY.md` documents the rotation steps.
