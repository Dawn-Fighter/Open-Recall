"""Alert DNA fingerprinting — cheap-model JSON extract with deterministic regex fallback."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from .models import AlertFingerprint, RouteTrace
from .router import estimate_cost

if TYPE_CHECKING:
    from .router import CascadeFlowRouter


_FINGERPRINT_FIELDS: tuple[str, ...] = (
    "error_class",
    "service_role",
    "dependency_pattern",
    "signal_shape",
    "attack_pattern",
    "environment",
)


_FINGERPRINT_RE = re.compile(
    r"^"
    r"error_class=(?P<error_class>[^;]*); "
    r"service_role=(?P<service_role>[^;]*); "
    r"dependency_pattern=(?P<dependency_pattern>[^;]*); "
    r"signal_shape=(?P<signal_shape>[^;]*); "
    r"attack_pattern=(?P<attack_pattern>[^;]*); "
    r"environment=(?P<environment>[^;]*)"
    r"$"
)


def infer_error_type(text: str) -> str:
    for key in [
        "crashloopbackoff",
        "oomkill",
        "oom",
        "liveness",
        "readiness",
        "5xx",
        "timeout",
        "sql injection",
        "jwt",
        "credential stuffing",
        "pool exhausted",
        "migration lock",
    ]:
        if key in text:
            return key
    return "application error"


def pick_known_service(text: str) -> str | None:
    known_services = [
        "auth-service",
        "checkout-service",
        "payments-api",
        "worker-service",
        "frontend",
        "orders-api",
        "notifications-service",
        "identity-service",
        "waf",
        "api-gateway",
        "catalog-api",
        "billing-worker",
        "search-service",
        "inventory-service",
        "realtime-api",
        "admin-api",
        "webhook-service",
        "profile-service",
    ]
    for service in known_services:
        if service in text:
            return service
    return None


def infer_dependency(text: str) -> str | None:
    for dep in [
        "postgres",
        "database",
        "redis",
        "smtp",
        "stripe",
        "identity",
        "jwks",
        "configmap",
        "feature flag",
    ]:
        if dep in text:
            return dep
    return None


def match_first(text: str, patterns: list[str], default: str = "") -> str:
    """Return the first pattern from ``patterns`` that appears in ``text`` or ``default``."""
    for p in patterns:
        if p in text:
            return p
    return default


def regex_fallback(raw_alert: str) -> AlertFingerprint:
    """Deterministic regex/keyword extractor used in Demo_Mode and live-failure paths."""
    text = raw_alert.lower()
    return AlertFingerprint(
        error_class=infer_error_type(text),
        service_role=pick_known_service(text) or "",
        dependency_pattern=infer_dependency(text) or "",
        signal_shape=match_first(
            text,
            ["5xx", "4xx", "timeout", "crashloop", "oom", "latency", "p95"],
            default="",
        ),
        attack_pattern=match_first(
            text,
            ["sql injection", "credential stuffing", "jwt", "waf", "attack", "csrf", "xss"],
            default="",
        ),
        environment=match_first(
            text,
            ["production", "prod", "staging", "dev", "qa"],
            default="production",
        ),
    )


def format_fingerprint(fp: AlertFingerprint) -> str:
    """Serialize an AlertFingerprint into the canonical string form.

    Empty fields render as the literal ``none``; field order is fixed.
    """
    parts = []
    for name in _FINGERPRINT_FIELDS:
        value = getattr(fp, name) or "none"
        parts.append(f"{name}={value}")
    return "; ".join(parts)


def parse_fingerprint(text: str) -> AlertFingerprint:
    """Parse a canonical fingerprint string back into an AlertFingerprint.

    Raises ``ValueError`` on missing/unknown keys. Treats the literal ``none`` as empty.
    """
    m = _FINGERPRINT_RE.match(text)
    if not m:
        raise ValueError(f"unparseable fingerprint string: {text!r}")
    fields = {name: ("" if value == "none" else value) for name, value in m.groupdict().items()}
    return AlertFingerprint(**fields)


class FingerprintGenerator:
    """Cheap-model-first fingerprint extractor with deterministic regex fallback."""

    def __init__(self, router: "CascadeFlowRouter") -> None:
        self.router = router

    def generate(self, raw_alert: str) -> tuple[AlertFingerprint, RouteTrace]:
        if self.router.live_groq and self.router.api_key:
            response, trace = self.router.fingerprint_with_trace(raw_alert)
            if response is not None:
                merged = self._fill_missing_with_regex(response, raw_alert)
                try:
                    return AlertFingerprint(**merged), trace
                except ValidationError:
                    pass  # fall through to regex
        # Demo_Mode / live failure path: regex fallback
        fp = regex_fallback(raw_alert)
        trace = self._build_synthetic_trace(raw_alert)
        return fp, trace

    def _fill_missing_with_regex(
        self, response: dict[str, Any], raw_alert: str
    ) -> dict[str, Any]:
        fb = regex_fallback(raw_alert)
        return {
            field: response.get(field) or getattr(fb, field)
            for field in _FINGERPRINT_FIELDS
        }

    def _build_synthetic_trace(self, raw_alert: str) -> RouteTrace:
        baseline = estimate_cost(raw_alert, self.router.strong_model)
        if not self.router.live_groq:
            reason = "Demo_Mode: deterministic regex fingerprint (LIVE_GROQ off)"
        elif not self.router.api_key:
            reason = "live Groq requested but GROQ_API_KEY is missing; deterministic regex fingerprint"
        else:
            reason = "cheap model returned malformed JSON; deterministic regex fingerprint"
        return RouteTrace(
            step="alert fingerprint",
            model=self.router.cheap_model,
            route_reason=reason,
            confidence=0.7,
            latency_ms=0.0,
            estimated_cost_usd=0.0,
            strong_model_baseline_cost_usd=baseline,
            savings_vs_strong_usd=baseline,
            escalated=False,
            cascadeflow_enabled=self.router.cascadeflow_enabled,
            live_model_call=False,
            budget_remaining_usd=max(0.0, round(self.router.run_budget, 5)),
        )
