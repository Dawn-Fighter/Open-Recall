"""Hypothesis strategies and fixtures for the OpenRecall property test suite.

Strategies (per design §Hypothesis Strategies, §Property Test Configuration):
- alert_fingerprint_strategy
- triage_decision_strategy
- memory_match_strategy(score_min, score_max, decision)
- strong_match_set_strategy(dominant_decision, n_total, agreement_count)
- raw_alert_strategy

Fixtures:
- frozen_router: CascadeFlowRouter with live_groq=False (Demo_Mode).
- frozen_memory: IncidentMemory subclass with in-memory store; no Hindsight,
  no local-JSON IO. Used by tests that need to control recall_by_fingerprint
  output deterministically.

CI Hypothesis profile registered with seed=20260101 and max_examples=100.
"""
from __future__ import annotations

import os
import string
from typing import Any

import pytest
from hypothesis import settings
from hypothesis import strategies as st

# Force fallback / Demo_Mode before any incident_agent module imports run.
os.environ.setdefault("CASCADEFLOW_LIVE_GROQ", "false")
os.environ.setdefault("HINDSIGHT_BASE_URL", "http://127.0.0.1:9")
os.environ.setdefault("HINDSIGHT_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")

from incident_agent.cost_curve import CostCurveTracker  # noqa: E402
from incident_agent.memory import IncidentMemory  # noqa: E402
from incident_agent.models import (  # noqa: E402
    AlertFingerprint,
    MemoryMatch,
    TriageDecision,
)
from incident_agent.router import CascadeFlowRouter  # noqa: E402

# Register a deterministic CI profile. Hypothesis settings does not accept a
# `seed` kwarg directly; deterministic ordering is handled by `derandomize`
# plus the `HYPOTHESIS_SEED` / `OPENRECALL_PBT_SEED` environment variable.
os.environ.setdefault(
    "HYPOTHESIS_SEED",
    os.environ.get("OPENRECALL_PBT_SEED", "20260101"),
)
settings.register_profile(
    "ci",
    max_examples=100,
    deadline=None,
    derandomize=True,
)
settings.register_profile(
    "default",
    max_examples=100,
    deadline=None,
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_token = st.text(
    alphabet=string.ascii_lowercase + string.digits + "-_",
    min_size=1,
    max_size=24,
)
_field_or_empty = st.one_of(st.just(""), _token)


@st.composite
def alert_fingerprint_strategy(draw) -> AlertFingerprint:
    """Generate AlertFingerprint values whose six fields use lowercase tokens.

    Tokens here intentionally exclude characters that would break the
    canonical-string parser (semicolons, equals, whitespace), so generated
    instances also satisfy the round-trip property without preconditions.
    """
    return AlertFingerprint(
        error_class=draw(_field_or_empty),
        service_role=draw(_field_or_empty),
        dependency_pattern=draw(_field_or_empty),
        signal_shape=draw(_field_or_empty),
        attack_pattern=draw(_field_or_empty),
        environment=draw(
            st.sampled_from(["", "production", "staging", "dev", "qa"])
        ),
    )


triage_decision_strategy: st.SearchStrategy[TriageDecision] = st.sampled_from(
    ["false_positive", "duplicate", "known_benign", "real", "escalated"]
)


@st.composite
def memory_match_strategy(
    draw,
    score_min: float = 0.0,
    score_max: float = 1.0,
    decision: TriageDecision | None = None,
) -> MemoryMatch:
    chosen = decision if decision is not None else draw(triage_decision_strategy)
    return MemoryMatch(
        title=draw(st.text(min_size=1, max_size=64)),
        content=draw(st.text(min_size=1, max_size=512)),
        score=draw(
            st.floats(
                min_value=score_min,
                max_value=score_max,
                allow_nan=False,
                allow_infinity=False,
            )
        ),
        source=draw(st.sampled_from(["hindsight", "local-json"])),
        metadata={
            "triage_decision": chosen,
            "dead_ends": draw(
                st.lists(st.text(min_size=1, max_size=32), max_size=4)
            ),
            "fingerprint_canonical": draw(_token),
        },
    )


@st.composite
def strong_match_set_strategy(
    draw,
    dominant_decision: TriageDecision,
    n_total: int,
    agreement_count: int,
) -> list[MemoryMatch]:
    """Build n_total Strong_Matches where exactly agreement_count carry dominant_decision.

    All scores drawn from [0.85, 1.0] so every match is a Strong_Match.
    """
    if agreement_count > n_total or agreement_count < 0 or n_total < 1:
        raise ValueError("invalid agreement_count / n_total")
    matches: list[MemoryMatch] = []
    for _ in range(agreement_count):
        matches.append(
            draw(
                memory_match_strategy(
                    score_min=0.85,
                    score_max=1.0,
                    decision=dominant_decision,
                )
            )
        )
    other_decisions = [
        d for d in (
            "false_positive",
            "duplicate",
            "known_benign",
            "real",
            "escalated",
        ) if d != dominant_decision
    ]
    for _ in range(n_total - agreement_count):
        matches.append(
            draw(
                memory_match_strategy(
                    score_min=0.85,
                    score_max=1.0,
                    decision=draw(st.sampled_from(other_decisions)),
                )
            )
        )
    return matches


raw_alert_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # exclude surrogates
    min_size=1,
    max_size=512,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def frozen_router() -> CascadeFlowRouter:
    """Return a CascadeFlowRouter wired for Demo_Mode (no live Groq, no key)."""
    os.environ["CASCADEFLOW_LIVE_GROQ"] = "false"
    os.environ["GROQ_API_KEY"] = ""
    router = CascadeFlowRouter()
    return router


class _DictBackedMemory(IncidentMemory):
    """In-memory IncidentMemory subclass with no Hindsight and no JSON IO.

    Use ``set_fingerprint_recall(fingerprint, matches)`` to control the
    return value of ``recall_by_fingerprint``. ``retain`` honors the
    in-process dedupe index from the parent class but does NOT write to
    disk.
    """

    def __init__(self) -> None:
        # Skip parent __init__ side effects (Hindsight init + local file IO).
        # We still want the dedupe index attribute and basic state.
        self.base_url = "memory://frozen"
        self.bank_id = "frozen"
        self.api_key = ""
        self.client = None
        self.status = "frozen in-memory test fixture"
        self.fallback_mode = True
        self._dedupe_index: set[tuple[str, str, str]] = set()
        self._canned_recall: dict[str, list[MemoryMatch]] = {}
        self._retained: list[dict[str, Any]] = []

    def set_fingerprint_recall(
        self, fingerprint: AlertFingerprint, matches: list[MemoryMatch]
    ) -> None:
        from incident_agent.fingerprint import format_fingerprint

        self._canned_recall[format_fingerprint(fingerprint)] = list(matches)

    def recall(self, query: str, limit: int = 5):  # type: ignore[override]
        return []

    def recall_by_fingerprint(
        self, fingerprint: AlertFingerprint, limit: int = 5
    ):  # type: ignore[override]
        from incident_agent.fingerprint import format_fingerprint

        canned = self._canned_recall.get(format_fingerprint(fingerprint))
        if canned is None:
            return []
        return list(canned)[:limit]

    def recall_by_decision(
        self,
        fingerprint: AlertFingerprint,
        decision: TriageDecision,
        limit: int = 5,
    ):  # type: ignore[override]
        matches = self.recall_by_fingerprint(fingerprint, limit=max(limit * 2, limit + 5))
        filtered = [m for m in matches if m.metadata.get("triage_decision") == decision]
        return filtered[:limit]

    def retain(  # type: ignore[override]
        self,
        content: str,
        context: str = "incident memory",
        metadata: dict[str, Any] | None = None,
        *,
        fingerprint: AlertFingerprint | None = None,
        decision: TriageDecision | None = None,
        dead_ends: list[str] | None = None,
        analyst_id: str | None = None,
        business_impact_minutes: int | None = None,
    ) -> str:
        from hashlib import sha256

        from incident_agent.fingerprint import format_fingerprint

        canonical = format_fingerprint(fingerprint) if fingerprint is not None else ""
        decision_key = decision or ""
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        dedupe_key = (canonical, decision_key, content_hash)
        if dedupe_key in self._dedupe_index:
            return "skipped duplicate"
        self._dedupe_index.add(dedupe_key)
        new_metadata: dict[str, Any] = {
            "fingerprint_canonical": canonical,
            "triage_decision": decision,
            "dead_ends": list(dead_ends) if dead_ends else [],
            "analyst_id": analyst_id,
            "business_impact_minutes": business_impact_minutes,
        }
        merged = {**(metadata or {}), **new_metadata}
        record = {
            "title": context,
            "content": content,
            "metadata": merged,
        }
        self._retained.append(record)
        # Surface the just-retained record in subsequent recall_by_fingerprint
        # so Property 13 (recall-then-retain consistency) holds.
        if fingerprint is not None:
            existing = self._canned_recall.setdefault(canonical, [])
            existing.insert(
                0,
                MemoryMatch(
                    title=context,
                    content=content,
                    score=0.95,
                    source="frozen-in-memory",
                    metadata=merged,
                ),
            )
        return "retained in frozen memory"

    def reflect(self, query: str, matches):  # type: ignore[override]
        return "reflection (frozen)"


@pytest.fixture
def frozen_memory() -> _DictBackedMemory:
    return _DictBackedMemory()


@pytest.fixture
def frozen_tracker() -> CostCurveTracker:
    return CostCurveTracker()
