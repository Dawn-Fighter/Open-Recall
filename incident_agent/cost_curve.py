"""Cost curve tracker.

Aggregates per-alert cost vs strong-model-only baseline across analyzed
alerts in the current API process. The tracker is intentionally a simple
in-memory append-only series so Property 9 (cost <= baseline) and
Property 8 (mean cost decreases as memory grows) are easy to assert.
"""
from __future__ import annotations

from .models import CostCurvePoint


class CostCurveTracker:
    """In-memory time-ordered series of CostCurvePoint values.

    The FastAPI backend (``api.py``) constructs a single tracker as a
    module-level singleton so cumulative state persists across requests
    within a process lifetime. Call ``reset()`` to clear the series
    without re-creating the instance.
    """

    def __init__(self) -> None:
        self._points: list[CostCurvePoint] = []
        self._cum_cost: float = 0.0
        self._cum_baseline: float = 0.0
        self._batch_id: int = 0

    # 6.6
    def begin_batch(self) -> int:
        """Mark a new batch boundary. Returns the new batch id."""
        self._batch_id += 1
        return self._batch_id

    def reset(self) -> None:
        """Re-initialize the tracker state without re-creating the instance.

        Useful when the FastAPI process holds a long-lived tracker and an
        operator wants to clear the cumulative cost series mid-session
        (for example, between demo recordings).
        """
        self._points.clear()
        self._cum_cost = 0.0
        self._cum_baseline = 0.0
        self._batch_id = 0

    # 6.2
    def record(
        self,
        alert_index: int,
        cost_usd: float,
        baseline_cost_usd: float,
    ) -> CostCurvePoint:
        """Append one CostCurvePoint and return it.

        ``cost_usd`` may be 0.0 on a memory-bypass; ``baseline_cost_usd``
        must be preserved from the strong-model estimate so Property 9
        (cost <= baseline) is well-defined and the savings band renders.
        """
        self._cum_cost += cost_usd
        self._cum_baseline += baseline_cost_usd
        point = CostCurvePoint(
            alert_index=alert_index,
            cost_usd=cost_usd,
            baseline_cost_usd=baseline_cost_usd,
            cumulative_cost_usd=self._cum_cost,
            cumulative_baseline_usd=self._cum_baseline,
            batch_id=self._batch_id,
        )
        self._points.append(point)
        return point

    # 6.3
    def series(self) -> list[CostCurvePoint]:
        """Return a copy of the recorded series in submission order."""
        return list(self._points)

    # 6.4
    def mean_cost_per_alert(self, batch_id: int | None = None) -> float:
        """Return mean cost-per-alert across the series or one batch."""
        if batch_id is None:
            points = self._points
        else:
            points = [p for p in self._points if p.batch_id == batch_id]
        if not points:
            return 0.0
        return sum(p.cost_usd for p in points) / len(points)

    # 6.5
    def savings(self) -> tuple[float, float, float]:
        """Return (total_cost, total_baseline, percent_saved)."""
        if self._cum_baseline == 0.0:
            return (self._cum_cost, self._cum_baseline, 0.0)
        pct = 100.0 * (self._cum_baseline - self._cum_cost) / self._cum_baseline
        return (self._cum_cost, self._cum_baseline, pct)

    # Convenience for tests / introspection
    @property
    def current_batch_id(self) -> int:
        return self._batch_id
