"""Deterministic generator for ``data/seed_alerts.json``.

This script emits exactly 100 synthetic alerts following the OpenRecall design
distribution (50 repeats from 8 fingerprint families / 30 false positives /
15 novel real incidents / 5 ambiguous mixed-signal entries).

The generator uses a fresh local ``random.Random(SEED)`` instance instead of
``random.seed`` so importing the module does not perturb the global RNG and
so re-running the script produces byte-identical output.

Run from ``incident-memory-agent/``::

    python scripts/generate_seed_alerts.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

SEED = 20260101
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_alerts.json"


# ---------------------------------------------------------------------------
# 8 fingerprint families aligned with data/seed_incidents.json
# ---------------------------------------------------------------------------

FAMILIES: list[dict[str, Any]] = [
    {
        "family_name": "auth-service-configmap-missing-key",
        "service": "auth-service",
        "severity_choices": ["SEV-2", "P2"],
        "signal_phrases": [
            "auth callback returning 500 after deploy",
            "KeyError OIDC_ISSUER_URL in pod logs",
            "login flow 5xx spike on /oauth/callback",
            "pods restarting with missing env var",
            "auth-service readiness probe flapping",
        ],
        "recent_change_phrases": [
            "right after the ConfigMap cleanup PR merged",
            "after deploy 2026.05.14 rolled the auth manifest",
            "shortly after secrets rotation in production",
        ],
        "title_prefix": "Repeat: auth-service ConfigMap missing key",
    },
    {
        "family_name": "checkout-service-crashloop",
        "service": "checkout-service",
        "severity_choices": ["SEV-2", "P2"],
        "signal_phrases": [
            "CrashLoopBackOff after deploy",
            "pods restart every 40s",
            "5xx on checkout endpoint",
            "KeyError PAYMENT_PROVIDER_URL",
            "container exits with code 137",
        ],
        "recent_change_phrases": [
            "after ConfigMap cleanup removed env var",
            "after deploy 2026.05.16",
            "right after the 14:07 UTC release",
        ],
        "title_prefix": "Repeat: checkout-service CrashLoopBackOff",
    },
    {
        "family_name": "payments-api-db-pool-exhausted",
        "service": "payments-api",
        "severity_choices": ["SEV-1", "SEV-2"],
        "signal_phrases": [
            "timeout waiting for connection from pool",
            "p95 latency above 8s on /charge",
            "503 spike with database connection errors",
            "active sessions near pg_stat_activity max",
            "payments retries draining the DB pool",
        ],
        "recent_change_phrases": [
            "after HPA doubled replicas during traffic spike",
            "after worker release increased pool size per pod",
            "shortly after autoscaler scaled out",
        ],
        "title_prefix": "Repeat: payments-api DB pool exhausted",
    },
    {
        "family_name": "worker-service-redis-timeout",
        "service": "worker-service",
        "severity_choices": ["SEV-3", "P3"],
        "signal_phrases": [
            "Redis timeout in worker logs",
            "background job latency increased",
            "DNS cache held stale Redis IP",
            "worker queue age climbing",
            "intermittent Redis ECONNREFUSED",
        ],
        "recent_change_phrases": [
            "after managed node restart in the cache tier",
            "after Redis cluster failover at 03:12 UTC",
            "after the cache node IP rotated",
        ],
        "title_prefix": "Repeat: worker-service Redis timeout",
    },
    {
        "family_name": "frontend-feature-flag-5xx",
        "service": "frontend",
        "severity_choices": ["SEV-3", "P3"],
        "signal_phrases": [
            "5xx spike from feature flag cohort",
            "Cannot read properties of undefined reading cart.total",
            "JS exception in checkout_redesign component",
            "errors limited to 25% rollout cohort",
            "client-side 500 reports on /checkout",
        ],
        "recent_change_phrases": [
            "right after feature flag checkout_redesign was enabled for 25% of users",
            "after gradual rollout bumped flag to 50%",
            "after the flag cohort widened overnight",
        ],
        "title_prefix": "Repeat: frontend feature flag 5xx",
    },
    {
        "family_name": "api-gateway-jwt-validation",
        "service": "api-gateway",
        "severity_choices": ["SEV-2", "P2"],
        "signal_phrases": [
            "JWT validation failures with 401",
            "JWKS cache mismatch on gateway pods",
            "downstream API rejecting tokens minted post-rotation",
            "auth boundary returning 401 for valid users",
            "intermittent 401 on /api endpoints",
        ],
        "recent_change_phrases": [
            "after identity-service key rotation at 02:00 UTC",
            "after JWKS overlap window expired",
            "after gateway pods cached the previous keyset",
        ],
        "title_prefix": "Repeat: api-gateway JWT validation failure",
    },
    {
        "family_name": "waf-sql-injection",
        "service": "waf",
        "severity_choices": ["HIGH", "SEV-2"],
        "signal_phrases": [
            "WAF grouped SQL injection payloads against /search",
            "repeated ' OR 1=1-- attempts from rotating ASNs",
            "app 500s correlated with blocked WAF events",
            "SQLi probes against api-gateway",
            "WAF rule matched 60+ requests in one minute",
        ],
        "recent_change_phrases": [
            "preserve request IDs for evidence",
            "no recent deploy correlated, looks like external probing",
            "matches the prior pattern from last week",
        ],
        "title_prefix": "Repeat: waf SQL injection probe",
    },
    {
        "family_name": "notifications-smtp-credential-expired",
        "service": "notifications-service",
        "severity_choices": ["SEV-3", "P3"],
        "signal_phrases": [
            "SMTP authentication rejected by upstream",
            "email delivery failing for transactional sends",
            "expired SMTP credential in secret store",
            "notifications queue age climbing",
            "outbound mail dropping with 535 auth error",
        ],
        "recent_change_phrases": [
            "after the SMTP credential expired overnight",
            "after the rotation reminder went unanswered",
            "after the secret hit its TTL boundary",
        ],
        "title_prefix": "Repeat: notifications-service expired SMTP credential",
    },
]


# ---------------------------------------------------------------------------
# False-positive templates (one-offs from non-incident sources)
# ---------------------------------------------------------------------------

FALSE_POSITIVES: list[dict[str, Any]] = [
    {
        "title_prefix": "FP: corp pen-test scanner",
        "service": "api-gateway",
        "severity_choices": ["LOW", "INFO"],
        "raw_phrases": [
            "internal pen-test scanner from corp ASN scanning prod gateway endpoints",
            "scheduled red-team scan probing /admin and /metrics from sre-toolkit-job",
            "authorized pen-test traffic flagged by IDS as suspicious",
        ],
    },
    {
        "title_prefix": "FP: scheduled vuln scan",
        "service": "staging-frontend",
        "severity_choices": ["LOW", "INFO"],
        "raw_phrases": [
            "scheduled vulnerability scan on staging-frontend, alert misrouted to prod channel",
            "weekly Nessus scan against staging hit prod alert routing rule by mistake",
            "vuln-scanner-job touched staging endpoints, paged the prod oncall",
        ],
    },
    {
        "title_prefix": "FP: synthetic monitor",
        "service": "synthetic-monitor",
        "severity_choices": ["LOW", "INFO"],
        "raw_phrases": [
            "synthetic monitor probe causing 401 on /healthz with stale credentials",
            "datadog synthetic check using rotated API token, expected 401 looks like an outage",
            "synthetic monitor in eu-west-1 paging on its own auth misconfig",
        ],
    },
    {
        "title_prefix": "FP: dependabot",
        "service": "ci-bot",
        "severity_choices": ["LOW", "INFO"],
        "raw_phrases": [
            "dependabot PR alert mistakenly tagged production by repo workflow",
            "dependabot security advisory on dev dependency, routed to prod channel",
            "automated dependency PR opened, alert pipeline tagged severity prod",
        ],
    },
    {
        "title_prefix": "FP: internal load test",
        "service": "payments-api",
        "severity_choices": ["LOW", "INFO"],
        "raw_phrases": [
            "internal load test from sre-toolkit-job hitting payments-api at 5x normal RPS",
            "k6 load test from sre-toolkit run window, traffic above SLO by design",
            "scheduled capacity-test traffic flagged as anomaly by traffic alerting",
        ],
    },
    {
        "title_prefix": "FP: scheduled DR drill",
        "service": "platform",
        "severity_choices": ["LOW", "INFO"],
        "raw_phrases": [
            "quarterly DR drill triggered region failover, monitoring alerts firing as expected",
            "DR exercise paused replication, lag alert firing per runbook",
            "planned region drain produced 5xx spike that resolved as the drill ended",
        ],
    },
]


# ---------------------------------------------------------------------------
# 15 novel real incidents — unique error_class + dependency_pattern combos
# not present in seed_incidents.json
# ---------------------------------------------------------------------------

NOVEL_REAL: list[dict[str, str]] = [
    {
        "title": "Novel: dns-resolver-service DNSResolutionFailure",
        "raw_alert": (
            "SEV-2 production dns-resolver-service reporting DNSResolutionFailure on internal "
            ".svc.cluster.local domains after CoreDNS rollout. Multiple consumer services "
            "logging upstream DNS lookups timing out around the rollout window."
        ),
    },
    {
        "title": "Novel: metrics-collector OOMKilled after relabeling",
        "raw_alert": (
            "SEV-2 prod metrics-collector pods OOMKilled after Prometheus relabeling rules "
            "expanded series cardinality by an order of magnitude. Heap usage doubled within "
            "minutes of the new scrape config landing."
        ),
    },
    {
        "title": "Novel: cdn-edge cache poisoning suspected",
        "raw_alert": (
            "HIGH prod cdn-edge cache poisoning suspected on /api/products. Some users seeing "
            "another tenant's response payloads. Vary header looks misconfigured for the "
            "endpoint at the edge."
        ),
    },
    {
        "title": "Novel: event-bus consumer lag on payments.received",
        "raw_alert": (
            "SEV-2 prod event-bus consumer lag spike on payments.received topic. Lag jumped "
            "from seconds to 40 minutes for the settlement consumer group while producer rate "
            "stayed flat."
        ),
    },
    {
        "title": "Novel: auth-broker MFA failing for offline TOTP",
        "raw_alert": (
            "SEV-2 prod auth-broker MFA challenges failing for users with offline TOTP "
            "devices after a clock-drift correction. Online push MFA still working, only "
            "TOTP-derived codes rejected."
        ),
    },
    {
        "title": "Novel: report-renderer PDF hang",
        "raw_alert": (
            "SEV-3 prod report-renderer PDF generation hanging on customer report 47291. "
            "Worker thread stuck in headless browser layout, queue draining slower than "
            "incoming requests."
        ),
    },
    {
        "title": "Novel: geo-router 503 in eu-west-1",
        "raw_alert": (
            "SEV-2 prod geo-router returning 503 Service Unavailable in eu-west-1. Other "
            "regions healthy. Edge load balancer reporting no healthy upstreams in that AZ."
        ),
    },
    {
        "title": "Novel: feature-store stale read after backfill",
        "raw_alert": (
            "SEV-3 prod feature-store stale read on user_segments after batch backfill ran "
            "overnight. ML scoring service computing decisions on yesterday's segment "
            "assignments for a subset of users."
        ),
    },
    {
        "title": "Novel: kms-proxy decrypt latency above SLO",
        "raw_alert": (
            "SEV-2 prod kms-proxy decrypt latency p99 above SLO at 4.2s. Downstream services "
            "depending on per-request decryption seeing checkout and tokenization paths slow "
            "in lockstep."
        ),
    },
    {
        "title": "Novel: istiod high CPU after VirtualService update",
        "raw_alert": (
            "SEV-2 prod service-mesh-istiod high CPU usage after VirtualService update added "
            "60+ host matches. Sidecar config push latency climbed and proxies stale by "
            "minutes."
        ),
    },
    {
        "title": "Novel: analytics-pipeline BigQuery quota exceeded",
        "raw_alert": (
            "SEV-3 prod analytics-pipeline daily job failed: BigQuery quota exceeded for "
            "concurrent slot usage. Downstream dashboards stale, refresh job retrying with "
            "backoff."
        ),
    },
    {
        "title": "Novel: mobile-api iOS 401 after sso refresh regression",
        "raw_alert": (
            "SEV-2 prod mobile-api iOS users hitting 401 after sso refresh token regression "
            "in the latest mobile build. Android cohort unaffected. Logs show refresh tokens "
            "rejected immediately on rotation."
        ),
    },
    {
        "title": "Novel: data-export-worker S3 multipart stalls",
        "raw_alert": (
            "SEV-3 prod data-export-worker S3 multipart upload stalls midway through 4GB "
            "exports. Part uploads succeed, completion call hangs. Affecting nightly "
            "compliance exports."
        ),
    },
    {
        "title": "Novel: password-policy-service rate limit shadow ban",
        "raw_alert": (
            "SEV-2 prod password-policy-service rate limit shadow-banning legit users after "
            "the new sliding window policy went live. Users see silent failures on password "
            "change with no error surfaced."
        ),
    },
    {
        "title": "Novel: chargeback-service late-night zero-row anomaly",
        "raw_alert": (
            "SEV-3 prod chargeback-service late-night batch produced zero rows for the first "
            "time in 18 months. Upstream provider feed looked healthy. No exception raised, "
            "anomaly detector caught it on the morning review."
        ),
    },
]


# ---------------------------------------------------------------------------
# 5 ambiguous mixed-signal alerts
# ---------------------------------------------------------------------------

AMBIGUOUS: list[dict[str, str]] = [
    {
        "title": "Ambiguous: payments-api intermittent 503",
        "raw_alert": (
            "P2 prod payments-api intermittent 503 with no obvious change in deploy logs. "
            "Multiple possible owners on call, ambiguous root cause across DB, cache, and "
            "third-party processor signals."
        ),
    },
    {
        "title": "Ambiguous: frontend 5xx spike across cohorts",
        "raw_alert": (
            "SEV-3 prod ambiguous frontend 5xx spike across 3 cohorts with unknown owner. "
            "Errors split between checkout, profile, and search bundles. No single deploy "
            "correlates."
        ),
    },
    {
        "title": "Ambiguous: profile-service intermittent cache miss",
        "raw_alert": (
            "SEV-3 prod profile-service intermittent cache misses that may correlate with "
            "deploy 2026.05.18, but the ratio is within normal weekly variance. Unknown "
            "owner, possibly platform or service team."
        ),
    },
    {
        "title": "Ambiguous: frontend 504 across upstreams",
        "raw_alert": (
            "SEV-3 prod frontend tracing reports 504 timeouts intermittently against multiple "
            "possible upstreams. Trace samples ambiguous between gateway, search, and "
            "recommendations as the slow hop."
        ),
    },
    {
        "title": "Ambiguous: payments retry storm",
        "raw_alert": (
            "SEV-2 prod payments retry storm with ambiguous root cause; no obvious deploy or "
            "config change. Retry budget burning fast across multiple downstreams. Unknown "
            "owner pending triage."
        ),
    },
]


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------


def render_repeat(rng: random.Random, family: dict[str, Any], repeat_idx: int) -> dict[str, str]:
    """Render one repeat alert for a given fingerprint family."""
    severity = rng.choice(family["severity_choices"])
    primary = rng.choice(family["signal_phrases"])
    secondary_pool = [phrase for phrase in family["signal_phrases"] if phrase != primary]
    secondary = rng.choice(secondary_pool) if secondary_pool else ""
    recent_change = rng.choice(family["recent_change_phrases"])

    sentences = [f"{severity} prod {family['service']} {primary}."]
    if secondary and rng.random() < 0.7:
        sentences.append(f"Also seeing {secondary}.")
    sentences.append(f"Triggered {recent_change}.")
    raw_alert = " ".join(sentences)

    title = f"{family['title_prefix']} #{repeat_idx}"
    return {"title": title, "raw_alert": raw_alert}


def render_false_positive(rng: random.Random, template: dict[str, Any], fp_idx: int) -> dict[str, str]:
    """Render one false-positive alert from a non-incident source."""
    severity = rng.choice(template["severity_choices"])
    body = rng.choice(template["raw_phrases"])
    raw_alert = f"{severity} {template['service']} {body}. No customer impact reported."
    title = f"{template['title_prefix']} #{fp_idx}"
    return {"title": title, "raw_alert": raw_alert}


def generate_repeats(rng: random.Random) -> list[dict[str, str]]:
    """Generate 50 repeats across the 8 fingerprint families.

    Distribution: 6 per family for the first 6 families, 7 for the last 2,
    summing to 6*6 + 7*2 = 50. Within the class we shuffle so families are
    interleaved rather than all-checkout-then-all-payments.
    """
    counts = [6, 6, 6, 6, 6, 6, 7, 7]
    assert sum(counts) == 50
    repeats: list[dict[str, str]] = []
    for family, count in zip(FAMILIES, counts):
        for repeat_idx in range(1, count + 1):
            repeats.append(render_repeat(rng, family, repeat_idx))
    rng.shuffle(repeats)
    return repeats


def generate_false_positives(rng: random.Random) -> list[dict[str, str]]:
    """Generate 30 one-off false-positive alerts (5 per template, 6 templates)."""
    per_template = 5
    assert per_template * len(FALSE_POSITIVES) == 30
    fps: list[dict[str, str]] = []
    for template in FALSE_POSITIVES:
        for fp_idx in range(1, per_template + 1):
            fps.append(render_false_positive(rng, template, fp_idx))
    rng.shuffle(fps)
    return fps


def generate_novel(rng: random.Random) -> list[dict[str, str]]:
    """Return the 15 novel real incidents, shuffled within their class."""
    novel = [dict(entry) for entry in NOVEL_REAL]
    assert len(novel) == 15
    rng.shuffle(novel)
    return novel


def generate_ambiguous(rng: random.Random) -> list[dict[str, str]]:
    """Return the 5 ambiguous mixed-signal alerts, shuffled within their class."""
    ambiguous = [dict(entry) for entry in AMBIGUOUS]
    assert len(ambiguous) == 5
    rng.shuffle(ambiguous)
    return ambiguous


def main() -> None:
    rng = random.Random(SEED)

    repeats = generate_repeats(rng)
    false_positives = generate_false_positives(rng)
    novel = generate_novel(rng)
    ambiguous = generate_ambiguous(rng)

    alerts: list[dict[str, str]] = []
    alerts.extend(repeats)
    alerts.extend(false_positives)
    alerts.extend(novel)
    alerts.extend(ambiguous)

    assert len(alerts) == 100, f"expected 100 alerts, got {len(alerts)}"
    for entry in alerts:
        assert isinstance(entry["title"], str) and entry["title"], "title must be non-empty str"
        assert isinstance(entry["raw_alert"], str) and entry["raw_alert"], "raw_alert must be non-empty str"

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(alerts, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(alerts)} alerts to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
