---
inclusion: always
---

# OpenRecall — Technology Stack Steering

## Runtime

- **Python 3.11+** (uses `match` statements, PEP 604 unions, `Literal`, `Final`)
  for the FastAPI backend and `incident_agent/` package.
- **Node.js 20+** for the Next.js cockpit (`frontend/`).
- All Python modules use `from __future__ import annotations`.

## Pinned dependencies

### Backend (`requirements.txt` and `pyproject.toml`)

- `fastapi>=0.136.0` — HTTP layer for the analyst cockpit
- `uvicorn>=0.47.0` — ASGI runner (`uvicorn api:app --reload --port 8000`)
- `pydantic>=2.7.0` — typed data models, **v2 only**, never v1
- `python-dotenv>=1.0.1` — load `.env` at process startup
- `httpx>=0.27.0` — sync HTTP for Groq + Hindsight health probe
- `hindsight-client>=0.1.0` — Hindsight Cloud SDK
- `cascadeflow[groq]>=0.1.0` — runtime cost intelligence with Groq adapter

Dev (`[project.optional-dependencies] dev`):

- `hypothesis>=6.108` — property-based testing
- `pytest>=8.0` — test runner

### Frontend (`frontend/package.json`)

- `next 16.x` (App Router)
- `react 19.x`, `react-dom 19.x`
- `tailwindcss 4.x`, `@tailwindcss/postcss 4.x`
- `shadcn 4.x` + `class-variance-authority`, `clsx`, `tailwind-merge`,
  `tw-animate-css`
- `lucide-react` for icons
- `@base-ui/react` for accessible primitives

## API endpoints + models

- **Hindsight Cloud** — `https://api.hindsight.vectorize.io`. Bearer
  `HINDSIGHT_API_KEY`. Default bank id `openrecall`.
- **Groq** — `https://api.groq.com/openai/v1/chat/completions`. OpenAI-compatible.
- **Cheap model** — `qwen/qwen3-32b` (default). Token cost heuristic
  $0.10/M tokens.
- **Strong model** — `openai/gpt-oss-120b` (default). Token cost heuristic
  $0.75/M tokens.
- **Memory-bypass model name** — the literal string `"memory-bypass"`. This
  is a synthetic RouteTrace step, not a real model. Used to satisfy P15
  (audit-trace completeness).

## Backend ⇄ Frontend contract

The FastAPI backend (`api.py`) holds the long-lived workflow singletons.
The Next.js cockpit calls the API over `fetch`. The frozen surface:

```text
GET  /health        → mode flags + model names
GET  /stats         → cumulative cost + savings
GET  /cost-curve    → per-alert {index, cost, baseline} points
POST /seed          → idempotent re-push of seed_incidents.json
POST /analyze       → AnalyzeRequest{alert} → triage card payload
POST /retain        → RetainRequest{...} → {status, hindsight_response, cache_key}
```

## Key idioms (do these unprompted)

- **Pydantic v2 only.** Use `ConfigDict`, `Field(default_factory=...)`,
  `model_config`, `model_dump()`, `model_fields`. Never use Pydantic v1
  patterns (`Config` inner class, `.dict()`, `.json()`).
- **Type hints everywhere.** Public methods on `incident_agent/*.py` modules
  carry full annotations. Use `list[X] | None` style, not `Optional[List[X]]`.
- **`Final[float]` for thresholds.** Triage thresholds live as module-level
  `Final[float]` constants in `incident_agent/triage.py`. Never inline a
  literal threshold; reference the constant by name.
- **Local imports for cycle-prone calls.** `format_fingerprint` is imported
  *inside* method bodies of `IncidentMemory` to avoid a fingerprint↔memory
  module-load cycle.
- **Module-level singletons in `api.py`.** `IncidentMemory`,
  `CascadeFlowRouter`, `CostCurveTracker`, and `IncidentWorkflow` are
  constructed exactly once at module load. The FastAPI process holds
  them for its lifetime. Do not instantiate per-request.

## Anti-patterns to refuse

- ❌ Pydantic v1 `class Config:` inner class. Use `ConfigDict`.
- ❌ `from typing import Optional, List, Dict`. Use built-in generics.
- ❌ Hard-coded threshold literals (e.g., `if score >= 0.85:`). Reference the
  named constant from `triage.py`.
- ❌ Using `random.seed(20260101)` (mutates global RNG). Use
  `random.Random(20260101)`.
- ❌ Calling Hindsight `client.recall` without try/except → flip to fallback.
- ❌ Adding a new `RouteTrace` step without a corresponding `AuditTraceEntry`.
  Property 15 requires `len(audit_trace) == len(route_trace)`.
- ❌ Skipping `_flip_to_fallback` when a Hindsight Cloud call fails.
  Per R11.3 the client must be closed and dropped for the session.
- ❌ Calling Hindsight Cloud or Groq directly from the cockpit. All
  outbound traffic goes through the FastAPI backend.
- ❌ Putting API keys in `NEXT_PUBLIC_*` env vars. They belong in the
  FastAPI process environment only.

## Test execution commands

```bash
make compile   # python -m compileall api.py incident_agent ...
make pbt       # pytest tests/property -q
make smoke     # pbt + scripts/smoke_test.py (4 sub-checks)
```

CI runs all three under `OPENRECALL_PBT_SEED=20260101`,
`HINDSIGHT_BASE_URL=http://127.0.0.1:9`, `CASCADEFLOW_LIVE_GROQ=false`.

## Run commands

```bash
make api        # uvicorn api:app --reload --port 8000
make frontend   # cd frontend && npm run dev
```

## Live demo env vars

```bash
HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
HINDSIGHT_API_KEY=hsk_...                # Bearer token
HINDSIGHT_BANK_ID=openrecall
GROQ_API_KEY=gsk_...
CASCADEFLOW_LIVE_GROQ=true
CASCADEFLOW_RUN_BUDGET_USD=0.02          # per-batch ceiling
CASCADEFLOW_CHEAP_MODEL=qwen/qwen3-32b
CASCADEFLOW_STRONG_MODEL=openai/gpt-oss-120b
OPENRECALL_PBT_SEED=20260101             # Hypothesis CI seed
OPENRECALL_BATCH_SIZE_LIMIT=200          # analyze_queue cap
```
