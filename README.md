# OpenRecall

**Alert triage co-pilot for SOC analysts and on-call SRE/devs.** Built on
Hindsight Cloud for persistent memory and cascadeflow for runtime cost
intelligence. Counterfactual. Cost-aware. Auditable.

OpenRecall fingerprints every incoming alert as structured "alert DNA",
queries Hindsight Cloud for prior triage decisions on the same fingerprint,
and bypasses the strong model entirely when memory is consistent. Every
retained alert carries the analyst's final triage decision (false_positive,
duplicate, known_benign, real, escalated) plus the dead ends that prior
responders already explored — so future analysts skip the paths that
didn't work.

Three pillars earn this project its differentiation:

1. **Counterfactual memory + auto-triage.** Hindsight is consulted before
   any expensive model call. When prior decisions are consistent enough,
   OpenRecall proposes the triage decision and the strong model is bypassed
   entirely.
2. **Cost curve visibility.** The cockpit renders cost-per-alert dropping
   over time as memory grows, with an explicit comparison against a
   strong-model-only baseline.
3. **Alert DNA fingerprinting.** Alerts are reduced to a structured
   fingerprint (error_class, service_role, dependency_pattern, signal_shape,
   attack_pattern, environment) instead of free-text keyword overlap, and
   Hindsight retrieval keys on that fingerprint.

The project is built to demo well without fragile dependencies: it runs in a
deterministic offline mode by default, then upgrades to live Hindsight Cloud
and Groq calls when those services are configured.

## Architecture

OpenRecall is split into two processes:

- **FastAPI backend** (`api.py`) — exposes `/health`, `/stats`,
  `/cost-curve`, `/seed`, `/analyze`, `/retain`. Holds the
  `IncidentMemory`, `CascadeFlowRouter`, `CostCurveTracker`, and
  `IncidentWorkflow` singletons.
- **Next.js cockpit** (`frontend/`) — the analyst-facing UI. Submits raw
  alerts to `/analyze`, renders the triage card with fingerprint, decision
  pill, prior incidents, root causes, dead ends, and cost. Calls `/retain`
  on the override flow.

```text
Browser ──▶ Next.js (3000) ──fetch──▶ FastAPI (8000) ──▶ incident_agent/* ──▶ Hindsight Cloud + Groq
```

## Features

- Single-alert RCA (paste a raw page, get the full RCA + audit trace).
- Counterfactual memory: every retained alert stores triage decision + dead ends.
- AlertFingerprint extraction (cheap-model JSON with regex fallback).
- Fingerprint-keyed Hindsight Cloud recall + idempotent retain.
- TriageEngine with hard thresholds (Strong_Match ≥ 0.85, consistency ≥ 0.9)
  and a security-novel kill switch.
- CascadeFlow router with cumulative live-cost tracking, per-batch budget
  enforcement, and a synthetic memory-bypass RouteTrace for full audit
  completeness.
- Cost curve series exposed via `/cost-curve` (cumulative cost vs
  strong-model-only baseline).
- Per-alert override flow: accept the proposed decision or override it,
  attach dead ends, retain to Hindsight (with local JSON fallback).
- Hypothesis-based property test suite covering 15 correctness properties.
- Deterministic offline mode for CI and demo recordings without credentials.

## Quick Start

### 1. Backend (FastAPI)

```bash
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env  # then edit .env with your keys

uvicorn api:app --reload --port 8000
```

The API is now live at `http://127.0.0.1:8000`. Visit `/docs` for the
auto-generated Swagger UI, or `/health` for a quick connectivity probe.

### 2. Frontend (Next.js)

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The cockpit talks to the FastAPI backend on
`localhost:8000` (CORS is wide open in dev).

If `HINDSIGHT_API_KEY` is unset or Hindsight Cloud is unreachable, the
backend falls back to the deterministic local memory store
(`data/seed_incidents.json` + `data/local_memory.json`). The `/health`
endpoint reports the live mode.

## Live Hindsight Cloud Demo

OpenRecall is wired to Hindsight Cloud at `https://api.hindsight.vectorize.io`
via the `hindsight-client` SDK. Set:

```bash
export HINDSIGHT_API_KEY=hsk_your_key_here
export HINDSIGHT_BANK_ID=openrecall
export GROQ_API_KEY=gsk_your_key_here
export CASCADEFLOW_LIVE_GROQ=true
uvicorn api:app --reload --port 8000
```

`GET /health` should return `"hindsight_connected": true` and
`"groq_live": true`. If they return `false`, the workflow still runs (and
produces the same audit trace + cost curve), but does not prove the live
integration.

Seed memories into Hindsight Cloud:

```bash
python seed_memory.py --limit 5 --delay 0
```

Or call `POST /seed` against the running API.

## Configuration

OpenRecall reads every API key from environment variables only. Copy
`.env.example` to `.env` and fill in the values you need.

| Variable | Default | Read by | Purpose |
| --- | --- | --- | --- |
| `HINDSIGHT_BASE_URL` | `https://api.hindsight.vectorize.io` | `IncidentMemory._init_hindsight` | Hindsight Cloud API base URL. |
| `HINDSIGHT_API_KEY` | unset | `IncidentMemory._init_hindsight` | Bearer token for Hindsight Cloud; required to use the cloud path. |
| `HINDSIGHT_BANK_ID` | `openrecall` | `IncidentMemory._init_hindsight`, `retain` | Memory bank ID inside Hindsight Cloud. |
| `HINDSIGHT_SEED_LIMIT` | `0` (all) | `IncidentMemory.seed` | Limit number of seed memories pushed at startup. |
| `HINDSIGHT_SEED_DELAY_SECONDS` | `0` | `IncidentMemory.seed` | Delay between seed retain calls (rate-limit pacing). |
| `GROQ_API_KEY` | unset | `CascadeFlowRouter.__init__` | Groq API key for live LLM calls. |
| `CASCADEFLOW_MODE` | `observe` | `CascadeFlowRouter._init_cascadeflow` | cascadeflow init mode. |
| `CASCADEFLOW_LIVE_GROQ` | `false` | `CascadeFlowRouter.__init__` | Toggle live Groq calls vs deterministic Demo_Mode. |
| `CASCADEFLOW_RUN_BUDGET_USD` | `0.02` | `CascadeFlowRouter.__init__` | Per-batch live-call USD ceiling. |
| `CASCADEFLOW_CHEAP_MODEL` | `qwen/qwen3-32b` | `CascadeFlowRouter.__init__` | Cheap routing model. |
| `CASCADEFLOW_STRONG_MODEL` | `openai/gpt-oss-120b` | `CascadeFlowRouter.__init__` | Strong escalation model. |
| `OPENRECALL_PBT_SEED` | `20260101` | `tests/property/conftest.py` | Hypothesis CI deterministic seed. |
| `OPENRECALL_BATCH_SIZE_LIMIT` | `200` | `IncidentWorkflow.analyze_queue` | Cap on batch size for queue processing. |

## API Surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness + Hindsight/Groq mode flags. |
| `GET` | `/stats` | Cumulative cost, savings, percent-saved, alert count. |
| `GET` | `/cost-curve` | Per-alert points: `{index, cost, baseline}`. |
| `POST` | `/seed` | Push `data/seed_incidents.json` into Hindsight. |
| `POST` | `/analyze` | Body `{alert: str}`. Runs the full workflow and returns the triage card payload. |
| `POST` | `/retain` | Body `{raw_alert, service, decision, dead_ends, ...}`. Closes the learning loop. |

Schema details available at `http://127.0.0.1:8000/docs` once the API is
running.

## Demo Flow

1. Start the API: `make api` (or `uvicorn api:app --reload --port 8000`).
2. Start the frontend: `make frontend` (or `cd frontend && npm run dev`).
3. Paste a raw alert into the cockpit, watch the agent trace and triage
   card render.
4. Pick an alert that returns `Escalated`. Click the override flow, set
   the decision to `false_positive`, add a dead end, save & retain.
5. Re-submit the same alert. The triage card should now show the cached
   decision and zero cost.
6. Try a security alert (e.g. WAF SQL injection). Confirm the
   security-novel kill switch fires (`requires_human_approval=true`).

See [docs/DEMO.md](docs/DEMO.md) for the full presenter runbook.

## Development

Run all checks locally:

```bash
make compile  # python -m compileall ...
make pbt      # property-based tests under tests/property/
make smoke    # deterministic offline smoke + queue smoke + .env.example schema
```

Or directly with pytest:

```bash
python -m pytest tests -q                                  # signature + integration
python -m pytest tests/property --hypothesis-profile=ci -q # 17 PBTs under CI seed
python scripts/smoke_test.py
```

The Hypothesis suite uses a deterministic CI profile with `OPENRECALL_PBT_SEED=20260101`
so failing examples reproduce. The smoke test runs in offline mode against
`HINDSIGHT_BASE_URL=http://127.0.0.1:9` so CI never needs network access.

## Repository Layout

```text
api.py                           FastAPI backend (the only Python entry point)
frontend/                        Next.js cockpit (App Router, Tailwind, shadcn)
incident_agent/
  models.py                      Pydantic v2 data models
  fingerprint.py                 AlertFingerprint generator + canonical (de)serializer
  triage.py                      TriageEngine + threshold constants
  memory.py                      IncidentMemory (Hindsight Cloud + local JSON fallback)
  router.py                      CascadeFlowRouter + cumulative live-cost tracking
  cost_curve.py                  CostCurveTracker (in-memory series)
  audit.py                       AuditTraceRecorder
  workflow.py                    IncidentWorkflow.analyze + analyze_queue
data/
  sample_alerts.json             6 demo alerts
  seed_alerts.json               100 synthetic alerts (queue demo)
  seed_incidents.json            18 synthetic incident memories with triage_decision + dead_ends
  local_memory.json              Local-fallback retained memories (gitignored)
scripts/
  smoke_test.py                  Deterministic offline smoke (single + queue + schema + env)
  generate_seed_alerts.py        Deterministic generator for data/seed_alerts.json
tests/
  test_signatures.py             Backward-compat signature checks
  property/                      Hypothesis property tests (15 correctness properties)
docs/                            Architecture, demo, hackathon submission notes
content/                         Article, social post, video script (hackathon deliverables)
```

## Why This Is Useful

Most response tools start fresh every alert. Even the same false-positive
scanner gets re-investigated every shift. OpenRecall makes prior triage
decisions and the dead ends behind them available before the next
investigation begins, while keeping every model routing and cost decision
visible to the operator in real time.

## License

MIT. See [LICENSE](LICENSE).
