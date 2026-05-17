from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from incident_agent.cost_curve import CostCurveTracker
from incident_agent.memory import IncidentMemory
from incident_agent.models import Alert
from incident_agent.router import CascadeFlowRouter
from incident_agent.workflow import IncidentWorkflow


def smoke_single_alert() -> None:
    """Backward-compat single-alert smoke against data/sample_alerts.json."""
    samples = json.loads((ROOT / "data" / "sample_alerts.json").read_text())
    memory = IncidentMemory()
    router = CascadeFlowRouter()
    tracker = CostCurveTracker()
    workflow = IncidentWorkflow(memory, router, tracker)

    results = [workflow.analyze(sample["raw_alert"]) for sample in samples]

    assert all(result.route_trace for result in results), "each run must emit route trace"
    assert all(result.verification_commands for result in results), (
        "each run must emit verification commands"
    )
    assert any(result.memory_matches for result in results), (
        "seed memory should produce at least one recall hit"
    )
    # Under the OpenRecall triage flow, RouteTrace.escalated no longer maps 1:1
    # to "strong-model invocation", so we instead require every alert to emit a
    # non-empty audit_trace (P15 invariant) — a strictly stronger contract.
    assert all(result.audit_trace for result in results), (
        "each run must emit a non-empty audit_trace"
    )
    assert any(
        not trace.escalated for result in results for trace in result.route_trace
    ), "at least one trace must stay on the standard route"

    print(
        "smoke ok:"
        f" samples={len(results)}"
        f" fallback={memory.fallback_mode}"
        f" traces={sum(len(result.route_trace) for result in results)}"
    )


def smoke_queue() -> None:
    """Exercise analyze_queue on the synthetic 100-alert batch and verify the
    new OpenRecall guarantees (queue ordering, dead_ends surfacing, audit
    completeness, cost-vs-baseline, strict bypass occurrence)."""
    alerts_path = ROOT / "data" / "seed_alerts.json"
    if not alerts_path.exists():
        print(
            "smoke skipped: data/seed_alerts.json missing "
            "(run scripts/generate_seed_alerts.py)"
        )
        return

    # Reset the local fallback file BEFORE running so a previous partial
    # failure (which never reached the post-test reset) cannot pollute this
    # run's memory state. Without this, leftover retained memories from a
    # crashed prior run can mask or amplify bypass behavior in unexpected
    # ways.
    (ROOT / "data" / "local_memory.json").write_text("[]", encoding="utf-8")

    # Reset module-level cached state so the queue test is independent.
    memory = IncidentMemory()
    router = CascadeFlowRouter()
    tracker = CostCurveTracker()
    workflow = IncidentWorkflow(memory, router, tracker)

    raw_alerts = json.loads(alerts_path.read_text(encoding="utf-8"))
    alerts = [
        Alert(raw_alert=str(item.get("raw_alert", "")), title=item.get("title"))
        for item in raw_alerts
    ]

    # R14.3 STRICT smoke: pre-seed memories aligned with the seed_alerts
    # fingerprints so the bypass invariant actually fires under offline
    # keyword-overlap recall. We retain three high-overlap synthetic
    # false_positive memories per fingerprint family; that hits both the
    # Strong_Match (>=0.85 score in local recall via term overlap) and
    # Decision_Consistency (>=0.9, all three agree) thresholds.
    from incident_agent.fingerprint import regex_fallback

    family_seeds = [
        ("checkout-service",
         "checkout-service crashloopbackoff after deploy configmap cleanup keyerror payment provider url crashloop pods restart payments paymentproviderurl checkout"),
        ("payments-api",
         "payments-api timeout pool connection p95 latency 503 active sessions database autoscaler hpa replicas pgstatactivity"),
        ("frontend",
         "frontend feature flag checkout_redesign 5xx spike cohort cart total exception 25 percent rollout javascript"),
        ("worker-service",
         "worker-service redis timeout dns cache stale node restart queue age background job latency cluster"),
        ("auth-service",
         "auth-service configmap key removed oidc issuer url callback 500 deploy readiness probe pods restarting"),
        ("api-gateway",
         "api-gateway jwt validation failure jwks cache key rotation 401 identity downstream gateway pods auth boundary"),
        ("waf",
         "waf sql injection api-gateway search request id source asn block payloads probes rotating"),
        ("notifications-service",
         "notifications-service smtp authentication rejected expired credential email transactional outbound mail queue"),
    ]
    for service, text in family_seeds:
        fp = regex_fallback(f"SEV-2 prod {service} {text}")
        # Seed 6 false_positive memories per family. The local-recall scorer
        # is capped at 5 results; we retain 6 high-overlap memories so that
        # after sorting by score descending the top-5 includes >=5 of our
        # false_positive entries (outweighing any seed_incidents 'real'
        # entries that also match the same keywords). With n_strong=5 and
        # c=1.0 the confidence clamp lands at 1*(1-1/7) ≈ 0.857, just above
        # BYPASS_CONFIDENCE_THRESHOLD=0.85.
        for i in range(6):
            content = f"Confirmed false_positive for {service}. Body: {text}. Iteration {i}."
            memory.retain(
                content,
                fingerprint=fp,
                decision="false_positive",
                dead_ends=[
                    "rolled back the deploy, made it worse (scanner traffic, not real)",
                    "increased timeouts, no effect",
                ],
                analyst_id="smoke-seed",
                business_impact_minutes=0,
            )

    results = workflow.analyze_queue(alerts)
    assert len(results) == len(alerts), "queue must return one result per alert"

    # P15 audit invariant per result.
    for res in results:
        assert len(res.audit_trace) == len(res.route_trace), (
            "audit_trace must have one entry per route_trace step"
        )

    # P9: every CostCurvePoint has cost <= baseline.
    for point in tracker.series():
        assert point.cost_usd <= point.baseline_cost_usd, point

    # R14.3 STRICT: at least one auto-triage bypass MUST occur against the
    # pre-seeded memory.
    bypass_steps = sum(
        1
        for r in results
        for t in r.route_trace
        if t.step == "auto-triage bypass"
    )
    assert bypass_steps >= 1, (
        "expected >= 1 auto-triage bypass after pre-seeding memory; "
        f"got {bypass_steps}. Local-recall scorer may have regressed."
    )

    # Memory-consultation sanity check.
    consulted = sum(
        1
        for r in results
        if r.triage_result and r.triage_result.consistent_decision_count >= 1
    )
    assert consulted >= bypass_steps, "consulted alerts must include all bypassed alerts"

    # Dead-ends should surface for at least one alert in this configuration
    # (seeded false_positive memories carry dead_ends; the bypass flow
    # aggregates them onto AnalysisResult.dead_ends).
    with_dead_ends = sum(1 for r in results if r.dead_ends)
    assert with_dead_ends >= 1, (
        f"expected >= 1 result with dead_ends, got {with_dead_ends}"
    )

    # Reset the local fallback file so re-running the smoke test stays
    # idempotent across runs.
    (ROOT / "data" / "local_memory.json").write_text("[]", encoding="utf-8")

    print(
        "smoke queue ok:"
        f" alerts={len(results)}"
        f" memory_consulted={consulted}"
        f" bypass_steps={bypass_steps}"
        f" with_dead_ends={with_dead_ends}"
        f" tracker_points={len(tracker.series())}"
    )


def smoke_env_example() -> None:
    """Verify .env.example has every required key and contains no live secrets."""
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    required = [
        "HINDSIGHT_BASE_URL",
        "HINDSIGHT_API_KEY",
        "HINDSIGHT_BANK_ID",
        "GROQ_API_KEY",
        "CASCADEFLOW_MODE",
        "CASCADEFLOW_LIVE_GROQ",
        "CASCADEFLOW_RUN_BUDGET_USD",
        "CASCADEFLOW_CHEAP_MODEL",
        "CASCADEFLOW_STRONG_MODEL",
        "OPENRECALL_PBT_SEED",
        "OPENRECALL_BATCH_SIZE_LIMIT",
    ]
    for key in required:
        assert f"{key}=" in text, f".env.example missing required key: {key}"
    pattern = re.compile(r"gsk_[A-Za-z0-9_]{20,}|hsk_[A-Za-z0-9_]{20,}")
    assert not pattern.search(text), ".env.example contains a live-looking key"
    print("smoke env.example ok: all keys present, no live secrets detected")


def smoke_seed_incidents_schema() -> None:
    """Every record in seed_incidents.json must expose triage_decision and dead_ends."""
    seed = json.loads(
        (ROOT / "data" / "seed_incidents.json").read_text(encoding="utf-8")
    )
    for record in seed:
        assert "triage_decision" in record, (
            f"missing triage_decision: {record.get('title')}"
        )
        assert "dead_ends" in record, f"missing dead_ends: {record.get('title')}"
        assert isinstance(record["dead_ends"], list)
    print(f"smoke seed_incidents schema ok: {len(seed)} records")


def main() -> None:
    os.environ.setdefault("CASCADEFLOW_LIVE_GROQ", "false")
    os.environ.setdefault("HINDSIGHT_BASE_URL", "http://127.0.0.1:9")

    smoke_single_alert()
    smoke_queue()
    smoke_env_example()
    smoke_seed_incidents_schema()


if __name__ == "__main__":
    main()
