from __future__ import annotations

import re
from typing import Any

from .memory import IncidentMemory
from .models import (
    AnalysisResult,
    IncidentObject,
    IncidentType,
    MemoryMatch,
    RouteTrace,
    utc_now,
)
from .router import CascadeFlowRouter


class IncidentWorkflow:
    def __init__(self, memory: IncidentMemory, router: CascadeFlowRouter) -> None:
        self.memory = memory
        self.router = router

    def analyze(self, raw_alert: str) -> AnalysisResult:
        llm_incident, normalize_trace = self.router.normalize_with_trace(raw_alert)
        incident = self._normalize(raw_alert, llm_incident)
        incident_type = self._classify(incident, raw_alert)
        impact = self._impact(incident, raw_alert)
        evidence = self._evidence_to_preserve(incident_type, incident)
        recall_query = f"{incident.service} {incident.error_type} {incident.affected_dependency or ''} {incident.suspected_recent_change or ''} {raw_alert}"
        matches = self.memory.recall(recall_query, limit=5)
        reflection = self.memory.reflect(
            f"Reflect on repeated incident patterns and useful lessons for: {recall_query}",
            matches,
        )
        match_confidence = self._effective_confidence(raw_alert, matches)
        rca_json, rca_trace = self.router.rca_with_trace(
            incident.model_dump(),
            [m.content for m in matches],
            match_confidence,
            incident_type in {"Security", "Hybrid"},
        )
        deterministic = self._deterministic_rca(incident, matches, incident_type)
        merged = merge_rca(deterministic, rca_json)
        return AnalysisResult(
            incident=incident,
            incident_type=incident_type,
            impact_level=impact,
            blast_radius_guess=self._blast_radius(incident, raw_alert),
            evidence_to_preserve=evidence,
            memory_matches=[model_to_dict(match) for match in matches],
            memory_reflection=reflection,
            likely_root_causes=merged["likely_root_causes"],
            verification_commands=merged["verification_commands"],
            remediation_suggestions=merged["remediation_suggestions"],
            containment_notes=merged["containment_notes"],
            roles={
                "incident_commander": "Own severity, decision log, and handoffs",
                "operations_lead": "Run verification commands and coordinate remediation",
                "communications": "Publish status updates and stakeholder notes",
                "scribe": "Maintain timeline and evidence references",
            },
            timeline_notes=[
                f"{utc_now()} alert received and normalized",
                "Detection/analysis: compare current symptoms with Hindsight incident memory",
                "Containment: choose lowest-impact reversible action after human approval",
                "Post-incident: retain final RCA, commands, and lessons learned",
            ],
            postmortem_action_items=merged["postmortem_action_items"],
            route_trace=[model_to_dict(normalize_trace), model_to_dict(rca_trace)],
            hindsight_status=self.memory.status,
            fallback_mode=self.memory.fallback_mode,
        )

    def _effective_confidence(
        self, raw_alert: str, matches: list[MemoryMatch]
    ) -> float:
        confidence = matches[0].score if matches else 0.0
        ambiguous_markers = [
            "ambiguous",
            "no obvious",
            "intermittent",
            "unknown owner",
            "multiple possible",
        ]
        if any(marker in raw_alert.lower() for marker in ambiguous_markers):
            return min(confidence, 0.55)
        return confidence

    def _normalize(self, raw: str, llm: dict[str, Any] | None) -> IncidentObject:
        data = {k: v for k, v in (llm or {}).items() if v}
        text = raw.lower()
        service = (
            data.get("service")
            or pick(r"([a-z0-9-]+(?:service|api|gateway|frontend|worker|waf))", text)
            or pick(r"service[=: ]+([a-z0-9-]+)", text)
            or pick_known_service(text)
            or "unknown-service"
        )
        env = (
            data.get("environment")
            or pick(r"\b(prod|production|staging|dev|qa)\b", text)
            or "production"
        )
        severity = (
            data.get("severity")
            or pick(r"\b(sev-[0-4]|p[0-4]|critical|high|medium|low)\b", text)
            or (
                "SEV-2"
                if any(w in text for w in ["critical", "5xx", "outage"])
                else "SEV-3"
            )
        )
        error_type = data.get("error_type") or infer_error_type(text)
        dep = data.get("affected_dependency") or infer_dependency(text)
        change = data.get("suspected_recent_change") or infer_change(text)
        security = data.get("security_relevance") or (
            "high"
            if any(
                w in text
                for w in [
                    "sql injection",
                    "credential stuffing",
                    "jwt",
                    "suspicious",
                    "waf",
                ]
            )
            else "none"
        )
        return IncidentObject(
            service=str(service),
            environment=str(env),
            severity=str(severity).upper(),
            timestamp=str(data.get("timestamp") or utc_now()),
            error_type=str(error_type),
            affected_dependency=dep,
            suspected_recent_change=change,
            security_relevance=str(security),
            raw_alert=raw,
        )

    def _classify(self, incident: IncidentObject, raw: str) -> IncidentType:
        text = f"{raw} {incident.error_type} {incident.security_relevance}".lower()
        sec = any(
            w in text
            for w in [
                "sql injection",
                "credential",
                "jwt",
                "suspicious",
                "waf",
                "attack",
                "auth failure",
            ]
        )
        sre = any(
            w in text
            for w in [
                "crashloop",
                "oom",
                "5xx",
                "timeout",
                "pool",
                "probe",
                "deploy",
                "latency",
                "401",
                "validation failure",
                "key rotation",
            ]
        )
        return "Hybrid" if sec and sre else "Security" if sec else "SRE"

    def _impact(self, incident: IncidentObject, raw: str) -> str:
        text = raw.lower()
        if (
            incident.severity in {"SEV-0", "SEV-1", "CRITICAL", "P0", "P1"}
            or "checkout" in text
            or "payments" in text
        ):
            return "High: customer-facing or revenue-path degradation"
        if "5xx" in text or "crashloop" in text or "login" in text:
            return "Medium: user-visible degradation likely"
        return "Low/Medium: confirm affected users before escalation"

    def _blast_radius(self, incident: IncidentObject, raw: str) -> str:
        if incident.environment.lower() in {
            "prod",
            "production",
        } and incident.service in {
            "api-gateway",
            "frontend",
            "checkout-service",
            "payments-api",
        }:
            return "Broad: production edge or revenue-path service"
        if incident.affected_dependency:
            return f"Potentially shared dependency impact via {incident.affected_dependency}"
        return "Likely bounded to the named service until dependency checks prove otherwise"

    def _evidence_to_preserve(
        self, incident_type: str, incident: IncidentObject
    ) -> list[str]:
        base = [
            "Alert payload and dedup/grouping key",
            "Deployment diff, config diff, and feature flag state at alert time",
            "Pod events, container restart history, and logs around first failure",
        ]
        if incident_type in {"Security", "Hybrid"}:
            base.extend(
                [
                    "Original request samples, WAF/SIEM event IDs, source IP/user-agent evidence",
                    "Auth logs and affected account IDs without modifying them",
                ]
            )
        return base

    def _deterministic_rca(
        self, incident: IncidentObject, matches: list[MemoryMatch], incident_type: str
    ) -> dict[str, list[Any]]:
        t = f"{incident.raw_alert} {incident.error_type} {incident.affected_dependency or ''}".lower()
        cause = "Recent configuration or deployment regression"
        commands = [
            f"kubectl -n {incident.environment} describe deploy/{incident.service}",
            f"kubectl -n {incident.environment} logs deploy/{incident.service} --previous --tail=200",
        ]
        remediation = [
            "Have the operations lead verify the hypothesis before changing state",
            "Roll back the last config/deploy change if verification confirms regression",
        ]
        containment = [
            "Freeze further deploys to affected service",
            "Route status updates through incident commander",
        ]
        actions = [
            "Add runbook entry for this signature",
            "Add alert annotation linking symptom to final RCA",
        ]
        if "crashloop" in t or "env" in t or "configmap" in t:
            cause = "Container crash from missing/bad configuration value"
            commands += [
                f'kubectl -n {incident.environment} get configmap -o yaml | grep -n "{incident.service}"',
                f"kubectl -n {incident.environment} get events --sort-by=.lastTimestamp | grep {incident.service}",
            ]
            remediation += [
                "Restore the missing ConfigMap/Secret key or roll back the release",
                "Restart only affected pods after config is corrected",
            ]
        elif "oom" in t:
            cause = "OOM kill from memory limit or traffic increase"
            commands += [
                f"kubectl -n {incident.environment} top pod -l app={incident.service}",
                f"kubectl -n {incident.environment} describe pod -l app={incident.service} | grep -i oom -C 3",
            ]
            remediation += [
                "Tune memory limit/request or revert memory-heavy build after confirming heap growth"
            ]
        elif "pool" in t or "db" in t or "database" in t:
            cause = "Database connection pool exhaustion"
            commands += [
                "kubectl logs deploy/"
                + incident.service
                + " | grep -i 'pool\\|connection'",
                'psql -c "select state,count(*) from pg_stat_activity group by 1;"',
            ]
            remediation += [
                "Reduce client pool size or scale database capacity after checking active sessions"
            ]
        elif "timeout" in t or "redis" in t:
            cause = "Downstream dependency timeout"
            commands += [
                "kubectl get endpoints",
                f"kubectl -n {incident.environment} logs deploy/{incident.service} | grep -i timeout",
            ]
            remediation += [
                "Enable retry/backoff guardrails and fail open/closed according to service runbook"
            ]
        elif incident_type in {"Security", "Hybrid"}:
            cause = "Security signal requiring enrichment before containment"
            commands += [
                "Query SIEM for matching source IPs, users, and request IDs",
                "Export WAF/auth logs for the alert window",
            ]
            remediation = [
                "Preserve evidence, enrich indicators, and escalate to security owner",
                "Apply targeted rate limit/block rule only after validating false positive risk",
            ]
            containment += [
                "Do not rotate keys or block broad ranges until impact and indicators are confirmed"
            ]
        if matches:
            cause = f"{cause}; closest memory suggests: {matches[0].title}"
            evidence = (
                "Matched alert terms, recent change hints, and recalled incident memory"
            )
        else:
            evidence = (
                "No close incident memory matched; hypothesis is based on current alert terms only"
            )
        return {
            "likely_root_causes": [
                {
                    "cause": cause,
                    "evidence": evidence,
                    "confidence": round(matches[0].score if matches else 0.55, 2),
                }
            ],
            "verification_commands": unique(commands),
            "remediation_suggestions": unique(remediation),
            "containment_notes": unique(containment),
            "postmortem_action_items": unique(actions),
        }


def merge_rca(
    base: dict[str, list[Any]], llm: dict[str, Any] | None
) -> dict[str, list[Any]]:
    if not llm or "model_error" in llm:
        return base
    for key in base:
        val = llm.get(key)
        if isinstance(val, list) and val:
            base[key] = normalize_llm_list(key, val)
    return base


def model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return dict(value)


def normalize_llm_list(key: str, values: list[Any]) -> list[Any]:
    if key == "likely_root_causes":
        normalized_causes = []
        for item in values[:6]:
            if isinstance(item, dict):
                normalized_causes.append(
                    {
                        "cause": str(item.get("cause", "Unknown cause")),
                        "evidence": stringify_list_item(
                            item.get("evidence", "Evidence pending")
                        ),
                        "confidence": item.get("confidence", "n/a"),
                    }
                )
            else:
                normalized_causes.append(
                    {
                        "cause": str(item),
                        "evidence": "Evidence pending",
                        "confidence": "n/a",
                    }
                )
        return normalized_causes
    return [stringify_list_item(item) for item in values[:6]]


def stringify_list_item(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, list):
        return "; ".join(stringify_list_item(value) for value in item)
    if isinstance(item, dict):
        parts = [f"{key}: {value}" for key, value in item.items() if value]
        return "; ".join(parts) if parts else str(item)
    return str(item)


def pick(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


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


def infer_change(text: str) -> str | None:
    for phrase in [
        "after deploy",
        "new release",
        "key rotation",
        "feature flag",
        "configmap",
        "migration",
        "node restart",
    ]:
        if phrase in text:
            return phrase
    return None


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
