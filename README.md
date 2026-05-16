# Open-Source Hindsight Incident Memory Agent

A production incident cockpit for SRE and security response. The app recalls
similar incidents with open-source Hindsight, routes investigation work through
CascadeFlow/Groq-style cost-aware paths, produces verification-first runbooks,
and retains the final RCA so future incidents start with operational memory.

The project is built to demo well without fragile dependencies: it runs in a
deterministic local fallback mode by default, then upgrades to live Hindsight and
Groq calls when those services are configured.

## Features

- Incident intake for raw alerts, logs, or paging notes.
- Normalized incident object with service, environment, severity, dependency,
  recent change, and security relevance.
- Hindsight recall, reflection, and retain workflow.
- CascadeFlow-style routing trace with model, confidence, escalation, latency,
  estimated cost, budget remaining, and savings versus strong-model-only runs.
- Evidence preservation, containment notes, remediation steps, response roles,
  timeline notes, and postmortem actions.
- Learning loop that stores final RCA, commands, and lessons after resolution.
- Local fallback mode for demos, CI, and offline review.

## Quick Start

```bash
cd /home/edneam/incident-memory-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Open the Streamlit URL printed by the command. If Hindsight is not running, the
app clearly shows `Fallback memory` and uses the synthetic seed incidents in
`data/seed_incidents.json`.

## Live Hindsight Demo

Start Hindsight in another terminal:

```bash
export GROQ_API_KEY=gsk_your_key_here
docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_PROVIDER=groq \
  -e HINDSIGHT_API_LLM_MODEL=openai/gpt-oss-20b \
  -e HINDSIGHT_API_LLM_API_KEY=$GROQ_API_KEY \
  -e HINDSIGHT_API_RETAIN_CHUNK_SIZE=1000 \
  -e HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS=4096 \
  -v hindsight-pg0:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest
```

Useful URLs:

- Hindsight API: `http://localhost:8888`
- Hindsight UI: `http://localhost:9999`
- Memory bank: `incident-memory-agent`

Seed memories:

```bash
source .venv/bin/activate
python seed_memory.py --limit 5 --delay 0
```

For a judged or recorded demo with real routing calls:

```bash
export CASCADEFLOW_LIVE_GROQ=true
streamlit run app.py
```

The top badges should show `Hindsight connected` and `Live model calls`. If they
show fallback or deterministic mode, the workflow still runs but does not prove
the live integration.

## Environment

Copy `.env.example` to `.env` and update the values you need.

```bash
GROQ_API_KEY=gsk_...
HINDSIGHT_BASE_URL=http://localhost:8888
HINDSIGHT_BANK_ID=incident-memory-agent
CASCADEFLOW_MODE=observe
CASCADEFLOW_LIVE_GROQ=false
CASCADEFLOW_RUN_BUDGET_USD=0.02
CASCADEFLOW_CHEAP_MODEL=qwen/qwen3-32b
CASCADEFLOW_STRONG_MODEL=openai/gpt-oss-120b
```

Never commit `.env`, `.streamlit/secrets.toml`, logs, or
`data/local_memory.json`.

## Architecture

```text
Raw alert
  -> normalize incident object
  -> classify SRE / Security / Hybrid
  -> recall similar memories from Hindsight or local seed data
  -> route RCA generation through cheap or strong model path
  -> produce verification-first runbook
  -> retain final RCA and lessons after resolution
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for component details.

## Demo Flow

1. Run `streamlit run app.py`.
2. Select `Known SRE: checkout CrashLoopBackOff` to show memory-assisted RCA.
3. Select `Security: WAF SQL injection` to show security escalation.
4. Select `Learning loop: cold fraud scoring outage`, retain the final RCA, and
   rerun to show the newly recalled memory.
5. Point to the audit trace for route reason, model, confidence, latency, cost,
   live-call status, and budget remaining.

See [docs/DEMO.md](docs/DEMO.md) for the full presenter runbook.

## Development

Run deterministic validation:

```bash
python -m compileall app.py incident_agent seed_memory.py scripts/smoke_test.py
python scripts/smoke_test.py
```

The smoke test intentionally uses fallback mode, so it can run in CI without
Hindsight Docker or Groq credentials.

Shortcut targets are available through `make`:

```bash
make install
make run
make smoke
```

## Repository Layout

```text
app.py                    Streamlit incident cockpit
incident_agent/           Memory, routing, models, and workflow code
data/sample_alerts.json   Demo alert inputs
data/seed_incidents.json  Synthetic incident memory seed set
scripts/smoke_test.py     Deterministic workflow validation
docs/                     Architecture, demo, and submission notes
content/                  Draft article, social post, and video script
```

## Why This Is Useful

Most response tools start fresh every incident. This project makes previous
postmortems and verified commands available inside the next triage loop, while
keeping model routing, escalation, and cost visible to the operator.

## License

MIT. See [LICENSE](LICENSE).
