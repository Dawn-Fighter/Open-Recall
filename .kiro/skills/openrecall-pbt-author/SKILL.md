---
name: openrecall-pbt-author
description: Author a new Hypothesis property test for OpenRecall. Use when adding a property test, writing the strategy for a new model field, extending the bypass invariant, or migrating an example test to a property test. Loads the conftest strategy catalog, the file-to-property mapping, and the docstring + settings template.
---

# Author a Hypothesis property test for OpenRecall

When the user asks to write a property test, follow these steps in order.

## Step 1 — Identify which file the test belongs in

| Subject | File | Properties already there |
|---|---|---|
| AlertFingerprint, fingerprint roundtrip | `tests/property/test_fingerprint.py` | P1, P2 |
| TriageEngine, triage decisions | `tests/property/test_triage.py` | P3, P4, P5, P6, P11, P12 |
| IncidentMemory.retain / recall | `tests/property/test_memory.py` | P7, P10, P13 |
| CostCurveTracker, budget | `tests/property/test_cost_curve.py` | P8, P9, P14 |
| Workflow end-to-end, audit, queue | `tests/property/test_workflow.py` | P15, queue-ordering, e2e |

If the new property doesn't fit any of these, it likely indicates a missing
abstraction; surface that observation to the user before adding a new file.

## Step 2 — Pick the right strategies from conftest

The full strategy catalog lives in
`incident-memory-agent/tests/property/conftest.py`. Use ONLY these:

| Strategy | Returns | When to use |
|---|---|---|
| `alert_fingerprint_strategy()` | `AlertFingerprint` | Any test that needs an arbitrary fingerprint. Tokens are lowercase + digits + `-_` so round-trip parsing stays clean. |
| `triage_decision_strategy` | `TriageDecision` Literal | Any test that needs an arbitrary triage decision. Already a strategy, no parens. |
| `memory_match_strategy(score_min, score_max, decision)` | `MemoryMatch` | Lock the score range when testing "Strong_Match" (>=0.85) or "weak match" (<0.85) cases. Lock `decision=` when seeding a deterministic dominant decision. |
| `strong_match_set_strategy(dominant_decision, n_total, agreement_count)` | `list[MemoryMatch]` | Build a set with controlled consistency. All scores in `[0.85, 1.0]`. Use when testing the bypass invariant (P6) or the consistency clamp (P5). |
| `raw_alert_strategy` | `str` | Any test taking arbitrary alert text. Excludes Unicode surrogates so the regex extractor stays well-defined. |

For complex compositions, use `data=st.data()` and `data.draw(...)` inside
the test body. The bypass invariant test is a working example.

## Step 3 — Pick the right fixtures

| Fixture | Purpose |
|---|---|
| `frozen_router` | `CascadeFlowRouter` with `live_groq=False`. Fresh per Hypothesis example. |
| `frozen_memory` | `_DictBackedMemory()` instance. Has `set_fingerprint_recall(fp, matches)` and an in-memory dedupe-honoring `retain`. Use when one-shot. For Hypothesis tests where each example needs a clean store, instantiate `_DictBackedMemory()` inside the test body and import via `from .conftest import _DictBackedMemory`. |
| `frozen_tracker` | Fresh `CostCurveTracker`. |

When a fixture is used inside `@given`, add
`suppress_health_check=[HealthCheck.function_scoped_fixture]` to settings.

## Step 4 — Use the canonical docstring tag

**Every property test docstring must carry these two lines:**

```python
def test_my_new_property(frozen_router, ...) -> None:
    """One-line summary.

    Longer rationale paragraph if needed.

    Feature: openrecall, Property N: <text matching the design doc>.
    Validates: Requirements R<X>.<Y>[, R<X>.<Y>...]
    """
```

If the new test doesn't map cleanly to a property in
`#correctness-properties`, do NOT invent a property number; instead use
`Feature: openrecall, <descriptor>:` (without "Property N") — see the
queue-ordering and Demo_Mode end-to-end tests for the existing pattern.

## Step 5 — Apply the standard settings

```python
from hypothesis import HealthCheck, given, settings, strategies as st

@given(...)
@settings(max_examples=100, deadline=None)
def test_my_new_property(...) -> None:
    ...
```

Settings tuning:

- `max_examples=100` — invariant properties (P1, P2, P3, P4, P9, P11, P12, P13).
- `max_examples=50` or `30` — tests that run the full `analyze` pipeline
  (P5, P6, P10, P14, P15, e2e).
- `deadline=None` — always set, the workflow can take >200 ms on Windows.
- `suppress_health_check=[HealthCheck.function_scoped_fixture]` — when
  using `frozen_router`/`frozen_memory` inside `@given`.

## Step 6 — Verify under the CI seed before declaring done

```bash
cd incident-memory-agent
set OPENRECALL_PBT_SEED=20260101    # Windows
set HYPOTHESIS_PROFILE=ci
set CASCADEFLOW_LIVE_GROQ=false
set HINDSIGHT_BASE_URL=http://127.0.0.1:9
python -m pytest tests/property/test_<file>.py::test_<name> -q --hypothesis-profile=ci
```

The new test must pass under the deterministic CI seed at least 100
examples before it's complete.

## Step 7 — Update the steering map

After landing the test, update `.kiro/steering/correctness-properties.md`
with:

- The property number (or descriptor) and statement.
- The exact test path (file::function).
- The validates line (R<X>.<Y> clauses).
- The touch-points table at the bottom (which modules can break this property).

## Common mistakes to avoid

- ❌ Using `random.random()` or `time.time()` inside a strategy. Strategies
  must be Hypothesis-driven so shrinking works.
- ❌ Asserting `==` on floats from cost calculations. Use `<= ... + 1e-9` or
  `pytest.approx()`.
- ❌ Leaving `os.environ` mutations live across test boundaries. Always
  reset at end-of-test (see `test_budget_enforcement` for the pattern).
- ❌ Generating raw_alert with surrogate codepoints. The blacklist
  `("Cs",)` in `raw_alert_strategy` already handles this; don't bypass it.
- ❌ Creating new strategies inside a test. Strategies belong in `conftest.py`
  so they're reusable.
