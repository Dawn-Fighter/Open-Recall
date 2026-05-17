"""Property tests covering the full workflow.

- P15: Audit trace completeness -- len(audit_trace) == len(route_trace).
- queue ordering: analyze_queue preserves submission order.
- Demo_Mode end-to-end: every alert produces fingerprint, triage, cost point, audit.
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from incident_agent.cost_curve import CostCurveTracker
from incident_agent.models import Alert
from incident_agent.workflow import IncidentWorkflow

from .conftest import raw_alert_strategy


@given(raw_alert=raw_alert_strategy)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_audit_trace_completeness(frozen_router, raw_alert) -> None:
    """P15: len(audit_trace) == len(route_trace) and required fields populated.

    Feature: openrecall, Property 15: Audit trace completeness.
    Validates: Requirements 10.1, 10.3
    """
    from .conftest import _DictBackedMemory

    if not raw_alert.strip():
        return  # invalid alerts go through analyze_queue's invalid-result path
    workflow = IncidentWorkflow(
        _DictBackedMemory(), frozen_router, CostCurveTracker()
    )
    result = workflow.analyze(raw_alert)
    assert len(result.audit_trace) == len(result.route_trace)
    for entry in result.audit_trace:
        assert entry.step
        assert entry.model
        assert entry.route_reason is not None
        assert entry.live_model_call is False  # Demo_Mode
        assert entry.cost_usd is not None
        assert entry.baseline_cost_usd is not None


@given(
    alerts=st.lists(
        st.builds(Alert, raw_alert=st.text(min_size=1, max_size=200)),
        min_size=1,
        max_size=10,
    )
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_analyze_queue_preserves_order(frozen_router, alerts) -> None:
    """analyze_queue returns one result per alert, in submission order.

    The workflow strips raw_alert before analyzing, so an entry whose
    raw_alert is whitespace-only routes to the invalid-alert path.

    Feature: openrecall, queue ordering: analyze_queue preserves submission order.
    Validates: Requirements 2.1, 2.4
    """
    from .conftest import _DictBackedMemory

    workflow = IncidentWorkflow(
        _DictBackedMemory(), frozen_router, CostCurveTracker()
    )
    results = workflow.analyze_queue(alerts)
    assert len(results) == len(alerts)
    for src, res in zip(alerts, results):
        stripped = (src.raw_alert or "").strip()
        if not stripped:
            assert res.incident.error_type == "invalid_alert"
        else:
            assert res.incident.raw_alert == stripped


@given(raw_alert=st.text(min_size=1, max_size=200))
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_demo_mode_end_to_end(frozen_router, raw_alert) -> None:
    """Demo_Mode end-to-end: fingerprint, triage, cost_point, audit_trace populated; no live calls.

    Feature: openrecall, Demo_Mode end-to-end: every alert produces fingerprint, triage, cost_point, audit_trace.
    Validates: Requirements 3.3, 11.6, 14.3
    """
    from .conftest import _DictBackedMemory

    if not raw_alert.strip():
        return
    workflow = IncidentWorkflow(
        _DictBackedMemory(), frozen_router, CostCurveTracker()
    )
    result = workflow.analyze(raw_alert)
    assert result.alert_fingerprint is not None
    assert result.triage_result is not None
    assert result.cost_curve_point is not None
    assert len(result.audit_trace) >= 1
    for trace in result.route_trace:
        assert trace.live_model_call is False
