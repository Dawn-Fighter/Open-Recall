"""Property tests covering the fingerprint module.

Feature: openrecall, Property 1: fingerprint determinism in Demo_Mode.
Feature: openrecall, Property 2: fingerprint round-trip.

Validates: Requirements 3.3, 3.4, 3.6, 3.7
"""
from __future__ import annotations

from hypothesis import given, settings

from incident_agent.fingerprint import (
    format_fingerprint,
    parse_fingerprint,
    regex_fallback,
)

from .conftest import alert_fingerprint_strategy, raw_alert_strategy


@given(raw_alert=raw_alert_strategy)
@settings(max_examples=100, deadline=None)
def test_fingerprint_determinism_demo_mode(raw_alert: str) -> None:
    """P1: Two consecutive regex-fallback fingerprints of the same input must match.

    Validates: Requirements 3.3, 3.4
    """
    fp1 = regex_fallback(raw_alert)
    fp2 = regex_fallback(raw_alert)
    assert fp1 == fp2


@given(fp=alert_fingerprint_strategy())
@settings(max_examples=100, deadline=None)
def test_fingerprint_round_trip(fp) -> None:
    """P2: parse_fingerprint(format_fingerprint(fp)) == fp.

    Validates: Requirements 3.6, 3.7
    """
    serialized = format_fingerprint(fp)
    parsed = parse_fingerprint(serialized)
    assert parsed == fp
