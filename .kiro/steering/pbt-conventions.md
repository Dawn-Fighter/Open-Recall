---
inclusion: fileMatch
fileMatchPattern: ["tests/property/**/*.py"]
---

# OpenRecall — Property-Based Testing Conventions

## What lives here

`tests/property/` is the **rubric-critical** evidence for the hackathon's
"Technical Implementation" criterion. Every correctness property in
`requirements.md` § Correctness Properties (P1–P15) maps to exactly one
Hypothesis test function here. Treat this directory like a reliability
contract.

## File-to-property mapping

| File | Properties | Function names |
|---|---|---|
| `test_fingerprint.py` | P1, P2 | `test_fingerprint_determinism_demo_mode`, `test_fingerprint_round_trip` |
| `test_triage.py` | P3, P4, P5, P6, P11, P12 | `test_triage_proposal_determinism`, `test_triage_confidence_bounds`, `test_confidence_reflects_history`, `test_strong_model_bypass_invariant`, `test_no_strong_match_escalates`, `test_security_novel_escalates` |
| `test_memory.py` | P7, P10, P13 | `test_retain_idempotent`, `test_fallback_vs_cloud_structural_parity`, `test_recall_then_retain_consistency` |
| `test_cost_curve.py` | P8, P9, P14 | `test_cost_curve_monotonic_repeating_distribution`, `test_cost_curve_never_exceeds_baseline`, `test_budget_enforcement` |
| `test_workflow.py` | P15 + queue + e2e | `test_audit_trace_completeness`, `test_analyze_queue_preserves_order`, `test_demo_mode_end_to_end` |

## Required docstring tag

Every property test docstring **must** carry the tag
`Feature: openrecall, Property N: <text>` so traceability tooling can scan
test sources for property coverage:

```python
def test_strong_model_bypass_invariant(...) -> None:
    """P6: no live strong-model call when memory is consistent and attack_pattern is empty.

    Constructs strong consistent matches via strong_match_set_strategy ...

    Feature: openrecall, Property 6: Strong-model bypass invariant.
    Validates: Requirements 6.1, 6.4, 6.5
    """
```

The `Validates:` line lists the requirement clauses the property closes.

## Hypothesis strategies (defined in `conftest.py`)

```python
# Tokens: lowercase, no whitespace, no semicolons / equals (to keep
# round-trip clean for AlertFingerprint canonical form).
_token = st.text(alphabet=string.ascii_lowercase + string.digits + "-_",
                 min_size=1, max_size=24)
_field_or_empty = st.one_of(st.just(""), _token)

# Composite for the AlertFingerprint Pydantic model.
@st.composite
def alert_fingerprint_strategy(draw) -> AlertFingerprint: ...

# Sampled Literal — convenient for filter chains.
triage_decision_strategy = st.sampled_from(
    ["false_positive", "duplicate", "known_benign", "real", "escalated"]
)

# Memory match with score range and optional decision lock.
@st.composite
def memory_match_strategy(draw, score_min=0.0, score_max=1.0,
                          decision: TriageDecision | None = None) -> MemoryMatch: ...

# Builds n_total Strong_Matches (score >= 0.85) where exactly
# agreement_count carry dominant_decision; rest carry random other decisions.
@st.composite
def strong_match_set_strategy(draw, dominant_decision, n_total,
                              agreement_count) -> list[MemoryMatch]: ...

raw_alert_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # exclude surrogates
    min_size=1, max_size=512,
)
```

## Fixtures (defined in `conftest.py`)

- `frozen_router` — `CascadeFlowRouter` with `live_groq=False`, no API key.
- `frozen_memory` — `_DictBackedMemory()` instance per test (skip parent
  `__init__` side effects, no Hindsight network, no JSON IO). Use the
  fixture for one-shot tests; use `_DictBackedMemory()` constructed inside
  the test body for Hypothesis tests where each example needs a clean store.
- `frozen_tracker` — fresh `CostCurveTracker`.

The `_DictBackedMemory` test double:

- Skips parent `IncidentMemory.__init__` (no Hindsight init, no file IO).
- `set_fingerprint_recall(fp, matches)` lets a test seed canned recall
  results for a specific fingerprint.
- `retain` honors the in-process dedupe index (so P7 holds) AND inserts the
  retained match into `_canned_recall` so the next `recall_by_fingerprint`
  surfaces it (so P13 holds).

## Settings discipline

```python
@settings(max_examples=100, deadline=None)
```

- `max_examples=100` is the floor for invariant properties (P1, P2, P3, P4,
  P9, P11, P12, P13).
- Use `max_examples=50` or `30` only for tests that run the full
  `IncidentWorkflow.analyze` pipeline (P6, P10, P14, P15) since each example
  is heavier.
- `deadline=None` because `analyze` may take >200 ms on Windows under
  property-driven generation.
- Add `suppress_health_check=[HealthCheck.function_scoped_fixture]` when
  using `frozen_router`/`frozen_memory` fixtures inside a `@given` test.

## CI Hypothesis profile

`conftest.py` registers two profiles:

```python
settings.register_profile("ci", max_examples=100, deadline=None,
                          derandomize=True)
settings.register_profile("default", max_examples=100, deadline=None)
```

CI runs with `--hypothesis-profile=ci` and `OPENRECALL_PBT_SEED=20260101`.
The conftest sets `HYPOTHESIS_SEED` from `OPENRECALL_PBT_SEED` so failing
examples reproduce deterministically.

## Confidence clamp formula (P5 reference)

`TriageEngine.confidence(consistency, n_strong)` returns
`min(c, max(c * n / (n + 1), c * (1 - 1 / (n + 2))))` where `c = consistency`.

For `c = 1.0`:

| n_strong | confidence |
|---|---|
| 1 | 0.667 |
| 2 | 0.750 |
| 3 | 0.800 |
| 4 | 0.833 |
| 5 | 0.857 ← first crosses BYPASS_CONFIDENCE_THRESHOLD=0.85 |
| 6 | 0.875 |
| 7 | 0.889 |

P6 (bypass invariant) tests must construct ≥6 Strong_Matches to deterministically
trigger the bypass condition. The local `recall_by_fingerprint` is hard-capped
at `limit=5`, so live workflows need ≥5 fully-agreeing strong matches to bypass.

## Determinism gotchas

- **Function-scoped fixtures with `@given` regenerate per example.** This
  means `frozen_memory` is a NEW instance per Hypothesis example, so
  retain-then-recall stays clean. Use this property to your advantage.
- **Avoid `data.draw(strategy)` inside loops** — generate the full input up
  front so shrinking works.
- **Avoid stateful globals** in property tests. The router's
  `_cum_live_cost` and `_budget_exhausted` ARE stateful; tests reset env
  vars at end-of-test (see `test_budget_enforcement`).
