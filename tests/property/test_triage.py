"""Property tests covering the triage engine and the strong-model bypass invariant.

Properties:
- P3: Triage proposal determinism for fixed inputs.
- P4: triage_confidence in [0, 1].
- P5: triage_confidence reflects historical agreement.
- P6: Strong-model bypass invariant (no live strong-model call when memory consistent).
- P11: No Strong_Match implies escalated.
- P12: Security-novel bypass refusal (attack_pattern + no Strong_Match -> escalated).
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from incident_agent.cost_curve import CostCurveTracker
from incident_agent.fingerprint import regex_fallback
from incident_agent.models import AlertFingerprint
from incident_agent.triage import (
    BYPASS_CONFIDENCE_THRESHOLD,
    DECISION_CONSISTENCY_THRESHOLD,
    STRONG_MATCH_THRESHOLD,
    TriageEngine,
)
from incident_agent.workflow import IncidentWorkflow

from .conftest import (
    alert_fingerprint_strategy,
    memory_match_strategy,
    strong_match_set_strategy,
    triage_decision_strategy,
)


@given(
    fp=alert_fingerprint_strategy(),
    matches=st.lists(memory_match_strategy(), max_size=12),
)
@settings(max_examples=100, deadline=None)
def test_triage_proposal_determinism(fp, matches) -> None:
    """P3: triage(fp, matches) is deterministic for fixed inputs.

    Feature: openrecall, Property 3: Triage proposal determinism.
    Validates: Requirements 5.1, 5.2, 5.3
    """
    engine = TriageEngine()
    r1 = engine.triage(fp, list(matches))
    r2 = engine.triage(fp, list(matches))
    assert r1.proposed_decision == r2.proposed_decision
    assert r1.triage_confidence == r2.triage_confidence
    assert r1.requires_human_approval == r2.requires_human_approval


@given(
    fp=alert_fingerprint_strategy(),
    matches=st.lists(memory_match_strategy(), max_size=12),
)
@settings(max_examples=100, deadline=None)
def test_triage_confidence_bounds(fp, matches) -> None:
    """P4: triage_confidence is bounded to [0, 1].

    Feature: openrecall, Property 4: Triage confidence bounds.
    Validates: Requirements 5.2
    """
    result = TriageEngine().triage(fp, list(matches))
    assert 0.0 <= result.triage_confidence <= 1.0


@given(
    dominant=triage_decision_strategy,
    n_total=st.integers(min_value=2, max_value=10),
    data=st.data(),
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_confidence_reflects_history(dominant, n_total, data) -> None:
    """P5: c * (n / (n + 1)) <= triage_confidence <= c, where c = consistency.

    Feature: openrecall, Property 5: Confidence reflects history.
    Validates: Requirements 5.2, 5.5
    """
    matches = data.draw(
        strong_match_set_strategy(
            dominant_decision=dominant,
            n_total=n_total,
            agreement_count=n_total,  # full agreement -> consistency = 1.0
        )
    )
    fp = AlertFingerprint(error_class="test", environment="production")
    result = TriageEngine().triage(fp, matches)
    consistency = 1.0
    if (
        consistency >= DECISION_CONSISTENCY_THRESHOLD
        and result.proposed_decision == dominant
    ):
        # Property 5 bound: c * (n / (n+1)) <= triage_confidence <= c
        assert result.triage_confidence <= consistency + 1e-9
        assert (
            result.triage_confidence
            >= consistency * (n_total / (n_total + 1)) - 1e-9
        )


@given(
    dominant=st.sampled_from(["false_positive", "duplicate", "known_benign"]),
    n_total=st.integers(min_value=6, max_value=10),
    data=st.data(),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
    ],
)
def test_strong_model_bypass_invariant(
    dominant, n_total, data, frozen_router
) -> None:
    """P6: no live strong-model call when memory is consistent and attack_pattern is empty.

    Constructs strong consistent matches via strong_match_set_strategy, seeds
    them on a fresh _DictBackedMemory under the fingerprint that the regex
    extractor will derive from a known crashloop alert, then runs
    IncidentWorkflow.analyze. Asserts:
      - zero RouteTrace entries with model == "openai/gpt-oss-120b"
        AND live_model_call == True
      - exactly one RouteTrace entry with model == "memory-bypass"
        AND llm_skipped == True

    n_total >= 6 ensures triage_confidence >= 0.85 (BYPASS_CONFIDENCE_THRESHOLD)
    when consistency = 1.0; see TriageEngine.confidence.

    Feature: openrecall, Property 6: Strong-model bypass invariant.
    Validates: Requirements 6.1, 6.4, 6.5
    """
    from .conftest import _DictBackedMemory

    matches = data.draw(
        strong_match_set_strategy(
            dominant_decision=dominant,
            n_total=n_total,
            agreement_count=n_total,
        )
    )
    raw_alert = (
        "SEV-2 prod checkout-service CrashLoopBackOff after deploy. "
        "ConfigMap cleanup removed env var. crashloop on /checkout."
    )
    # Use the regex extractor to compute the fingerprint the workflow will see,
    # so the canned recall key matches exactly.
    fp = regex_fallback(raw_alert)
    assert not fp.attack_pattern  # precondition for the bypass invariant
    memory = _DictBackedMemory()
    memory.set_fingerprint_recall(fp, matches)

    tracker = CostCurveTracker()
    workflow = IncidentWorkflow(memory, frozen_router, tracker)
    result = workflow.analyze(raw_alert)

    strong_live = [
        t
        for t in result.route_trace
        if t.model == "openai/gpt-oss-120b" and t.live_model_call is True
    ]
    bypass = [
        t
        for t in result.route_trace
        if t.model == "memory-bypass" and t.llm_skipped is True
    ]
    assert len(strong_live) == 0
    assert len(bypass) == 1


@given(
    fp=alert_fingerprint_strategy(),
    matches=st.lists(
        memory_match_strategy(score_min=0.0, score_max=0.84),
        max_size=10,
    ),
)
@settings(max_examples=100, deadline=None)
def test_no_strong_match_escalates(fp, matches) -> None:
    """P11: No Strong_Match implies proposed_decision == 'escalated'.

    Every score is strictly below STRONG_MATCH_THRESHOLD (0.85) so the
    Strong_Match filter is empty.

    Feature: openrecall, Property 11: No-Strong-Match implies escalation.
    Validates: Requirements 5.4
    """
    # Sanity: scores are all below threshold.
    assert all(m.score < STRONG_MATCH_THRESHOLD for m in matches)
    result = TriageEngine().triage(fp, list(matches))
    assert result.proposed_decision == "escalated"


@given(
    fp_attack=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=20
    ),
    matches=st.lists(
        memory_match_strategy(score_min=0.0, score_max=0.84),
        max_size=10,
    ),
)
@settings(max_examples=100, deadline=None)
def test_security_novel_escalates(fp_attack, matches) -> None:
    """P12: attack_pattern non-empty AND no Strong_Match -> escalated.

    Feature: openrecall, Property 12: Security-novel bypass refusal.
    Validates: Requirements 5.6
    """
    fp = AlertFingerprint(
        error_class="alert",
        attack_pattern=fp_attack,
        environment="production",
    )
    result = TriageEngine().triage(fp, list(matches))
    assert result.proposed_decision == "escalated"
