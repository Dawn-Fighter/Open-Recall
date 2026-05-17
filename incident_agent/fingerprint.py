"""Alert DNA fingerprinting — cheap-model JSON extract with deterministic regex fallback."""
from __future__ import annotations

import re
from hashlib import sha256
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


# Allowed values per field. Empty string is always allowed; only Groq-output
# normalisation enforces these. The regex fallback already produces values
# from these vocabularies.
_SECURITY_KEYWORDS: tuple[str, ...] = (
    "sql injection",
    "credential stuffing",
    "jwt",
    "waf",
    "attack",
    "csrf",
    "xss",
    "ddos",
    "ssrf",
    "rce",
    "lfi",
    "rfi",
    "log4shell",
    "phishing",
)

_DEPENDENCY_KEYWORDS: tuple[str, ...] = (
    "postgres",
    "database",
    "redis",
    "smtp",
    "stripe",
    "identity",
    "jwks",
    "configmap",
    "feature flag",
    "kafka",
    "rabbitmq",
    "mongo",
    "mysql",
    "s3",
    "dynamodb",
)

_SIGNAL_SHAPES: tuple[str, ...] = (
    "5xx",
    "4xx",
    "timeout",
    "crashloop",
    "oom",
    "latency",
    "p95",
    "p99",
    "spike",
)

_ENV_VOCAB: tuple[str, ...] = ("production", "prod", "staging", "dev", "qa")


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


def _canonicalize(value: Any, max_len: int = 30) -> str:
    """Trim, lowercase, collapse whitespace, cap length.

    Used to normalise cheap-model output so the same alert text produces
    the same canonical fingerprint values across runs even if the model
    returns minor wording variations like ``"Crashloop"`` vs ``"crashloop"``
    or ``"recurring crash every 90s"`` vs ``"service crashing every 90s"``.
    """
    if not value:
        return ""
    s = str(value).strip().lower()
    s = re.sub(r"\s+", " ", s)
    # Strip surrounding punctuation that adds no signal.
    s = s.strip("\"';:.,!?-_")
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


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
    """Cheap-model-first fingerprint extractor with deterministic regex fallback.

    Adds three defenses against cheap-model non-determinism so identical
    alert text always produces identical fingerprints:

    1. **Per-process cache** keyed on ``sha256(raw_alert)``. The first call
       for a given alert text runs through the model + canonicalize path;
       every subsequent call returns the cached fingerprint instantly.
    2. **Canonicalization** of every cheap-model field (lowercase, strip,
       collapse whitespace, cap length) so wording drift between calls
       (``"recurring crash every 90s"`` vs ``"service crashing every 90s"``)
       collapses to the same value.
    3. **Attack-pattern validation**. The cheap model occasionally
       hallucinates an ``attack_pattern`` for non-security alerts (e.g.
       deploy hashes). We accept the model's value only if the regex
       extractor ALSO finds at least one known security keyword in the raw
       alert; otherwise we drop it. This keeps the security-novel kill
       switch (P12) honest.
    """

    _MAX_CACHE = 1024  # cap to avoid unbounded growth in long-lived processes

    def __init__(self, router: "CascadeFlowRouter") -> None:
        self.router = router
        self._cache: dict[str, tuple[AlertFingerprint, RouteTrace]] = {}

    def generate(self, raw_alert: str) -> tuple[AlertFingerprint, RouteTrace]:
        cache_key = sha256(raw_alert.encode("utf-8")).hexdigest()
        cached = self._cache.get(cache_key)
        if cached is not None:
            # Return a fresh trace clone so cumulative cost accounting
            # downstream isn't double-charged for cached fingerprints.
            fp, _orig_trace = cached
            cached_trace = self._build_synthetic_trace(
                raw_alert,
                reason="cached fingerprint (deterministic — same raw alert seen this session)",
            )
            return fp, cached_trace

        if self.router.live_groq and self.router.api_key:
            response, trace = self.router.fingerprint_with_trace(raw_alert)
            if response is not None:
                merged = self._fill_missing_with_regex(response, raw_alert)
                try:
                    fp = AlertFingerprint(**merged)
                    self._remember(cache_key, fp, trace)
                    return fp, trace
                except ValidationError:
                    pass  # fall through to regex
        # Demo_Mode / live failure path: regex fallback
        fp = regex_fallback(raw_alert)
        trace = self._build_synthetic_trace(raw_alert)
        self._remember(cache_key, fp, trace)
        return fp, trace

    def _remember(
        self,
        cache_key: str,
        fp: AlertFingerprint,
        trace: RouteTrace,
    ) -> None:
        if len(self._cache) >= self._MAX_CACHE:
            # Drop the oldest entry. Insertion-order is preserved by dict
            # since Python 3.7, so popping the first key is FIFO.
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = (fp, trace)

    def _fill_missing_with_regex(
        self, response: dict[str, Any], raw_alert: str
    ) -> dict[str, Any]:
        """Merge cheap-model output with the regex fallback.

        Cheap-model values are canonicalized (lowercase, trimmed,
        whitespace-collapsed, length-capped). For ``attack_pattern`` we
        additionally REQUIRE corroboration from the regex extractor — if
        the alert text contains no security keywords, the model's value
        is dropped. This protects the security-novel kill switch from
        false triggers caused by the model attaching ``attack_pattern`` to
        deploy events, feature flags, etc.
        """
        fb = regex_fallback(raw_alert)
        text = raw_alert.lower()

        merged: dict[str, Any] = {}
        for field in _FINGERPRINT_FIELDS:
            model_value = _canonicalize(response.get(field))

            if field == "attack_pattern":
                # Hallucination guard: only accept the model's attack_pattern
                # if the alert text actually contains a security signature.
                regex_value = fb.attack_pattern
                if model_value and any(
                    kw in text for kw in _SECURITY_KEYWORDS
                ):
                    merged[field] = model_value
                else:
                    merged[field] = regex_value
                continue

            if field == "environment":
                # Constrain to known vocabulary; default to regex output.
                if model_value in _ENV_VOCAB:
                    merged[field] = model_value
                else:
                    merged[field] = fb.environment or "production"
                continue

            # All other fields: prefer the canonicalized model value when
            # non-empty, else fall back to regex.
            merged[field] = model_value or getattr(fb, field) or ""

        return merged

    def _build_synthetic_trace(
        self, raw_alert: str, reason: str | None = None
    ) -> RouteTrace:
        baseline = estimate_cost(raw_alert, self.router.strong_model)
        if reason is None:
            if not self.router.live_groq:
                reason = "Demo_Mode: deterministic regex fingerprint (LIVE_GROQ off)"
            elif not self.router.api_key:
                reason = (
                    "live Groq requested but GROQ_API_KEY is missing; "
                    "deterministic regex fingerprint"
                )
            else:
                reason = (
                    "cheap model returned malformed JSON; "
                    "deterministic regex fingerprint"
                )
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
