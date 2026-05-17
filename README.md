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

## Features

- Single-alert RCA cockpit (preserved from the original "Single alert" tab).
- Queue tab for batch triage: drop in 100 alerts, watch the cost curve drop.
- AlertFingerprint extraction (cheap-model JSON with regex fallback).
- Fingerprint-keyed Hindsight Cloud recall + idempotent retain.
- Counterfactual memory: every retained alert stores triage decision + dead ends.
- TriageEngine with hard thresholds (Strong_Match ≥ 0.85, consistency ≥ 0.9)
  and a security-novel kill switch.
- CascadeFlow router with cumulative live-cost tracking, per-batch budget
  enforcement, and a synthetic memory-bypass RouteTrace for full audit
  completeness.
- Altair cost-curve chart with shaded savings band against the
  strong-model-only baseline.
- Per-row override flow: accept the proposed decision or override it,
  attach dead ends, retain to Hindsight (with local JSON fallback).
- Hypothesis-based property test suite covering 15 correctness properties.
- Deterministic offline mode for CI and demo recordings without credentials.

## Quick Start

```bash
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env  # then edit .env with your keys
streamlit run app.py
```

Open the Streamlit URL printed by the command. The cockpit shows two tabs:

- **Single alert** — paste a raw page or pick a sample, get the full RCA + audit trace.
- **Queue** — upload a JSON array of alerts, click `Use packaged seed alerts (100)`,
  or paste in your own. Watch the cost curve drop as memory accumulates.

If `HINDSIGHT_API_KEY` is unset or Hindsight Cloud is unreachable, the app
falls back to the deterministic local memory store (`data/seed_incidents.json`
+ `data/local_memory.json`). Badges at the top of the cockpit make the mode
visible.

## Live Hindsight Cloud Demo

OpenRecall is wired to Hindsight Cloud at `https://api.hindsight.vectorize.io`
via the `hindsight-client` SDK. Set:

```bash
export HINDSIGHT_API_KEY=hsk_your_key_here
export HINDSIGHT_BANK_ID=openrecall
export GROQ_API_KEY=gsk_your_key_here
export CASCADEFLOW_LIVE_GROQ=true
streamlit run app.py
```

The top badges should show `Hindsight connected` and `Live model calls`. If
they show `Fallback memory` or `Deterministic model output`, the workflow
still runs (and produces the same audit trace + cost curve), but does not
prove the live integration.

Seed memories into Hindsight Cloud:

```bash
python seed_memory.py --limit 5 --delay 0
```

Or use the **Seed 5 memories into Hindsight** button in the cockpit sidebar.

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

## Architecture

```text
Raw alert
  -> generate AlertFingerprint (cheap model JSON or regex fallback)
  -> recall_by_fingerprint() against Hindsight Cloud (or local fallback)
  -> TriageEngine.triage(fingerprint, matches)
       -> propose decision + confidence + escalation reason
       -> security-novel kill switch when attack_pattern non-empty
  -> if memory consistent AND confidence >= 0.85 AND attack_pattern empty:
       -> emit synthetic memory-bypass RouteTrace, skip the LLM entirely
     else:
       -> rca_with_trace() with dead_ends from matched memories in the prompt
  -> record CostCurvePoint (cost vs strong-model baseline)
  -> build AuditTraceEntry list (one entry per RouteTrace, per P15)
  -> retain final triage decision + dead ends after analyst override
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for component diagrams and
the full design.

## Demo Flow

1. Run `streamlit run app.py`.
2. **Queue tab → click `Use packaged seed alerts (100)`** → click `Analyze queue`.
3. Watch the cost curve render and the queue table populate. Note how many
   alerts have memory consulted vs how many escalate.
4. Pick one row with `proposed_decision = escalated` and click `Override`.
   Set the decision to `false_positive`, add a dead end, click `Save & retain`.
5. Re-run `Analyze queue`. The same fingerprint family is now memory-consistent;
   watch the cost curve flatten near zero for those repeats.
6. Switch to the **Single alert** tab and pick `Security: WAF SQL injection`.
   The badges and audit trace show the security-novel kill switch in action.

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
python -m pytest tests -q                                  # 21 tests
python -m pytest tests/property --hypothesis-profile=ci -q # 17 PBT under CI seed
python scripts/smoke_test.py
```

The Hypothesis suite uses a deterministic CI profile with `OPENRECALL_PBT_SEED=20260101`
so failing examples reproduce. The smoke test runs in offline mode against
`HINDSIGHT_BASE_URL=http://127.0.0.1:9` so CI never needs network access.

## Repository Layout

```text
app.py                          Streamlit cockpit (Single alert + Queue tabs)
incident_agent/
  models.py                     Pydantic v2 data models
  fingerprint.py                AlertFingerprint generator + canonical (de)serializer
  triage.py                     TriageEngine + threshold constants
  memory.py                     IncidentMemory (Hindsight Cloud + local JSON fallback)
  router.py                     CascadeFlowRouter + cumulative live-cost tracking
  cost_curve.py                 CostCurveTracker (in-memory series)
  audit.py                      AuditTraceRecorder
  workflow.py                   IncidentWorkflow.analyze + analyze_queue
data/
  sample_alerts.json            Original 6 demo alerts (single-alert tab)
  seed_alerts.json              100 synthetic alerts (queue demo)
  seed_incidents.json           18 synthetic incident memories with triage_decision + dead_ends
  local_memory.json             Local-fallback retained memories (gitignored at runtime)
scripts/
  smoke_test.py                 Deterministic offline smoke (single + queue + schema + env)
  generate_seed_alerts.py       Deterministic generator for data/seed_alerts.json
tests/
  test_signatures.py            Backward-compat signature checks
  property/                     Hypothesis property tests (15 correctness properties)
docs/                           Architecture, demo, hackathon submission notes
content/                        Article, social post, video script (hackathon deliverables)
```

## Why This Is Useful

Most response tools start fresh every alert. Even the same false-positive
scanner gets re-investigated every shift. OpenRecall makes prior triage
decisions and the dead ends behind them available before the next
investigation begins, while keeping every model routing and cost decision
visible to the operator in real time.

## License

MIT. See [LICENSE](LICENSE).
