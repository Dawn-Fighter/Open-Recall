from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


IncidentType = Literal["SRE", "Security", "Hybrid"]


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
