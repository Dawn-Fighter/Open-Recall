"""Property tests covering the memory adapter.

- P7: Idempotent retain.
- P10: Fallback-vs-cloud structural parity (AnalysisResult shape).
- P13: Recall-then-retain consistency (write-then-read).
"""
from __future__ import annotations

from hashlib import sha256

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from incident_agent.cost_curve import CostCurveTracker
from incident_agent.fingerprint import format_fingerprint
from incident_agent.models import AnalysisResult
from incident_agent.workflow import IncidentWorkflow

from .conftest import (
    _DictBackedMemory,
    alert_fingerprint_strategy,
    raw_alert_strategy,
    triage_decision_strategy,
)


@given(
    fp=alert_fingerprint_strategy(),
    decision=triage_decision_strategy,
    content=st.text(min_size=1, max_size=200),
    dead_ends=st.lists(st.text(min_size=1, max_size=32), max_size=4),
)
@settings(
    max_examples=100,
    deadline=None,
)
def test_retain_idempotent(fp, decision, content, dead_ends) -> None:
    """P7: Calling retain twice with the same key produces exactly one record.

    Feature: openrecall, Property 7: Idempotent retain.
    Validates: Requirements 8.3
    """
    memory = _DictBackedMemory()
    s1 = memory.retain(
        content,
        fingerprint=fp,
        decision=decision,
        dead_ends=list(dead_ends),
    )
    s2 = memory.retain(
        content,
        fingerprint=fp,
        decision=decision,
        dead_ends=list(dead_ends),
    )
    canonical = format_fingerprint(fp)
    digest = sha256(content.encode("utf-8")).hexdigest()
    expected_key = (canonical, decision, digest)
    assert expected_key in memory._dedupe_index
    matching = [
        r
        for r in memory._retained
        if r["metadata"].get("fingerprint_canonical") == canonical
        and r["metadata"].get("triage_decision") == decision
        and sha256(str(r["content"]).encode("utf-8")).hexdigest() == digest
    ]
    assert len(matching) == 1
    assert s1 != "skipped duplicate"
    assert s2 == "skipped duplicate"


@given(raw_alert=raw_alert_strategy)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_fallback_vs_cloud_structural_parity(frozen_router, raw_alert) -> None:
    """P10: Demo_Mode AnalysisResult shape is identical across memory backends.

    Compares two IncidentWorkflow runs: one with frozen_memory (no Hindsight,
    no local IO) and one with the default IncidentMemory (HINDSIGHT_BASE_URL
    points at 127.0.0.1:9 so it lands on the local-JSON fallback path). The
    Pydantic class, field name set, and nested model classes must agree.

    Feature: openrecall, Property 10: Fallback-vs-cloud structural parity.
    Validates: Requirements 11.4
    """
    from incident_agent.memory import IncidentMemory

    if not raw_alert.strip():
        return  # invalid alert paths short-circuit; skip vacuous comparison

    workflow_frozen = IncidentWorkflow(
        _DictBackedMemory(), frozen_router, CostCurveTracker()
    )
    workflow_local = IncidentWorkflow(
        IncidentMemory(), frozen_router, CostCurveTracker()
    )

    r_frozen = workflow_frozen.analyze(raw_alert)
    r_local = workflow_local.analyze(raw_alert)

    assert isinstance(r_frozen, AnalysisResult)
    assert isinstance(r_local, AnalysisResult)
    assert set(r_frozen.model_fields.keys()) == set(r_local.model_fields.keys())
    # Nested model parity: alert_fingerprint, triage_result, cost_curve_point
    if (
        r_frozen.alert_fingerprint is not None
        and r_local.alert_fingerprint is not None
    ):
        assert type(r_frozen.alert_fingerprint) is type(r_local.alert_fingerprint)
    if r_frozen.triage_result is not None and r_local.triage_result is not None:
        assert type(r_frozen.triage_result) is type(r_local.triage_result)
    if (
        r_frozen.cost_curve_point is not None
        and r_local.cost_curve_point is not None
    ):
        assert type(r_frozen.cost_curve_point) is type(r_local.cost_curve_point)


@given(
    fp=alert_fingerprint_strategy(),
    decision=triage_decision_strategy,
    content=st.text(min_size=1, max_size=200),
    dead_ends=st.lists(st.text(min_size=1, max_size=32), max_size=4),
)
@settings(
    max_examples=100,
    deadline=None,
)
def test_recall_then_retain_consistency(
    fp, decision, content, dead_ends
) -> None:
    """P13: After retain, the next recall_by_fingerprint surfaces the new metadata.

    Feature: openrecall, Property 13: Recall-then-retain consistency.
    Validates: Requirements 7.4, 7.5, 8.5
    """
    memory = _DictBackedMemory()
    memory.retain(
        content,
        fingerprint=fp,
        decision=decision,
        dead_ends=list(dead_ends),
    )
    matches = memory.recall_by_fingerprint(fp, limit=5)
    assert len(matches) >= 1
    found = any(
        m.metadata.get("triage_decision") == decision
        and all(d in (m.metadata.get("dead_ends") or []) for d in dead_ends)
        for m in matches
    )
    assert found
