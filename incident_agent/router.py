from __future__ import annotations

import json
import os
import time
from typing import Any

from .models import RouteTrace


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

    def rca_with_trace(
        self,
        incident: dict[str, Any],
        memories: list[str],
        confidence: float,
        security_relevant: bool,
    ) -> tuple[dict[str, Any] | None, RouteTrace]:
        escalate = confidence < 0.65 or security_relevant
        model = self.strong_model if escalate else self.cheap_model
        reason = (
            "weak memory match or security relevance requires stronger RCA"
            if escalate
            else "strong memory match keeps route on cheap model"
        )
        prompt = (
            "Produce strict JSON for incident RCA. Keys: likely_root_causes (array of {cause,evidence,confidence}), "
            "verification_commands, remediation_suggestions, containment_notes, postmortem_action_items. Prefer evidence-backed steps.\n\n"
            f"Incident: {json.dumps(incident)}\nSimilar memories:\n"
            + "\n---\n".join(memories[:4])
        )
        content, trace = self._call_model(
            "RCA investigation", model, prompt, confidence, reason, escalated=escalate
        )
        try:
            return json.loads(_json_object(content)), trace
        except Exception:
            return None, trace

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
        if self.api_key and self.live_groq:
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
            except Exception as exc:
                model_error = exc.__class__.__name__
                content = json.dumps({"model_error": model_error})
        latency_ms = (time.perf_counter() - start) * 1000
        if self.live_groq and not self.api_key:
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
            budget_remaining_usd=max(0.0, round(self.run_budget - estimated_cost, 5)),
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
                "temperature": 0.1,
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
