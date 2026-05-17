"""Confidence calibration tracker.

Tracks proposed vs actual triage decisions over time to measure how well
OpenRecall's auto-triage aligns with analyst overrides. Exposes metrics
for a calibration dashboard that SOC leads can use to decide when to
enable auto-close.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .models import TriageDecision, utc_now


ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_PATH = ROOT / "data" / "calibration_log.json"


class CalibrationEntry(BaseModel):
    """Single proposed-vs-actual record."""
    timestamp: str = Field(default_factory=utc_now)
    fingerprint_canonical: str = ""
    proposed_decision: TriageDecision | None = None
    proposed_confidence: float = 0.0
    actual_decision: TriageDecision | None = None
    was_overridden: bool = False
    memory_bypassed: bool = False
    latency_ms: float = 0.0


class CalibrationMetrics(BaseModel):
    """Aggregated calibration metrics for the dashboard."""
    total_decisions: int = 0
    total_overrides: int = 0
    accuracy_pct: float = 0.0
    override_rate_pct: float = 0.0
    # Per-decision breakdown
    per_decision: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # Confidence calibration buckets (0-20, 20-40, ..., 80-100)
    confidence_buckets: list[dict[str, Any]] = Field(default_factory=list)
    # Trend: last 7 days accuracy
    daily_accuracy: list[dict[str, Any]] = Field(default_factory=list)
    auto_close_eligible: bool = False
    auto_close_reason: str = ""


class CalibrationTracker:
    """Tracks proposed vs actual decisions for confidence calibration."""

    def __init__(self) -> None:
        self._entries: list[CalibrationEntry] = []
        self._load()

    def _load(self) -> None:
        if CALIBRATION_PATH.exists():
            try:
                raw = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
                self._entries = [CalibrationEntry(**e) for e in raw]
            except Exception:
                self._entries = []

    def _save(self) -> None:
        CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        CALIBRATION_PATH.write_text(
            json.dumps([e.model_dump() for e in self._entries], indent=2),
            encoding="utf-8",
        )

    def record_proposal(
        self,
        fingerprint_canonical: str,
        proposed_decision: TriageDecision | None,
        proposed_confidence: float,
        memory_bypassed: bool = False,
        latency_ms: float = 0.0,
    ) -> None:
        """Record a proposed decision (before analyst review)."""
        self._entries.append(
            CalibrationEntry(
                fingerprint_canonical=fingerprint_canonical,
                proposed_decision=proposed_decision,
                proposed_confidence=proposed_confidence,
                memory_bypassed=memory_bypassed,
                latency_ms=latency_ms,
            )
        )
        self._save()

    def record_override(
        self,
        fingerprint_canonical: str,
        actual_decision: TriageDecision,
    ) -> None:
        """Record an analyst override (after review)."""
        # Find the most recent proposal for this fingerprint
        for entry in reversed(self._entries):
            if entry.fingerprint_canonical == fingerprint_canonical and entry.actual_decision is None:
                entry.actual_decision = actual_decision
                entry.was_overridden = entry.proposed_decision != actual_decision
                break
        self._save()

    def record_acceptance(self, fingerprint_canonical: str) -> None:
        """Record that the analyst accepted the proposed decision."""
        for entry in reversed(self._entries):
            if entry.fingerprint_canonical == fingerprint_canonical and entry.actual_decision is None:
                entry.actual_decision = entry.proposed_decision
                entry.was_overridden = False
                break
        self._save()

    def metrics(self) -> CalibrationMetrics:
        """Compute calibration metrics."""
        resolved = [e for e in self._entries if e.actual_decision is not None]
        total = len(resolved)
        if total == 0:
            return CalibrationMetrics()

        correct = sum(1 for e in resolved if not e.was_overridden)
        overrides = sum(1 for e in resolved if e.was_overridden)

        # Per-decision breakdown
        per_decision: dict[str, dict[str, Any]] = {}
        for e in resolved:
            d = e.proposed_decision or "unknown"
            if d not in per_decision:
                per_decision[d] = {"proposed": 0, "correct": 0, "overridden": 0}
            per_decision[d]["proposed"] += 1
            if e.was_overridden:
                per_decision[d]["overridden"] += 1
            else:
                per_decision[d]["correct"] += 1

        # Confidence calibration buckets
        buckets: list[dict[str, Any]] = []
        for lo in range(0, 100, 20):
            hi = lo + 20
            in_bucket = [e for e in resolved if lo <= e.proposed_confidence * 100 < hi]
            if in_bucket:
                bucket_correct = sum(1 for e in in_bucket if not e.was_overridden)
                buckets.append({
                    "range": f"{lo}-{hi}%",
                    "count": len(in_bucket),
                    "accuracy_pct": round(bucket_correct / len(in_bucket) * 100, 1),
                })

        # Auto-close eligibility: >90% accuracy over 50+ decisions
        auto_close_eligible = total >= 50 and (correct / total) >= 0.90
        auto_close_reason = (
            f"Accuracy {correct/total*100:.1f}% over {total} decisions meets threshold"
            if auto_close_eligible
            else f"Need {'50+ decisions' if total < 50 else '>90% accuracy'} "
                 f"(currently {total} decisions, {correct/total*100:.1f}% accuracy)"
        )

        return CalibrationMetrics(
            total_decisions=total,
            total_overrides=overrides,
            accuracy_pct=round(correct / total * 100, 1),
            override_rate_pct=round(overrides / total * 100, 1),
            per_decision=per_decision,
            confidence_buckets=buckets,
            auto_close_eligible=auto_close_eligible,
            auto_close_reason=auto_close_reason,
        )
