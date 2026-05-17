from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


IncidentType = Literal["SRE", "Security", "Hybrid"]

TriageDecision = Literal[
    "false_positive",
    "duplicate",
    "known_benign",
    "real",
    "escalated",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentObject(BaseModel):
    service: str = "unknown-service"
    environment: str = "unknown"
    severity: str = "SEV-3"
    timestamp: str = Field(default_factory=utc_now)
    error_type: str = "unknown"
    affected_dependency: str | None = None
    suspected_recent_change: str | None = None
    security_relevance: str = "none"
    raw_alert: str = ""
    lifecycle_phase: str = "detection/analysis"


class MemoryMatch(BaseModel):
    title: str
    content: str
    score: float = 0.0
    source: str = "hindsight"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Alert(BaseModel):
    raw_alert: str
    title: str | None = None
    submitted_at: str = Field(default_factory=utc_now)


class AlertFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    error_class: str = ""
    service_role: str = ""
    dependency_pattern: str = ""
    signal_shape: str = ""
    attack_pattern: str = ""
    environment: str = ""


class TriageResult(BaseModel):
    proposed_decision: TriageDecision
    triage_confidence: float = 0.0
    supporting_matches: list[MemoryMatch] = Field(default_factory=list)
    consistent_decision_count: int = 0
    requires_human_approval: bool = False
    escalation_reason: str = ""


class CostCurvePoint(BaseModel):
    alert_index: int
    cost_usd: float
    baseline_cost_usd: float
    cumulative_cost_usd: float
    cumulative_baseline_usd: float
    batch_id: int = 0


class AuditTraceEntry(BaseModel):
    step: str
    model: str
    route_reason: str
    memory_hit_count: int
    proposed_decision: TriageDecision | None = None
    escalation_reason: str | None = None
    live_model_call: bool
    llm_skipped: bool = False
    cost_usd: float
    baseline_cost_usd: float
    savings_usd: float


class RouteTrace(BaseModel):
    step: str
    model: str
    provider: str = "groq"
    route_reason: str
    confidence: float
    latency_ms: float
    estimated_cost_usd: float
    strong_model_baseline_cost_usd: float = 0.0
    savings_vs_strong_usd: float = 0.0
    escalated: bool = False
    cascadeflow_enabled: bool = False
    live_model_call: bool = False
    model_error: str | None = None
    budget_remaining_usd: float | None = None
    triage_decision_proposed: TriageDecision | None = None
    memory_match_score: float | None = None
    decision_consistency: float | None = None
    llm_skipped: bool = False
    budget_exhausted: bool = False


class AnalysisResult(BaseModel):
    incident: IncidentObject
    incident_type: IncidentType
    impact_level: str
    blast_radius_guess: str
    evidence_to_preserve: list[str]
    memory_matches: list[MemoryMatch]
    memory_reflection: str
    likely_root_causes: list[dict[str, Any]]
    verification_commands: list[str]
    remediation_suggestions: list[str]
    containment_notes: list[str]
    roles: dict[str, str]
    timeline_notes: list[str]
    postmortem_action_items: list[str]
    route_trace: list[RouteTrace]
    hindsight_status: str
    fallback_mode: bool = False
    alert_fingerprint: AlertFingerprint | None = None
    triage_result: TriageResult | None = None
    cost_curve_point: CostCurvePoint | None = None
    dead_ends: list[str] = Field(default_factory=list)
    audit_trace: list[AuditTraceEntry] = Field(default_factory=list)
