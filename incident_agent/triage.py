"""Auto-triage decision engine.

Converts an AlertFingerprint plus recalled MemoryMatch list into a TriageResult
under hard, auditable thresholds. Designed so a single conjunction expresses
the strong-model bypass invariant for property tests.
"""
from __future__ import annotations

from collections import Counter
from typing import Final

from .models import (
    AlertFingerprint,
    MemoryMatch,
    TriageDecision,
    TriageResult,
)


STRONG_MATCH_THRESHOLD: Final[float] = 0.85
DECISION_CONSISTENCY_THRESHOLD: Final[float] = 0.9
BYPASS_CONFIDENCE_THRESHOLD: Final[float] = 0.85


class TriageEngine:
    """Hard-threshold triage decision engine.

    The thresholds STRONG_MATCH_THRESHOLD, DECISION_CONSISTENCY_THRESHOLD, and
    BYPASS_CONFIDENCE_THRESHOLD are module constants so property tests and
    future tuning live in one place.
    """

    def triage(
        self,
        fingerprint: AlertFingerprint,
        matches: list[MemoryMatch],
    ) -> TriageResult:
        """Convert (fingerprint, matches) into a TriageResult.

        Decision rules (matching design §Triage Decision Flowchart):

        1. Filter to Strong_Matches (score >= STRONG_MATCH_THRESHOLD).
        2. If no Strong_Match → escalated (Property 11).
        3. If fingerprint.attack_pattern is non-empty AND no Strong_Match
           → escalated (Property 12). Covered by step 2 path; this is
           documented as the security-novel rule.
        4. If Strong_Matches lack stored decisions → escalated.
        5. If Decision_Consistency < DECISION_CONSISTENCY_THRESHOLD
           → escalated.
        6. Otherwise propose the dominant decision with
           requires_human_approval=True.
        7. Security-novel kill switch: when fingerprint.attack_pattern is
           non-empty AND a strong, consistent prior decision exists, still
           propose the dominant decision but flag it requires_human_approval
           with escalation_reason "security-novel: human approval required".
        """
        strong = [m for m in matches if m.score >= STRONG_MATCH_THRESHOLD]
        if not strong:
            best_score = max((m.score for m in matches), default=0.0)
            return TriageResult(
                proposed_decision="escalated",
                triage_confidence=best_score,
                supporting_matches=[],
                consistent_decision_count=0,
                requires_human_approval=False,
                escalation_reason="no Strong_Match in memory",
            )

        dominant, consistency, n_dominant = self.decision_consistency(strong)
        n_strong = len(strong)

        if dominant is None:
            return TriageResult(
                proposed_decision="escalated",
                triage_confidence=sum(m.score for m in strong) / n_strong,
                supporting_matches=strong,
                consistent_decision_count=0,
                requires_human_approval=False,
                escalation_reason="strong matches lack stored decisions",
            )

        if consistency < DECISION_CONSISTENCY_THRESHOLD:
            return TriageResult(
                proposed_decision="escalated",
                triage_confidence=consistency,
                supporting_matches=strong,
                consistent_decision_count=n_dominant,
                requires_human_approval=False,
                escalation_reason="decision consistency below threshold",
            )

        confidence_value = self.confidence(consistency, n_strong)

        if fingerprint.attack_pattern:
            return TriageResult(
                proposed_decision=dominant,
                triage_confidence=confidence_value,
                supporting_matches=strong,
                consistent_decision_count=n_dominant,
                requires_human_approval=True,
                escalation_reason="security-novel: human approval required",
            )

        return TriageResult(
            proposed_decision=dominant,
            triage_confidence=confidence_value,
            supporting_matches=strong,
            consistent_decision_count=n_dominant,
            requires_human_approval=True,
            escalation_reason="memory consistent",
        )

    @staticmethod
    def decision_consistency(
        strong_matches: list[MemoryMatch],
    ) -> tuple[TriageDecision | None, float, int]:
        """Return (dominant_decision, consistency_in_[0,1], n_dominant).

        Strong matches are sorted by score descending so Counter tie-breaks
        deterministically toward the higher-scoring match.
        """
        if not strong_matches:
            return (None, 0.0, 0)
        sorted_matches = sorted(strong_matches, key=lambda m: m.score, reverse=True)
        decisions = [m.metadata.get("triage_decision") for m in sorted_matches]
        counter = Counter(d for d in decisions if d)
        if not counter:
            return (None, 0.0, 0)
        dominant, n_dominant = counter.most_common(1)[0]
        consistency = n_dominant / len(sorted_matches)
        return (dominant, consistency, n_dominant)

    @staticmethod
    def confidence(consistency: float, n_strong: int) -> float:
        """Clamp the proposal confidence to satisfy Property 5.

        Property 5: c * (n / (n + 1)) <= triage_confidence <= c
        Pick a value monotonic in n that respects the bound:
            min(c, max(c * n / (n + 1), c * (1 - 1 / (n + 2))))
        """
        if n_strong <= 0:
            return 0.0
        c = max(0.0, min(1.0, consistency))
        lower = c * (n_strong / (n_strong + 1))
        candidate = c * (1.0 - 1.0 / (n_strong + 2))
        # Clamp candidate inside [lower, c]
        return min(c, max(lower, candidate))
