---
inclusion: fileMatch
fileMatchPattern: ["frontend/**/*.tsx", "frontend/**/*.ts", "api.py"]
---

# OpenRecall — Next.js Cockpit + FastAPI Backend Steering

This file is the contract for the analyst-facing cockpit. It pairs the
**Next.js 16 frontend** (`frontend/`) with the **FastAPI backend**
(`api.py`). When you change either side of the boundary, both sides
must stay consistent.

## Process boundary

| Process | Code | Port | Holds |
| --- | --- | --- | --- |
| FastAPI backend | `api.py` | `8000` | `IncidentMemory`, `CascadeFlowRouter`, `CostCurveTracker`, `IncidentWorkflow` singletons |
| Next.js cockpit | `frontend/` (App Router) | `3000` | UI only; calls FastAPI over `fetch` |

CORS is wide open in development. Production deployments must lock it
down to the cockpit origin.

## API surface (frozen contract)

```text
GET  /health        → {status, hindsight_connected, hindsight_status, groq_live, cheap_model, strong_model, budget_usd}
GET  /stats         → {total_alerts, total_cost_usd, total_savings_usd, pct_saved, hindsight_connected, groq_live}
GET  /cost-curve    → {points: [{index, cost, baseline}, ...]}
POST /seed          → {status, message}                    # idempotent re-push of seed_incidents.json
POST /analyze       → AnalyzeRequest{alert} → triage card payload (see api.py)
POST /retain        → RetainRequest{raw_alert, service, decision, dead_ends, ...} → {status, hindsight_response, cache_key}
```

The `/analyze` payload is the single source of truth for what the
cockpit can render. New triage card sections **MUST** be backed by a
field in the payload, not derived client-side.

## Frontend layout

```text
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx        # Geist fonts, dark theme, root <main>
│   │   ├── page.tsx          # renders <Demo />
│   │   ├── globals.css       # Tailwind v4 + shadcn tokens
│   │   └── favicon.ico
│   ├── components/
│   │   ├── demo.tsx          # mounts <VercelV0Chat />
│   │   └── ui/
│   │       ├── v0-ai-chat.tsx   # the cockpit (chat input, agent steps, triage card)
│   │       ├── button.tsx       # shadcn button
│   │       └── textarea.tsx     # shadcn textarea
│   └── lib/utils.ts          # cn() helper
├── package.json              # next 16, react 19, tailwind 4, shadcn 4
├── components.json           # shadcn config
├── postcss.config.mjs
├── eslint.config.mjs
└── tsconfig.json
```

## Cockpit conventions

- **`v0-ai-chat.tsx` is the cockpit.** Extend it; do not bypass it with
  parallel page components for new UI surfaces.
- **Decision pill palette.** `DecisionBadge` covers every
  `TriageDecision` Literal value. Adding a decision value without
  updating the badge palette is incomplete.
- **Streaming agent steps.** The `/analyze` response carries a `steps:
  string[]` field that the cockpit renders in order. Steps are plain
  English sentences in this fixed order: normalize, fingerprint, memory
  query, routing decision (or memory bypass), triage decision, optional
  root cause line, and approval/auto-remediation footer. **MUST NOT**
  introduce emojis or pictographs in step strings — the cockpit is for
  professional SOC operators and logs are read in dashboards and
  copied into ticket systems.
- **Section pattern.** Use the `Section` collapsible wrapper (already
  in `v0-ai-chat.tsx`) for every triage-card subsection so the analyst
  can collapse noise.
- **Override flow.** Calls `POST /retain` with the full triage card
  payload as `cached_payload` so the API's hash-cache shortcut surfaces
  the analyst-confirmed decision on the next identical alert.

## When to surface the mode badges

`/health` returns the four runtime flags. The cockpit header should
render badge-style indicators for each:

- `Hindsight connected` (green) vs `Fallback memory` (amber) — driven
  by `hindsight_connected`.
- `Live model calls` (green) vs `Deterministic model output` (amber) —
  driven by `groq_live`.

These are the most visible audit signal in the demo. Keep them prominent.

## When the API and cockpit must change together

Any of these changes touches the contract on both sides. Update both in
the same commit:

- New `RouteTrace` field surfaced in `/analyze` → cockpit renders it in
  the audit panel.
- New `TriageDecision` value → cockpit `DecisionBadge` palette + this
  steering file.
- New `RetainRequest` field → cockpit override form + this steering
  file.
- New endpoint → cockpit hook + this steering file.

## Anti-patterns

- ❌ Calling Hindsight Cloud or Groq directly from the cockpit. All
  outbound traffic goes through the FastAPI backend.
- ❌ Storing API keys in the frontend env (`NEXT_PUBLIC_*`). They
  belong in the FastAPI process environment only.
- ❌ Adding a separate cost-tracking or memory-bypass mechanism in the
  frontend that doesn't go through `IncidentWorkflow.analyze`.
- ❌ Bypassing the `Section` wrapper for new triage card subsections.
- ❌ Hard-coding the API base URL outside one shared constant.
