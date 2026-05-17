.PHONY: install run seed pbt smoke compile

install:
	python -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/streamlit run app.py

seed:
	.venv/bin/python seed_memory.py --limit 5 --delay 0

compile:
	.venv/bin/python -m compileall app.py incident_agent seed_memory.py scripts/smoke_test.py scripts/generate_seed_alerts.py tests

pbt: compile
	.venv/bin/python -m pytest tests/property -q

smoke: compile pbt
	.venv/bin/python scripts/smoke_test.py
