from __future__ import annotations

import json
import os
import time
from typing import Any

from .models import AlertFingerprint, MemoryMatch, RouteTrace, TriageResult


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class CascadeFlowRouter:
    """Small cascadeflow harness adapter plus Groq model routing."""

    def __init__(self) -> None:
        self.cheap_model = os.getenv("CASCADEFLOW_CHEAP_MODEL", "qwen/qwen3-32b")
        self.strong_model = os.getenv("CASCADEFLOW_STRONG_MODEL", "openai/gpt-oss-120b")
        self.mode = os.getenv("CASCADEFLOW_MODE", "observe")
        self.run_budget = float(os.getenv("CASCADEFLOW_RUN_BUDGET_USD", "0.02"))
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.live_groq = os.getenv("CASCADEFLOW_LIVE_GROQ", "false").lower() == "true"
        self.status = "cascadeflow not initialized"
        self.cascadeflow_enabled = False
        self.cascadeflow: Any | None = None
        # Cumulative live-cost tracking and budget enforcement (Task 9.3 / R6.6 / P14).
        self._cum_live_cost: float = 0.0
        self._budget_exhausted: bool = False
        self._init_cascadeflow()

    def _init_cascadeflow(self) -> None:
        try:
            import cascadeflow  # type: ignore

            cascadeflow.init(mode=self.mode)
            self.cascadeflow = cascadeflow
            self.cascadeflow_enabled = True
            self.status = f"cascadeflow initialized in {self.mode} mode"
        except Exception:
            self.cascadeflow = None
            self.cascadeflow_enabled = False
            self.status = "cascadeflow import/init failed; using explicit trace fallback"

    def normalize_with_trace(
        self, raw_alert: str
    ) -> tuple[dict[str, Any] | None, RouteTrace]:
        prompt = (
            "Normalize this SRE/security alert as strict JSON with keys service, environment, severity, "
            "timestamp, error_type, affected_dependency, suspected_recent_change, security_relevance.\n\n"
            f"Alert:\n{raw_alert}"
        )
        content, trace = self._call_model(
            "alert normalization",
            self.cheap_model,
            prompt,
            0.72,
            "cheap model is sufficient for structured extraction",
        )
        try:
            return json.loads(_json_object(content)), trace
        except Exception:
            return None, trace

    def fingerprint_with_trace(
        self, raw_alert: str
    ) -> tuple[dict[str, Any] | None, RouteTrace]:
        """Cheap-model JSON extract for the six AlertFingerprint fields (Task 9.1, R3.2/R3.5)."""
        prompt = (
            "Extract a structured 'alert DNA' fingerprint from the signal below "
            "as strict JSON. Output rules:\n"
            "  - Return ONLY the JSON object, no prose.\n"
            "  - All six keys MUST be present: error_class, service_role, "
            "dependency_pattern, signal_shape, attack_pattern, environment.\n"
            "  - All values MUST be lowercase, ASCII-only, no extra whitespace.\n"
            "  - All values MUST be short canonical phrases (1-3 words max, "
            "max 30 chars). Do NOT include version numbers, deploy hashes, "
            "timestamps, region names, or commit IDs.\n"
            "  - If a field cannot be determined from the alert text, return "
            "an empty string \"\".\n"
            "  - attack_pattern MUST be a security signature (e.g. "
            "\"sql injection\", \"credential stuffing\", \"jwt\", \"xss\", "
            "\"csrf\"). If the alert is NOT security-related, "
            "attack_pattern MUST be \"\". Do NOT put deploy events, "
            "feature flags, or operational signals here.\n"
            "  - signal_shape is the symptom shape (e.g. \"crashloop\", "
            "\"5xx\", \"timeout\", \"latency\", \"oom\"). Not free-text prose.\n"
            "  - error_class is a short error category (e.g. \"keyerror\", "
            "\"crashloopbackoff\", \"connectiontimeout\"), not a full message.\n"
            "  - dependency_pattern is one of: postgres, database, redis, "
            "smtp, stripe, identity, jwks, configmap, feature flag, or empty.\n"
            "  - environment is one of: production, prod, staging, dev, qa.\n\n"
            f"Alert:\n{raw_alert}"
        )
        content, trace = self._call_model(
            "alert fingerprint",
            self.cheap_model,
            prompt,
            0.7,
            "cheap model is sufficient for structured fingerprint extraction",
        )
        try:
            return json.loads(_json_object(content)), trace
        except Exception:
            return None, trace

    def rca_with_trace(
        self,
        incident: dict[str, Any],
        memories: list[str],
        confidence: float,
        security_relevant: bool,
        *,
        dead_ends: list[str] | None = None,
        force_strong_model: bool = False,
    ) -> tuple[dict[str, Any] | None, RouteTrace]:
        # ``force_strong_model`` lets the workflow respect the triage decision
        # directly: when the TriageEngine proposes ``escalated`` or ``real``,
        # the router MUST use the strong model regardless of memory match score
        # or security relevance heuristics (R6.2, R6.3).
        escalate = force_strong_model or confidence < 0.65 or security_relevant
        model = self.strong_model if escalate else self.cheap_model
        if force_strong_model:
            reason = "triage decision requires strong-model RCA"
        elif escalate:
            reason = (
                "weak memory match or security relevance requires stronger RCA"
            )
        else:
            reason = "strong memory match keeps route on cheap model"
        dead_ends_section = ""
        if dead_ends:
            bullets = "\n".join(f"- {d}" for d in dead_ends[:8])
            dead_ends_section = (
                "\nSkip these dead ends (already disproven on similar prior incidents):\n"
                + bullets
            )
        prompt = (
            "Produce strict JSON for incident RCA. Keys: likely_root_causes (array of {cause,evidence,confidence}), "
            "verification_commands, remediation_suggestions, containment_notes, postmortem_action_items. Prefer evidence-backed steps.\n\n"
            f"Incident: {json.dumps(incident)}\nSimilar memories:\n"
            + "\n---\n".join(memories[:4])
            + dead_ends_section
        )
        content, trace = self._call_model(
            "RCA investigation", model, prompt, confidence, reason, escalated=escalate
        )
        try:
            return json.loads(_json_object(content)), trace
        except Exception:
            return None, trace

    def triage_with_trace(
        self,
        fingerprint: AlertFingerprint,
        triage_result: TriageResult,
        matches: list[MemoryMatch],
    ) -> RouteTrace:
        """Build a synthetic memory-bypass RouteTrace for an alert that skips the LLM.

        Property 6 + Property 15 require this entry to exist in route_trace whenever
        the strong-model call is bypassed, so the audit panel and cost curve see the
        bypass and can still report a savings figure against the strong-model
        baseline.
        """
        titles = "; ".join(m.title for m in matches[:4]) or "no titles"
        n = len(matches)
        # Approximate baseline using the same prompt-shape we would have sent for RCA.
        baseline_prompt = (
            "Produce strict JSON for incident RCA. Keys: likely_root_causes (array of {cause,evidence,confidence}), "
            "verification_commands, remediation_suggestions, containment_notes, postmortem_action_items. "
            "Prefer evidence-backed steps.\n\nIncident: {fingerprint_canonical}\nSimilar memories:\n"
            + "\n---\n".join(m.content for m in matches[:4])
        )
        baseline_cost = estimate_cost(baseline_prompt, self.strong_model)
        top_score = matches[0].score if matches else 0.0
        consistency = (
            triage_result.consistent_decision_count / n
            if n > 0 and triage_result.consistent_decision_count > 0
            else 0.0
        )
        return RouteTrace(
            step="auto-triage bypass",
            model="memory-bypass",
            provider="openrecall",
            route_reason=(
                f"memory consistent across {triage_result.consistent_decision_count} "
                f"prior decisions: {titles}"
            ),
            confidence=round(triage_result.triage_confidence, 4),
            latency_ms=0.0,
            estimated_cost_usd=0.0,
            strong_model_baseline_cost_usd=baseline_cost,
            savings_vs_strong_usd=baseline_cost,
            escalated=False,
            cascadeflow_enabled=self.cascadeflow_enabled,
            live_model_call=False,
            model_error=None,
            budget_remaining_usd=max(0.0, round(self.run_budget - self._cum_live_cost, 5)),
            triage_decision_proposed=triage_result.proposed_decision,
            memory_match_score=round(top_score, 4),
            decision_consistency=round(consistency, 4),
            llm_skipped=True,
            budget_exhausted=self._budget_exhausted,
        )

    def _call_model(
        self,
        step: str,
        model: str,
        prompt: str,
        confidence: float,
        reason: str,
        escalated: bool = False,
    ) -> tuple[str, RouteTrace]:
        start = time.perf_counter()
        estimated_cost = estimate_cost(prompt, model)
        baseline_cost = estimate_cost(prompt, self.strong_model)
        content = "{}"
        live_call = False
        model_error = None
        budget_exhausted_now = False

        if self.api_key and self.live_groq:
            # Best-effort budget enforcement: allow the in-flight call when the
            # budget is hit, but suppress further live calls afterwards.
            if self._budget_exhausted:
                budget_exhausted_now = True
            else:
                try:
                    if self.cascadeflow_enabled and self.cascadeflow is not None:
                        with self.cascadeflow.run(
                            budget=self.run_budget,
                            max_latency_ms=4500,
                            kpi_weights={"quality": 0.55, "cost": 0.30, "latency": 0.15},
                        ):
                            content = self._groq_chat(model, prompt)
                    else:
                        content = self._groq_chat(model, prompt)
                    live_call = True
                    self._cum_live_cost += estimated_cost
                    if self._cum_live_cost + estimated_cost > self.run_budget:
                        self._budget_exhausted = True
                except Exception as exc:
                    model_error = exc.__class__.__name__
                    content = json.dumps({"model_error": model_error})

        latency_ms = (time.perf_counter() - start) * 1000

        if budget_exhausted_now:
            route_reason = "run budget exhausted; deterministic fallback"
        elif self.live_groq and not self.api_key:
            route_reason = f"{reason}; live Groq requested but GROQ_API_KEY is missing"
        elif self.live_groq:
            route_reason = reason
        else:
            route_reason = f"{reason}; deterministic demo mode avoids live Groq rate limits"

        trace = RouteTrace(
            step=step,
            model=model,
            route_reason=route_reason,
            confidence=round(confidence, 2),
            latency_ms=round(latency_ms, 1),
            estimated_cost_usd=estimated_cost,
            strong_model_baseline_cost_usd=baseline_cost,
            savings_vs_strong_usd=max(0.0, round(baseline_cost - estimated_cost, 6)),
            escalated=escalated,
            cascadeflow_enabled=self.cascadeflow_enabled,
            live_model_call=live_call,
            model_error=model_error,
            budget_remaining_usd=max(0.0, round(self.run_budget - self._cum_live_cost, 5)),
            budget_exhausted=budget_exhausted_now or self._budget_exhausted,
        )
        return content, trace

    def _groq_chat(self, model: str, prompt: str) -> str:
        import httpx

        response = httpx.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                # Temperature 0 for maximum determinism on structured-extract
                # tasks (fingerprint, normalize). Groq supports temperature=0;
                # higher values cause subtle field-value drift across calls
                # for the same alert text.
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


def estimate_cost(prompt: str, model: str) -> float:
    tokens = max(1, len(prompt) // 4)
    per_million = 0.10 if "qwen" in model.lower() else 0.75
    return round(tokens / 1_000_000 * per_million, 6)


def _json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return "{}"
    return text[start : end + 1]
