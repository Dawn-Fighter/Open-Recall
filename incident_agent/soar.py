"""SOAR enrichment adapter.

Provides webhook-compatible endpoints for Splunk SOAR, Microsoft Sentinel,
and generic SIEM/SOAR platforms. Transforms incoming webhook payloads into
OpenRecall's internal alert format and returns enrichment data (memory matches,
proposed triage decision, dead ends) that the SOAR can attach to the alert
ticket inline.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .models import AlertFingerprint, TriageDecision, utc_now


# ── Webhook payload models ──────────────────────────────────────────────────

class SplunkSOARWebhook(BaseModel):
    """Splunk SOAR (Phantom) webhook payload."""
    container_id: int | None = None
    container_name: str = ""
    severity: str = "medium"
    description: str = ""
    source_data_identifier: str = ""
    raw_event: str = ""
    label: str = "alert"
    tags: list[str] = Field(default_factory=list)

    def to_raw_alert(self) -> str:
        parts = [self.description or self.container_name]
        if self.raw_event:
            parts.append(self.raw_event)
        if self.severity:
            parts.append(f"Severity: {self.severity}")
        return " ".join(p for p in parts if p)


class SentinelWebhook(BaseModel):
    """Microsoft Sentinel webhook payload (simplified)."""
    incident_id: str = ""
    title: str = ""
    description: str = ""
    severity: Literal["High", "Medium", "Low", "Informational"] = "Medium"
    status: str = "New"
    classification: str = ""
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    tactics: list[str] = Field(default_factory=list)

    def to_raw_alert(self) -> str:
        parts = [f"{self.severity} {self.title}"]
        if self.description:
            parts.append(self.description)
        if self.tactics:
            parts.append(f"MITRE tactics: {', '.join(self.tactics)}")
        for alert in self.alerts[:3]:
            if alert.get("description"):
                parts.append(alert["description"])
        return " ".join(parts)


class GenericWebhook(BaseModel):
    """Generic SIEM/SOAR webhook — accepts any JSON with a text field."""
    alert_text: str = ""
    title: str = ""
    severity: str = ""
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_raw_alert(self) -> str:
        parts = []
        if self.severity:
            parts.append(self.severity)
        if self.title:
            parts.append(self.title)
        if self.alert_text:
            parts.append(self.alert_text)
        return " ".join(parts) or "unknown alert"


# ── Enrichment response ─────────────────────────────────────────────────────

class SOAREnrichmentResponse(BaseModel):
    """Enrichment payload returned to the SOAR platform."""
    status: str = "enriched"
    proposed_decision: TriageDecision | None = None
    confidence: float = 0.0
    requires_human_approval: bool = True
    memory_bypassed: bool = False
    memory_match_count: int = 0
    top_match_score: float = 0.0
    top_match_decision: str | None = None
    dead_ends: list[str] = Field(default_factory=list)
    fingerprint: dict[str, str] = Field(default_factory=dict)
    escalation_reason: str = ""
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    enriched_at: str = Field(default_factory=utc_now)
    # For SOAR action chaining
    recommended_action: str = ""
    auto_closeable: bool = False
