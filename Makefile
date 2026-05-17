.PHONY: install api frontend seed pbt smoke compile

install:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

# Run the FastAPI backend on http://127.0.0.1:8000
api:
	.venv/bin/uvicorn api:app --reload --port 8000

# Run the Next.js cockpit on http://localhost:3000 (talks to the FastAPI backend)
frontend:
	cd frontend && npm run dev

seed:
	.venv/bin/python seed_memory.py --limit 5 --delay 0

compile:
	.venv/bin/python -m compileall api.py incident_agent seed_memory.py scripts/smoke_test.py scripts/generate_seed_alerts.py tests

pbt: compile
	.venv/bin/python -m pytest tests/property -q

smoke: compile pbt
	.venv/bin/python scripts/smoke_test.py
