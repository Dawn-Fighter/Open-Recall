"""OpenRecall FastAPI backend.

Holds the long-lived ``IncidentMemory``, ``CascadeFlowRouter``,
``CostCurveTracker``, and ``IncidentWorkflow`` singletons (RULE-CODE-07).
Exposes the cockpit-facing HTTP surface: ``/health``, ``/stats``,
``/cost-curve``, ``/seed``, ``/analyze``, ``/retain``.

Every ``/analyze`` request goes through ``workflow.analyze`` so that the
audit-trace completeness invariant (P15) holds for every response. Do
not introduce a parallel cache layer that bypasses the workflow.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")

from incident_agent.cost_curve import CostCurveTracker
from incident_agent.fingerprint import format_fingerprint
from incident_agent.memory import IncidentMemory
from incident_agent.models import AlertFingerprint
from incident_agent.router import CascadeFlowRouter
from incident_agent.workflow import IncidentWorkflow


# ── Module-level singletons (RULE-CODE-07) ──────────────────────────────────
mem = IncidentMemory()
rt = CascadeFlowRouter()
tracker = CostCurveTracker()
workflow = IncidentWorkflow(mem, rt, tracker)


# ── App + lifespan ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-seed Hindsight memory on startup without blocking the app from
    binding to its port. Seeding 18 records can take ~50s against the live
    Hindsight Cloud, which would otherwise leave ``/health`` unanswered for
    the entire window. We dispatch it as a fire-and-forget background task
    so the API is ready immediately and the seed status is logged when it
    finishes (or fails).
    """
    import asyncio
    import os

    os.environ.setdefault("HINDSIGHT_SEED_LIMIT", "18")

    async def _seed_in_background() -> None:
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, mem.seed)
            print(f"[OpenRecall] Startup seed: {result}")
        except Exception as exc:  # noqa: BLE001 — log and continue; runtime is up
            print(f"[OpenRecall] Startup seed failed: {exc!r}")

    seed_task = asyncio.create_task(_seed_in_background())
    try:
        yield
    finally:
        # Cancel the seed task on shutdown so we don't leak it.
        if not seed_task.done():
            seed_task.cancel()
            try:
                await seed_task
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(title="OpenRecall API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


TriageDecision = Literal[
    "false_positive", "duplicate", "known_benign", "real", "escalated"
]


# ── Request models ──────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    alert: str


class RetainRequest(BaseModel):
    raw_alert: str
    service: str
    decision: TriageDecision
    dead_ends: list[str] = []
    analyst_note: Optional[str] = None
    fingerprint: Optional[dict] = None


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "hindsight_connected": not mem.fallback_mode,
        "hindsight_status": mem.status,
        "groq_live": rt.live_groq and bool(rt.api_key),
        "cheap_model": getattr(rt, "cheap_model", "qwen/qwen3-32b"),
        "strong_model": getattr(rt, "strong_model", "openai/gpt-oss-120b"),
        "budget_usd": getattr(rt, "run_budget", 0.05),
    }


# ── Stats ───────────────────────────────────────────────────────────────────
@app.get("/stats")
def stats() -> dict:
    total_cost, total_baseline, pct_saved = tracker.savings()
    savings = max(0.0, total_baseline - total_cost)
    points = tracker.series()
    return {
        "total_alerts": len(points),
        "total_cost_usd": round(total_cost, 6),
        "total_savings_usd": round(savings, 6),
        "pct_saved": round(pct_saved, 1),
        "hindsight_connected": not mem.fallback_mode,
        "groq_live": rt.live_groq and bool(rt.api_key),
    }


# ── Cost curve ──────────────────────────────────────────────────────────────
@app.get("/cost-curve")
def cost_curve() -> dict:
    points = tracker.series()
    return {
        "points": [
            {
                "index": p.alert_index,
                "cost": round(p.cost_usd, 6),
                "baseline": round(p.baseline_cost_usd, 6),
            }
            for p in points
        ]
    }


# ── Seed Hindsight ──────────────────────────────────────────────────────────
@app.post("/seed")
def seed_memory() -> dict:
    """Push all seed incidents from data/seed_incidents.json into Hindsight."""
    import os

    os.environ["HINDSIGHT_SEED_LIMIT"] = "18"
    try:
        result = mem.seed()
        return {"status": "ok", "message": result}
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


# ── Analyze ─────────────────────────────────────────────────────────────────
@app.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    """Single source of truth for an alert's triage card.

    Every request runs through ``workflow.analyze`` so that the audit
    trace and route trace stay in lockstep (P15). Memory bypass is
    decided inside the workflow based on the structured fingerprint
    plus ``Strong_Match`` and ``Decision_Consistency`` thresholds — not
    via a parallel hash cache here.
    """
    try:
        result = workflow.analyze(req.alert)
        triage = result.triage_result
        top_trace = result.route_trace[-1] if result.route_trace else None

        fp = result.alert_fingerprint
        fingerprint = {k: v for k, v in fp.model_dump().items() if v} if fp else {}

        decision = triage.proposed_decision if triage else "escalated"
        confidence = round(triage.triage_confidence * 100, 1) if triage else 0.0
        requires_human = triage.requires_human_approval if triage else True
        escalation_reason = triage.escalation_reason if triage else ""
        memory_hit_count = len(triage.supporting_matches) if triage else 0

        memory_bypassed = top_trace.llm_skipped if top_trace else False
        escalated = top_trace.escalated if top_trace else True
        cost_usd = sum(t.estimated_cost_usd for t in result.route_trace)
        baseline_usd = sum(
            t.strong_model_baseline_cost_usd for t in result.route_trace
        )
        savings_usd = max(0.0, baseline_usd - cost_usd)
        latency_ms = sum(t.latency_ms for t in result.route_trace)
        router_model = top_trace.model if top_trace else "unknown"

        root_causes = [
            {
                "cause": rc.get("cause", ""),
                "evidence": rc.get("evidence", ""),
                "confidence": rc.get("confidence", 0),
            }
            for rc in result.likely_root_causes
        ]

        prior_incidents: list[dict] = []
        for m in result.memory_matches[:3]:
            md = m.get("metadata", {}) if isinstance(m, dict) else (m.metadata or {})
            prior_incidents.append(
                {
                    "title": (
                        m.get("title", "") if isinstance(m, dict) else m.title
                    ),
                    "score": (
                        m.get("score", 0) if isinstance(m, dict) else m.score
                    ),
                    "decision": md.get("triage_decision", "unknown"),
                }
            )

        # Build human-readable agent steps from the structured trace.
        fp_summary = (
            ", ".join(f"{k}: {v}" for k, v in list(fingerprint.items())[:3])
            if fingerprint
            else "no fingerprint"
        )
        steps = [
            f"Normalizing alert. Service: {result.incident.service}. Severity: {result.incident.severity}.",
            f"Fingerprinting alert. {fp_summary}.",
            "Querying Hindsight memory bank for similar incidents.",
        ]
        if memory_hit_count > 0 and prior_incidents:
            top = prior_incidents[0]
            steps.append(
                f"Found {memory_hit_count} memory match"
                f"{'es' if memory_hit_count != 1 else ''}. "
                f"Closest: \"{top['title']}\" (score: {top['score']:.2f})."
            )
        else:
            steps.append("No strong memory match found. Treating as a novel pattern.")

        if memory_bypassed:
            steps.append(
                f"Memory confidence sufficient. Strong LLM bypassed. "
                f"Saved ${savings_usd:.4f} on this alert."
            )
        else:
            steps.append(
                f"Routing to {router_model} for deep analysis. "
                f"Cost: ${cost_usd:.4f}."
            )

        steps.append(
            f"Triage decision: {decision.replace('_', ' ').title()} "
            f"({confidence}% confidence)."
        )

        if result.likely_root_causes:
            rc = result.likely_root_causes[0]
            cause = rc.get("cause", "")
            if cause:
                steps.append(
                    f"Root cause identified: "
                    f"{cause[:120]}{'...' if len(cause) > 120 else ''}"
                )

        if requires_human:
            reason = escalation_reason or "policy threshold"
            steps.append(f"Human approval required before remediation. Reason: {reason}.")
        else:
            steps.append("Decision within auto-remediation threshold. Review and act.")

        # ── Structured route + audit trace (so the cockpit can render an audit panel) ─
        route_trace_payload = [
            {
                "step": t.step,
                "model": t.model,
                "route_reason": t.route_reason,
                "confidence": t.confidence,
                "latency_ms": t.latency_ms,
                "estimated_cost_usd": t.estimated_cost_usd,
                "strong_model_baseline_cost_usd": t.strong_model_baseline_cost_usd,
                "savings_vs_strong_usd": t.savings_vs_strong_usd,
                "escalated": t.escalated,
                "live_model_call": t.live_model_call,
                "model_error": t.model_error,
                "llm_skipped": t.llm_skipped,
                "budget_exhausted": t.budget_exhausted,
            }
            for t in result.route_trace
        ]
        audit_trace_payload = [
            {
                "step": e.step,
                "model": e.model,
                "route_reason": e.route_reason,
                "memory_hit_count": e.memory_hit_count,
                "proposed_decision": e.proposed_decision,
                "escalation_reason": e.escalation_reason,
                "live_model_call": e.live_model_call,
                "llm_skipped": e.llm_skipped,
                "cost_usd": e.cost_usd,
                "baseline_cost_usd": e.baseline_cost_usd,
                "savings_usd": e.savings_usd,
                # AuditTraceEntry has no latency_ms; carry it from the matching
                # RouteTrace step so the cockpit can render per-step timing.
                "latency_ms": result.route_trace[i].latency_ms if i < len(result.route_trace) else 0.0,
            }
            for i, e in enumerate(result.audit_trace)
        ]

        return {
            # Agent reasoning trace (stringly-typed for the chat bubble)
            "steps": steps,
            # Incident context
            "service": result.incident.service,
            "environment": result.incident.environment,
            "severity": result.incident.severity,
            "incident_type": result.incident_type,
            "impact_level": result.impact_level,
            "blast_radius": result.blast_radius_guess,
            # Fingerprint
            "fingerprint": fingerprint,
            # Triage
            "decision": decision.replace("_", " ").title(),
            "decision_raw": decision,
            "confidence": confidence,
            "requires_human_approval": requires_human,
            "escalation_reason": escalation_reason,
            # Memory / routing
            "memory_bypassed": memory_bypassed,
            "memory_hit_count": memory_hit_count,
            "escalated": escalated,
            "router_model": router_model,
            "prior_incidents": prior_incidents,
            "memory_reflection": result.memory_reflection,
            # Cost
            "cost_usd": round(cost_usd, 6),
            "savings_usd": round(savings_usd, 6),
            "latency_ms": round(latency_ms, 1),
            # SOC actionables
            "root_causes": root_causes,
            "verification_commands": result.verification_commands,
            "remediation_suggestions": result.remediation_suggestions,
            "containment_notes": result.containment_notes,
            "evidence_to_preserve": result.evidence_to_preserve,
            "dead_ends": result.dead_ends,
            "postmortem_action_items": result.postmortem_action_items,
            # Structured trace for the audit panel
            "route_trace": route_trace_payload,
            "audit_trace": audit_trace_payload,
            # System
            "fallback_mode": result.fallback_mode,
            "hindsight_status": result.hindsight_status,
        }
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


# ── Retain (closes the learning loop) ────────────────────────────────────────
@app.post("/retain")
def retain(req: RetainRequest) -> dict:
    try:
        fp: AlertFingerprint | None = None
        if req.fingerprint:
            try:
                fp = AlertFingerprint(**req.fingerprint)
            except Exception:  # noqa: BLE001 — best-effort fingerprint parse
                fp = None

        fp_canonical = format_fingerprint(fp) if fp else "unknown fingerprint"
        content = (
            f"Triage decision for {req.service}: {req.decision}.\n"
            f"Alert fingerprint: {fp_canonical}\n"
            f"Raw alert: {req.raw_alert}\n"
            f"Dead ends:\n" + "\n".join(f"- {d}" for d in req.dead_ends)
        )
        if req.analyst_note:
            content += f"\nAnalyst note: {req.analyst_note}"

        mem_status = mem.retain(
            content,
            fingerprint=fp,
            decision=req.decision,
            dead_ends=req.dead_ends,
        )

        return {"status": "retained", "hindsight_response": mem_status}
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))
