# Contributing

This is a focused demo repository for the Hindsight x CascadeFlow incident
memory workflow. Keep changes small, explain user-visible behavior, and prefer
deterministic validation when live Hindsight or Groq credentials are not
available.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

cd frontend && npm install && cd ..
```

Run the backend:

```bash
uvicorn api:app --reload --port 8000
```

Run the frontend (in a second shell):

```bash
cd frontend && npm run dev
```

Run checks before opening a pull request:

```bash
python -m compileall api.py incident_agent seed_memory.py scripts/smoke_test.py
python -m pytest tests/property -q --hypothesis-profile=ci
python scripts/smoke_test.py
```

## Pull Request Checklist

- Keep `.env`, `data/local_memory.json`, `data/decision_cache.json`, and
  logs out of git.
- Update `README.md` or `docs/` when behavior, setup, or demo flow changes.
- Include screenshots for meaningful UI changes.
- Keep fallback mode working without Hindsight Cloud or Groq credentials.
