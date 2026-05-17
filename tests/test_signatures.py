"""Signature and shape checks for the OpenRecall public API."""
from __future__ import annotations

import inspect

from incident_agent.models import (
    Alert,
    AlertFingerprint,
    AnalysisResult,
    AuditTraceEntry,
    CostCurvePoint,
    IncidentObject,
    MemoryMatch,
    RouteTrace,
    TriageDecision,
    TriageResult,
)
from incident_agent.workflow import IncidentWorkflow


def test_analyze_signature_preserved() -> None:
    """IncidentWorkflow.analyze must keep its (self, raw_alert: str) -> AnalysisResult signature."""
    sig = inspect.signature(IncidentWorkflow.analyze)
    params = list(sig.parameters.values())
    assert [p.name for p in params] == ["self", "raw_alert"]
    annotations = inspect.get_annotations(IncidentWorkflow.analyze, eval_str=True)
    assert annotations.get("raw_alert") is str
    assert annotations.get("return") is AnalysisResult


def test_analysis_result_exposes_new_optional_fields() -> None:
    """AnalysisResult must be a strict superset adding the OpenRecall fields with safe defaults."""
    fields = AnalysisResult.model_fields
    for name in (
        "alert_fingerprint",
        "triage_result",
        "cost_curve_point",
        "dead_ends",
        "audit_trace",
    ):
        assert name in fields, f"missing new AnalysisResult field: {name}"
    # Defaults must not require explicit init for backward compat
    instance = AnalysisResult(
        incident=IncidentObject(),
        incident_type="SRE",
        impact_level="low",
        blast_radius_guess="bounded",
        evidence_to_preserve=[],
        memory_matches=[],
        memory_reflection="",
        likely_root_causes=[],
        verification_commands=[],
        remediation_suggestions=[],
        containment_notes=[],
        roles={},
        timeline_notes=[],
        postmortem_action_items=[],
        route_trace=[],
        hindsight_status="ok",
    )
    assert instance.alert_fingerprint is None
    assert instance.triage_result is None
    assert instance.cost_curve_point is None
    assert instance.dead_ends == []
    assert instance.audit_trace == []


def test_alert_fingerprint_is_frozen() -> None:
    """AlertFingerprint must be hashable (used as a dedupe key)."""
    fp = AlertFingerprint(error_class="crashloop", service_role="checkout-service")
    # Hashable check: should not raise
    hash(fp)


def test_triage_decision_literal_values() -> None:
    """TriageDecision must include the five expected values."""
    # Round-trip through Pydantic to ensure the Literal is honored.
    for value in ("false_positive", "duplicate", "known_benign", "real", "escalated"):
        result = TriageResult(proposed_decision=value)  # type: ignore[arg-type]
        assert result.proposed_decision == value
