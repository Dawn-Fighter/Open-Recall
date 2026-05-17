---
inclusion: fileMatch
fileMatchPattern: ["**/*.py"]
---

# OpenRecall — Python Conventions Steering

## File header (always)

Every Python file starts with a one-line module docstring describing the
responsibility, then `from __future__ import annotations`:

```python
"""Auto-triage decision engine.

Converts an AlertFingerprint plus recalled MemoryMatch list into a TriageResult
under hard, auditable thresholds.
"""
from __future__ import annotations
```

The `from __future__ import annotations` line is **mandatory** because
several modules use `"CascadeFlowRouter"` forward references and PEP 604
unions in `Final[float]` annotations.

## Type hints

- Use built-in generics: `list[str]`, `dict[str, Any]`, `tuple[int, ...]`.
  Never `from typing import List, Dict, Tuple`.
- Use PEP 604 unions: `str | None`. Never `Optional[str]`.
- `Final[float]` for module-level thresholds.
- `Literal[...]` for closed string sets (e.g., `IncidentType`,
  `TriageDecision`).
- `TYPE_CHECKING` for cycle-prone hints (`fingerprint.py` uses it for
  `CascadeFlowRouter`).

## Pydantic v2 patterns

```python
from pydantic import BaseModel, ConfigDict, Field

class AlertFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)  # hashable for dedupe key
    error_class: str = ""
    # ...

class TriageResult(BaseModel):
    proposed_decision: TriageDecision
    triage_confidence: float = 0.0
    supporting_matches: list[MemoryMatch] = Field(default_factory=list)
    consistent_decision_count: int = 0
    requires_human_approval: bool = False
    escalation_reason: str = ""
```

- Backward-compatible field additions go **at the end of the class body**
  with `= None` or `Field(default_factory=list)` defaults.
- Never break the existing `AnalysisResult` field order; only append.
- Use `model_dump()` to serialize to dict, never `.dict()`.

## Error handling

- **Hindsight Cloud failures** flip to fallback via `_flip_to_fallback`
  helper in `memory.py`. The helper closes the SDK client, drops the
  reference, sets `fallback_mode=True`, and updates `self.status`. Per R11.3
  the client must NOT survive the failure.
- **Groq failures** are caught inside `_call_model` and recorded as
  `model_error` on the RouteTrace. They never crash the workflow; the
  caller falls back to deterministic output.
- **Pydantic ValidationError** in `analyze_queue` produces a placeholder
  `AnalysisResult` with `incident.error_type="invalid_alert"` and a single
  `AuditTraceEntry` with the rejection reason. Processing continues.

## Threshold references

```python
# RIGHT
from .triage import STRONG_MATCH_THRESHOLD, BYPASS_CONFIDENCE_THRESHOLD

if match.score >= STRONG_MATCH_THRESHOLD:
    ...

# WRONG — never inline a literal threshold
if match.score >= 0.85:
    ...
```

## Determinism rules

- **No `random.seed(...)`** in any module that imports cleanly. The global
  RNG belongs to the caller. Use `random.Random(seed)` instead.
- Hypothesis tests use `derandomize=True` + `HYPOTHESIS_SEED` env var (set
  by conftest from `OPENRECALL_PBT_SEED`).
- The `scripts/generate_seed_alerts.py` script uses `SEED = 20260101` and
  `random.Random(SEED)` only.

## Hindsight Cloud client wiring

```python
# memory.py — module-level helper
def _build_hindsight_client(base_url: str, api_key: str) -> Any:
    from hindsight_client import Hindsight  # type: ignore
    try:
        return Hindsight(base_url=base_url, api_key=api_key)  # native API key support
    except TypeError:
        # SDK doesn't accept api_key=; inject Bearer header into underlying httpx
        client = Hindsight(base_url=base_url)
        underlying = getattr(client, "_client", None) or getattr(client, "client", None)
        if underlying is not None and api_key:
            try:
                underlying.headers["Authorization"] = f"Bearer {api_key}"
            except Exception:
                pass
        return client
```

The dual-path probe is required because the `hindsight-client` SDK API may
have changed between versions; the fallback header injection keeps OpenRecall
compatible with older SDK builds.

## Backward-compatibility contract

The pre-OpenRecall single-alert path **must** keep working:

- `IncidentWorkflow.analyze(raw_alert: str) -> AnalysisResult` signature
  unchanged. Validate via `tests/test_signatures.py` after every workflow
  edit.
- `IncidentMemory.recall(query, limit)` and the legacy positional
  `IncidentMemory.retain(content, context, metadata)` shapes continue to work.
- New `AnalysisResult` fields all have safe defaults.
- New `RouteTrace` fields (`triage_decision_proposed`, `memory_match_score`,
  `decision_consistency`, `llm_skipped`, `budget_exhausted`) default to
  `None`/`False`.

## After every code change

Run in order:

1. `python -m compileall app.py incident_agent seed_memory.py scripts/smoke_test.py scripts/generate_seed_alerts.py tests`
2. `python -m pytest tests -q --hypothesis-profile=ci`
3. `python scripts/smoke_test.py`

If you touched `triage.py`, `memory.py`, `router.py`, `cost_curve.py`, or
`workflow.py`, also re-trace the correctness properties (P1-P15, see
`#correctness-properties`) to confirm none regressed.
