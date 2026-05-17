"""Audit trace recorder.

Builds one AuditTraceEntry per RouteTrace so that the audit-completeness
invariant ``len(audit_trace) == len(route_trace)`` (Property 15) holds for
every analyzed alert. The recorder is purposely a static-method module so
it composes cleanly inside the workflow without state.
"""
from __future__ import annotations

from .models import (
    AlertFingerprint,
    AuditTraceEntry,
    CostCurvePoint,
    MemoryMatch,
    RouteTrace,
    TriageResult,
)


class AuditTraceRecorder:
    """Deterministic builder of AuditTraceEntry lists from RouteTrace lists."""

    @staticmethod
    def build(
        fingerprint: AlertFingerprint | None,
        matches: list[MemoryMatch],
        triage_result: TriageResult | None,
        route_trace: list[RouteTrace],
        cost_point: CostCurvePoint | None = None,
    ) -> list[AuditTraceEntry]:
        """Return one AuditTraceEntry per RouteTrace.

        ``fingerprint`` and ``cost_point`` are accepted for parity with the
        design's call signature; they are not required to populate the
        per-entry fields but enable future enrichment without a breaking
        change.
        """
        entries: list[AuditTraceEntry] = []
        memory_hit_count = len(matches)
        proposed_decision = triage_result.proposed_decision if triage_result else None
        escalation_reason = (
            triage_result.escalation_reason if triage_result else None
        )

        for trace in route_trace:
            entries.append(
                AuditTraceEntry(
                    step=trace.step,
                    model=trace.model,
                    route_reason=trace.route_reason,
                    memory_hit_count=memory_hit_count,
                    proposed_decision=proposed_decision,
                    escalation_reason=escalation_reason or None,
                    live_model_call=trace.live_model_call,
                    llm_skipped=trace.llm_skipped,
                    cost_usd=trace.estimated_cost_usd,
                    baseline_cost_usd=trace.strong_model_baseline_cost_usd,
                    savings_usd=trace.savings_vs_strong_usd,
                )
            )
        return entries
