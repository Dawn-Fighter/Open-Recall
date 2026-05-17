---
name: openrecall-spec-trace
description: Trace a code change to its requirement IDs, correctness properties, and verification gates for OpenRecall. Use when reviewing a diff, planning a refactor, deciding which tests to run after a change, or auditing whether a proposed change is in or out of spec scope.
---

# Trace OpenRecall code changes to spec contracts

When given a code change (diff, file, or proposed edit), produce a four-line
summary:

```
Touches:        <files / functions>
Requirements:   <R<X>.<Y> list>
Properties:     <P<N> list>
Verify with:    <commands to run>
```

## File → Requirement / Property cheat sheet

| File | Owns | Properties to re-verify |
|---|---|---|
| `incident_agent/models.py` | All Pydantic data models | P10 (parity), P15 (if RouteTrace fields change) |
| `incident_agent/fingerprint.py` | AlertFingerprint extractor + (de)serializer | P1, P2 |
| `incident_agent/triage.py` | TriageEngine + thresholds | P3, P4, P5, P6, P11, P12 |
| `incident_agent/memory.py` | Hindsight Cloud + local fallback + idempotent retain | P7, P10, P13 |
| `incident_agent/router.py` | cascadeflow + Groq + budget enforcement + bypass trace | P6, P14, P15 |
| `incident_agent/cost_curve.py` | In-memory cost series | P8, P9 |
| `incident_agent/audit.py` | AuditTraceRecorder | P15 |
| `incident_agent/workflow.py` | Orchestrator | P6, P9, P15, queue-ordering, e2e |
| `app.py` | Streamlit cockpit (no PBT coverage; UX layer) | (visual smoke + signature) |
| `data/seed_incidents.json` | Synthetic memory seeds | smoke schema check |
| `data/seed_alerts.json` | Synthetic queue batch | smoke + determinism hook |
| `scripts/smoke_test.py` | 4 smoke sub-checks | smoke_test self |
| `scripts/generate_seed_alerts.py` | Deterministic batch generator | determinism hook |
| `tests/property/conftest.py` | Hypothesis strategies + fixtures | All property tests |

## Requirement → Property reverse index

| Requirement | Properties |
|---|---|
| R1.1, R1.2, R1.3 | (signature test) |
| R1.4 | P15 |
| R2.1, R2.4 | queue ordering |
| R2.5 | (smoke + e2e) |
| R3.3, R3.4 | P1 |
| R3.6, R3.7 | P2 |
| R5.1, R5.2, R5.3 | P3 |
| R5.2 | P4 |
| R5.2, R5.5 | P5 |
| R5.4 | P11 |
| R5.6 | P12 |
| R6.1, R6.4, R6.5 | P6 |
| R6.6 | P14 |
| R7.4, R7.5, R8.5 | P13 |
| R8.3 | P7 |
| R8.6 | smoke schema |
| R9.1, R9.4 | P9 |
| R9.5 | P8 |
| R10.1, R10.3 | P15 |
| R10.4 | (RouteTrace shape; structural test) |
| R11.4 | P10 |
| R11.6, R14.3 | (smoke) |
| R12.4 | smoke env-example regex check |

## Touch-point matrix (most common scenarios)

### Adding a new TriageDecision value

- Edit `models.py` `TriageDecision = Literal[...]`
- Edit `triage.py` (no value list edits — Literal handles set membership; but
  bypass-eligible set in `workflow.py` may need extension)
- Edit `app.py` `TRIAGE_PILL_CLASS` palette + add CSS class in `inject_css`
- Re-run: P3, P4, P5, P6, P11, P12 (test_triage.py)

### Adding a new RouteTrace step in router or workflow

- Edit `router.py` (emit the step) or `workflow.py` (append to route_trace)
- Edit `audit.py` (no edit needed — `build` is one-entry-per-trace)
- Edit `models.py` (only if RouteTrace fields change)
- Re-run: P15 (test_workflow.py::test_audit_trace_completeness), full PBT

### Adding a new env var

- Edit `.env.example` (placeholder only)
- Edit `README.md` Configuration table
- Edit `.kiro/steering/tech.md` env section
- Edit `scripts/smoke_test.py::smoke_env_example` required keys
- Edit `design.md` Configuration table
- Re-run: smoke (env-example check)

### Changing a triage threshold

- Edit `triage.py` constants only
- Re-run: full triage PBT (test_triage.py)
- Audit: `test_strong_model_bypass_invariant` may need `n_total >= K`
  bumped if `BYPASS_CONFIDENCE_THRESHOLD` changed

### Touching the Hindsight client wiring

- Edit `memory.py` `_build_hindsight_client` or `_init_hindsight`
- Confirm: `_flip_to_fallback` is still called on per-request failures
- Re-run: P10 (test_memory.py::test_fallback_vs_cloud_structural_parity), smoke

### Changing the cost-curve recording rule

- Edit `cost_curve.py` (rare) or `workflow.py` (where `record()` is called)
- Re-run: P8, P9 (test_cost_curve.py), and the workflow e2e tests

## Verification command catalog

| Goal | Command |
|---|---|
| Compile only | `cd incident-memory-agent && python -m compileall app.py incident_agent seed_memory.py scripts/smoke_test.py scripts/generate_seed_alerts.py tests` |
| All PBT under CI seed | `cd incident-memory-agent && set OPENRECALL_PBT_SEED=20260101 && set HYPOTHESIS_PROFILE=ci && python -m pytest tests/property -q --hypothesis-profile=ci` |
| Single property file | `cd incident-memory-agent && python -m pytest tests/property/test_<name>.py -q --hypothesis-profile=ci` |
| Single property test | `cd incident-memory-agent && python -m pytest tests/property/test_<file>.py::test_<func> -q --hypothesis-profile=ci` |
| Signature tests | `cd incident-memory-agent && python -m pytest tests/test_signatures.py -q` |
| Smoke (4 sub-checks) | `cd incident-memory-agent && python scripts/smoke_test.py` |
| Full local CI | `cd incident-memory-agent && make compile && make pbt && make smoke` |

## When a change is OUT OF SPEC

Some proposed changes don't trace to any requirement clause. Examples:

- A new tab in the cockpit (the design contract is **two** tabs, no more).
- A new memory backend besides Hindsight Cloud + local JSON.
- Slack/Teams/PagerDuty live ingestion.
- A new autoscaling rule for the Groq budget.

When you see one of these, push back to the user before coding. Cite the
"Out of Scope" section of `requirements.md` and `tasks.md`'s "Non-goals" if
the change crosses those lines.

## Output format expected

When asked to trace a change, respond with:

```
Touches:        incident_agent/triage.py (TriageEngine.triage)
Requirements:   R5.3, R5.4, R5.6
Properties:     P3, P4, P11, P12 (must re-verify); P5, P6 (no impact unless thresholds changed)
Verify with:    cd incident-memory-agent && python -m pytest tests/property/test_triage.py -q --hypothesis-profile=ci
Notes:          (any spec-scope or out-of-spec flags)
```
