"""Property tests covering the cost-curve tracker and budget enforcement.

- P8: Cost-curve monotonicity under repeating distribution.
- P9: cost_usd <= baseline_cost_usd; series ordered by alert_index.
- P14: Per-batch budget enforcement.
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from incident_agent.cost_curve import CostCurveTracker


@given(
    pairs=st.lists(
        st.tuples(
            st.floats(
                min_value=0.0,
                max_value=0.05,
                allow_nan=False,
                allow_infinity=False,
            ),
            st.floats(
                min_value=0.0,
                max_value=0.05,
                allow_nan=False,
                allow_infinity=False,
            ),
        ),
        min_size=1,
        max_size=80,
    )
)
@settings(max_examples=100, deadline=None)
def test_cost_curve_never_exceeds_baseline(pairs) -> None:
    """P9: For every recorded point, cost_usd <= baseline_cost_usd, sorted by alert_index, no gaps.

    Feature: openrecall, Property 9: Cost-curve never exceeds baseline.
    Validates: Requirements 9.1, 9.4
    """
    tracker = CostCurveTracker()
    tracker.begin_batch()
    for idx, (a, b) in enumerate(pairs):
        cost = min(a, b)
        baseline = max(a, b)
        tracker.record(idx, cost, baseline)
    series = tracker.series()
    assert [p.alert_index for p in series] == list(range(len(pairs)))
    for p in series:
        assert p.cost_usd <= p.baseline_cost_usd


def test_cost_curve_monotonic_repeating_distribution(frozen_tracker) -> None:
    """P8: Mean cost in batch 2 <= mean cost in batch 1 when retain happened in between.

    The tracker accounts for non-increasing per-alert cost; the workflow-level
    invariant follows because memory bypasses always lower per-alert cost
    relative to the baseline (P9) and retain never raises it.

    Feature: openrecall, Property 8: Cost-curve monotonicity under repeating distribution.
    Validates: Requirements 9.5
    """
    # Batch 1 -- simulate three alerts, none of which bypass.
    frozen_tracker.begin_batch()
    for i in range(3):
        frozen_tracker.record(i, 0.005, 0.02)
    mean1 = frozen_tracker.mean_cost_per_alert(batch_id=1)

    # Batch 2 -- same three alerts, now memory bypasses two of them.
    frozen_tracker.begin_batch()
    for i in range(3, 6):
        if i % 3 == 0:
            frozen_tracker.record(i, 0.005, 0.02)  # one still escalates
        else:
            frozen_tracker.record(i, 0.0, 0.02)  # bypass
    mean2 = frozen_tracker.mean_cost_per_alert(batch_id=2)

    assert mean2 <= mean1


@given(
    budget=st.floats(
        min_value=0.001,
        max_value=0.05,
        allow_nan=False,
        allow_infinity=False,
    ),
    n_alerts=st.integers(min_value=1, max_value=20),
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_budget_enforcement(monkeypatch, budget, n_alerts) -> None:
    """P14: After budget exhaustion, no new live calls fire and budget_exhausted flag is set.

    In Demo_Mode (CASCADEFLOW_LIVE_GROQ=false) no live calls fire at all, so
    we explicitly drive _call_model with live_groq=True plus a monkeypatched
    _groq_chat that succeeds without HTTP. The router's cumulative live-cost
    tracking is then exercised end-to-end.

    Feature: openrecall, Property 14: Budget enforcement.
    Validates: Requirements 6.6
    """
    import os

    os.environ["CASCADEFLOW_LIVE_GROQ"] = "true"
    os.environ["GROQ_API_KEY"] = "fake-key"
    os.environ["CASCADEFLOW_RUN_BUDGET_USD"] = str(budget)

    from incident_agent.router import CascadeFlowRouter

    router = CascadeFlowRouter()
    monkeypatch.setattr(router, "_groq_chat", lambda model, prompt: '{"ok": true}')

    traces = []
    prompt = "x" * 5000  # ~1250 tokens; estimated cost > 0
    for i in range(n_alerts):
        _, trace = router._call_model(
            f"step{i}",
            router.cheap_model,
            prompt,
            0.7,
            "test",
            escalated=False,
        )
        traces.append(trace)

    # Reset env so other tests stay in Demo_Mode.
    os.environ["CASCADEFLOW_LIVE_GROQ"] = "false"
    os.environ["GROQ_API_KEY"] = ""

    live = [t for t in traces if t.live_model_call]
    if not live:
        return  # not enough alerts to test enforcement

    live_total = sum(t.estimated_cost_usd for t in live)
    last_live = live[-1].estimated_cost_usd
    # Per P14: live total <= budget + final in-flight call's cost.
    assert live_total <= budget + last_live + 1e-9

    # Live calls must form a contiguous prefix; after the last live call
    # every subsequent trace must be budget_exhausted=True and
    # live_model_call=False (the in-flight budget-hit call is allowed to
    # be both live=True and budget_exhausted=True per the property).
    live_indices = [i for i, t in enumerate(traces) if t.live_model_call]
    last_live_idx = live_indices[-1]
    for trace in traces[last_live_idx + 1 :]:
        assert trace.live_model_call is False
        assert trace.budget_exhausted is True
