# Handover

This repository includes the app code, docs, demo data, `.env`, and the current
local retained memory file.

## Run It

```bash
make install
make run
```

Or manually:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Validate It

```bash
make smoke
```

The smoke test runs in deterministic fallback mode and does not require
Hindsight Docker or Groq credentials.

## Included Runtime State

- `.env` is tracked for handoff convenience.
- `data/local_memory.json` is tracked so the learning-loop state is included.
- `.venv/`, caches, and logs are not tracked because they are generated and
  machine-specific.

Before pushing to a public remote, review `.env` and rotate or remove any real
tokens.
