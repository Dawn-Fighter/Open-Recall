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
```

Run the app:

```bash
streamlit run app.py
```

Run checks before opening a pull request:

```bash
python -m compileall app.py incident_agent seed_memory.py scripts/smoke_test.py
python scripts/smoke_test.py
```

## Pull Request Checklist

- Keep `.env`, `.streamlit/secrets.toml`, `data/local_memory.json`, and logs out
  of git.
- Update `README.md` or `docs/` when behavior, setup, or demo flow changes.
- Include screenshots for meaningful UI changes.
- Keep fallback mode working without Hindsight Docker or Groq credentials.
