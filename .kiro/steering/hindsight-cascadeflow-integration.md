---
inclusion: fileMatch
fileMatchPattern: ["**/memory.py", "**/router.py", "**/workflow.py", "**/fingerprint.py"]
---

# OpenRecall — Hindsight + cascadeflow Integration Steering

## Memory backend (Hindsight Cloud first, local JSON fallback)

`incident_agent/memory.py` is the single integration point with Hindsight
Cloud. It must obey four contracts:

### 1. Initialization (R11.1, R11.2, R12.1, R12.5)

```python
def _init_hindsight(self) -> None:
    self.api_key = os.getenv("HINDSIGHT_API_KEY", "").strip()
    if not self.api_key:
        self.client = None
        self.fallback_mode = True
        self.status = "fallback mode: HINDSIGHT_API_KEY unset"
        return
    try:
        # Health probe: HEAD with 2s timeout. 401/403 means host-up.
        # Only connection error / 5xx flip to fallback.
        response = httpx.head(self.base_url, timeout=2,
                              headers={"Authorization": f"Bearer {self.api_key}"},
                              follow_redirects=True)
        if response.status_code >= 500:
            raise RuntimeError(...)
        self.client = _build_hindsight_client(self.base_url, self.api_key)
        self.fallback_mode = False
        ...
    except Exception as exc:
        self.client = None
        self.fallback_mode = True
        self.status = f"fallback mode: Hindsight Cloud unreachable ({exc.__class__.__name__})"
```

### 2. Per-request failure → close client for the session (R11.3)

```python
def _flip_to_fallback(self, exc: Exception, where: str) -> None:
    self.fallback_mode = True
    self.status = f"fallback mode: Hindsight {where} failed ({exc.__class__.__name__})"
    if self.client is not None:
        close = getattr(self.client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        self.client = None
```

Every recall/retain/reflect call wraps Hindsight in `try/except Exception`
and routes failures through `_flip_to_fallback`. The client must NOT survive
the failure — subsequent calls take the local-fallback branch.

### 3. SDK API key probe (design §Hindsight Cloud Client Wiring)

```python
def _build_hindsight_client(base_url: str, api_key: str) -> Any:
    from hindsight_client import Hindsight  # type: ignore
    try:
        return Hindsight(base_url=base_url, api_key=api_key)  # native
    except TypeError:
        client = Hindsight(base_url=base_url)
        underlying = getattr(client, "_client", None) or getattr(client, "client", None)
        if underlying is not None and api_key:
            try:
                underlying.headers["Authorization"] = f"Bearer {api_key}"
            except Exception:
                pass
        return client
```

This dual-path probe makes OpenRecall compatible with multiple
`hindsight-client` SDK versions.

### 4. Idempotent retain (R8.3, P7)

The dedupe key is:

```python
dedupe_key = (
    format_fingerprint(fingerprint) if fingerprint else "",
    decision or "",
    sha256(content.encode("utf-8")).hexdigest(),
)
```

In-process: `self._dedupe_index: set[tuple[str, str, str]]`.
On-disk: re-check `data/local_memory.json` via `_match_local_dedupe(...)`
because the file persists across processes.

## Router contract (cascadeflow + Groq)

`incident_agent/router.py` is the integration point with cascadeflow and Groq.

### Required methods

| Method | Returns | Purpose |
|---|---|---|
| `normalize_with_trace(raw_alert)` | `(dict|None, RouteTrace)` | Cheap-model alert normalization → `IncidentObject` JSON. |
| `fingerprint_with_trace(raw_alert)` | `(dict|None, RouteTrace)` | Cheap-model fingerprint extraction (six fields). |
| `rca_with_trace(incident, memories, confidence, security_relevant, *, dead_ends, force_strong_model)` | `(dict|None, RouteTrace)` | RCA generation. `force_strong_model=True` overrides the cheap/strong heuristic per R6.2/R6.3 when triage proposes `escalated` or `real`. |
| `triage_with_trace(fp, triage_result, matches)` | `RouteTrace` | Synthetic memory-bypass entry. Never makes a network call. |

### Synthetic memory-bypass RouteTrace (P6, P15)

```python
RouteTrace(
    step="auto-triage bypass",
    model="memory-bypass",
    provider="openrecall",
    route_reason=f"memory consistent across {n} prior decisions: {titles}",
    confidence=triage_result.triage_confidence,
    latency_ms=0.0,
    estimated_cost_usd=0.0,
    strong_model_baseline_cost_usd=baseline_cost,  # what we WOULD have paid
    savings_vs_strong_usd=baseline_cost,           # full baseline saved
    escalated=False,
    cascadeflow_enabled=self.cascadeflow_enabled,
    live_model_call=False,
    model_error=None,
    budget_remaining_usd=...,
    triage_decision_proposed=triage_result.proposed_decision,
    memory_match_score=top_score,
    decision_consistency=consistency,
    llm_skipped=True,                              # P6 invariant
    budget_exhausted=self._budget_exhausted,
)
```

The `model="memory-bypass"` is a sentinel string, not a real Groq model.
P6 + P15 + R10.3 all reference this string verbatim.

### Budget enforcement (R6.6, P14)

```python
self._cum_live_cost: float = 0.0
self._budget_exhausted: bool = False

# inside _call_model, after a successful live call:
self._cum_live_cost += estimated_cost
if self._cum_live_cost + estimated_cost > self.run_budget:
    self._budget_exhausted = True

# subsequent calls when self._budget_exhausted is True:
#   live_model_call=False, budget_exhausted=True,
#   route_reason="run budget exhausted; deterministic fallback"
```

The "in-flight call when budget hits" rule of P14: the call that crosses
the threshold IS allowed to complete. Only future calls are suppressed.

## Workflow integration contract

`incident_agent/workflow.py` orchestrates:

```
analyze(raw_alert):
  1. router.normalize_with_trace        → normalize_trace
  2. fingerprint_generator.generate     → fingerprint_trace (NEW per OpenRecall)
  3. memory.recall_by_fingerprint(fp)   → matches
  4. memory.reflect(...)                → reflection
  5. triage_engine.triage(fp, matches)  → triage_result

  if bypass condition:
    6a. router.triage_with_trace(...)   → bypass_trace (NEW, llm_skipped=True)
    7a. cost_tracker.record(idx, 0.0, baseline)        # R9.4
  else:
    6b. router.rca_with_trace(..., force_strong_model=triage_result.proposed_decision in {"escalated","real"})
    7b. cost_tracker.record(idx, sum_cost, sum_baseline)

  8. deterministic_rca + merge_rca      # always runs so verification commands exist
  9. AuditTraceRecorder.build           # one entry per route_trace step (P15)
 10. return AnalysisResult(...)
```

### Bypass condition (verbatim from `BYPASS_CONFIDENCE_THRESHOLD`)

```python
bypass = (
    triage_result.proposed_decision in {"false_positive", "duplicate", "known_benign"}
    and triage_result.triage_confidence >= BYPASS_CONFIDENCE_THRESHOLD
    and not fingerprint.attack_pattern   # security-novel kill switch
)
```

### Force-strong rule (R6.2, R6.3)

When triage proposes `escalated` or `real`, the workflow passes
`force_strong_model=True` to `rca_with_trace`. The router uses the strong
model regardless of the cheap/strong heuristic.

## When to flip the mode badges

The cockpit's badge row reflects three runtime flags:

- `Hindsight connected` vs `Fallback memory` — driven by
  `result.fallback_mode` (mirror of `mem.fallback_mode`).
- `Live model calls` vs `Deterministic model output` — driven by
  `any(t.live_model_call for t in result.route_trace)`.
- `Standard route` vs `Escalated route` — driven by
  `result.route_trace[-1].escalated`.

These badges are the most visible audit signal in the demo. Don't add new
badges that obscure the existing four; instead add new audit fields to the
RouteTrace and surface them in the per-row audit expander.
