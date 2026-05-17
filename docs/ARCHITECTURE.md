# Architecture

OpenRecall is a queue-driven alert triage co-pilot built on three
load-bearing ideas: counterfactual memory keyed on a structured Alert DNA
fingerprint, an auto-triage engine that bypasses the strong model when
memory is consistent, and a live cost curve that proves the cascadeflow
value in under sixty seconds of demo time.

The system runs as two cooperating processes:

- **`api.py`** — a FastAPI service holding the long-lived `IncidentMemory`,
  `CascadeFlowRouter`, `CostCurveTracker`, and `IncidentWorkflow`
  singletons. Exposes `/health`, `/stats`, `/cost-curve`, `/seed`,
  `/analyze`, `/retain`.
- **`frontend/`** — a Next.js 16 App Router application (Tailwind +
  shadcn) that renders the analyst cockpit and calls the FastAPI
  endpoints. CORS is wide open in development.

## System Context

```mermaid
flowchart LR
    subgraph Actors
        Maya[Maya<br/>SOC Analyst Tier 1]
        Devon[Devon<br/>Senior SRE on-call]
    end

    subgraph OpenRecall_System
        Frontend[Next.js Cockpit<br/>frontend/ on :3000]
        Backend[FastAPI Backend<br/>api.py on :8000]
        Workflow[Workflow Orchestrator<br/>incident_agent/workflow.py]
    end

    HindsightCloud[(Hindsight Cloud<br/>api.hindsight.vectorize.io)]
    LocalStore[(Local Fallback Store<br/>data/local_memory.json<br/>data/seed_incidents.json)]
    Groq[Groq via cascadeflow<br/>qwen3-32b / gpt-oss-120b]

    Maya -- pastes/uploads alerts --> Frontend
    Devon -- pastes single page --> Frontend
    Frontend -- fetch /analyze /retain /stats /cost-curve --> Backend
    Backend --> Workflow
    Workflow -- recall_by_fingerprint / retain --> HindsightCloud
    Workflow -. fallback recall/retain .-> LocalStore
    Workflow -- fingerprint extract / RCA generate --> Groq
    Workflow -- triage bypass / no LLM --> Backend
```

## Components

```mermaid
flowchart TB
    subgraph UI [Next.js Cockpit]
        AlertChat[v0-ai-chat input]
        TriageCard[Triage Card]
        CostChart[Cost Curve Chart]
        AuditPanel[Audit Trace Panel]
        DeadEndsPanel[Skip-These-Paths Panel]
    end

    subgraph API [FastAPI Backend]
        Analyze[/POST /analyze/]
        Retain[/POST /retain/]
        Stats[/GET /stats/]
        Curve[/GET /cost-curve/]
        Health[/GET /health/]
    end

    subgraph Orchestration
        Workflow[Workflow Orchestrator]
        FPGen[Fingerprint Generator]
        Triage[Triage Engine]
    end

    subgraph Routing
        Router[CascadeFlow Router]
    end

    subgraph Memory
        Adapter[Memory Adapter]
        HSClient[Hindsight Client]
        LocalFB[Local Fallback Store]
    end

    subgraph Telemetry
        CostTracker[Cost Curve Tracker]
        Audit[Audit Trace Recorder]
    end

    AlertChat --> Analyze
    TriageCard -. override .-> Retain
    CostChart --> Curve
    Analyze --> Workflow
    Retain --> Adapter
    Workflow --> FPGen
    FPGen --> Router
    Workflow --> Adapter
    Adapter --> HSClient
    Adapter -. fallback .-> LocalFB
    Workflow --> Triage
    Triage --> Router
    Router --> CostTracker
    Router --> Audit
    Audit --> AuditPanel
    CostTracker --> CostChart
    Adapter --> DeadEndsPanel
```

## Single Alert Flow

```mermaid
sequenceDiagram
    autonumber
    participant U as Analyst (browser)
    participant FE as Next.js Cockpit
    participant BE as FastAPI /analyze
    participant W as Workflow Orchestrator
    participant FG as Fingerprint Generator
    participant R as CascadeFlow Router
    participant M as Memory Adapter
    participant T as Triage Engine
    participant CT as Cost Curve Tracker
    participant A as Audit Trace Recorder

    U->>FE: submit alert
    FE->>BE: POST /analyze {alert: "..."}
    BE->>W: workflow.analyze(raw_alert)
    W->>FG: generate(raw_alert)
    FG->>R: cheap-model JSON extract (qwen/qwen3-32b)
    R-->>FG: fingerprint JSON + RouteTrace(step="alert fingerprint")
    FG-->>W: AlertFingerprint, fingerprint_trace
    W->>M: recall_by_fingerprint(fp, limit=5)
    M-->>W: list[MemoryMatch]
    W->>T: triage(fp, matches)
    T-->>W: TriageResult(proposed_decision, triage_confidence, requires_human_approval)

    alt bypass condition met (Strong_Match >= 0.85 AND consistency >= 0.9 AND attack_pattern empty)
        W->>R: emit synthetic memory-bypass RouteTrace
        R-->>W: RouteTrace(model="memory-bypass", llm_skipped=True, cost=0.0)
    else escalation required
        W->>R: rca_with_trace(incident, dead_ends, confidence, security_relevant)
        R-->>W: rca_json + RouteTrace(step="RCA investigation")
    end

    W->>CT: record(alert_index, cost_usd, baseline_cost_usd)
    CT-->>W: CostCurvePoint
    W->>A: build(fingerprint, matches, triage_result, route_trace, cost_point)
    A-->>W: list[AuditTraceEntry]
    W-->>BE: AnalysisResult
    BE-->>FE: JSON triage card payload
    FE-->>U: render decision pill, fingerprint, prior incidents, root causes, dead ends, cost
```

## Retain After Override

```mermaid
sequenceDiagram
    autonumber
    participant U as Analyst (browser)
    participant FE as Next.js Cockpit
    participant BE as FastAPI /retain
    participant M as Memory Adapter
    participant H as Hindsight Client
    participant L as Local Fallback Store

    U->>FE: open Override Flow on triage card
    U->>FE: submit (decision, dead_ends, analyst_note)
    FE->>BE: POST /retain {raw_alert, service, decision, dead_ends, fingerprint}
    BE->>M: retain(fingerprint, decision, content, dead_ends, ...)
    M->>M: dedupe_key = (fingerprint_canonical, decision, sha256(content))
    alt duplicate
        M-->>BE: status="skipped duplicate"
    else new record
        alt Hindsight Cloud reachable
            M->>H: retain(metadata={fingerprint, decision, dead_ends, ...})
            H-->>M: ok
            M-->>BE: status="retained in Hindsight"
        else fallback
            M->>L: append to data/local_memory.json
            M-->>BE: status="retained in local JSON fallback"
        end
    end
    BE-->>FE: {status, hindsight_response, cache_key}
    FE-->>U: success toast + refresh of triage card
```

## Triage Decision Flowchart

```mermaid
flowchart TD
    Start[AlertFingerprint fp + matches] --> Filter[Filter Strong_Matches: score >= 0.85]
    Filter --> HasStrong{any Strong_Match?}
    HasStrong -- no --> EscNoMatch[proposed_decision = escalated]
    HasStrong -- yes --> Group[group Strong_Matches by decision]
    Group --> Cons[Decision_Consistency = n_dominant / n_strong]
    Cons --> ConsCheck{>= 0.9?}
    ConsCheck -- no --> EscWeak[proposed_decision = escalated]
    ConsCheck -- yes --> AttackCheck{attack_pattern non-empty?}
    AttackCheck -- yes --> KillSwitch[propose dominant<br/>requires_human_approval=True<br/>security-novel rationale]
    AttackCheck -- no --> Propose[propose dominant<br/>requires_human_approval=True]
    Propose --> BypassCheck{decision in {fp, dup, kb}<br/>AND confidence >= 0.85?}
    BypassCheck -- yes --> Bypass[memory-bypass RouteTrace<br/>llm_skipped=True, cost=0.0]
    BypassCheck -- no --> InvokeStrong[Strong-model RCA<br/>with dead_ends in prompt]
    EscNoMatch --> InvokeStrong
    EscWeak --> InvokeStrong
    KillSwitch --> InvokeStrong
```

Threshold constants live as module-level `Final[float]` values in
`incident_agent/triage.py`:
- `STRONG_MATCH_THRESHOLD = 0.85`
- `DECISION_CONSISTENCY_THRESHOLD = 0.9`
- `BYPASS_CONFIDENCE_THRESHOLD = 0.85`

## Runtime Modes

| Mode | `HINDSIGHT_API_KEY` | `CASCADEFLOW_LIVE_GROQ` | Recall path | Fingerprint path | `/health` flags |
| --- | --- | --- | --- | --- | --- |
| Hindsight Cloud + live Groq | set, host reachable | true + key set | Cloud first, fallback if 5xx | Live cheap-model JSON | `hindsight_connected=true` + `groq_live=true` |
| Hindsight Cloud + Demo_Mode | set, host reachable | false | Cloud first, fallback if 5xx | Regex fallback | `hindsight_connected=true` + `groq_live=false` |
| Local Fallback + live Groq | unset/unreachable | true + key set | local JSON | Live cheap-model JSON | `hindsight_connected=false` + `groq_live=true` |
| Local Fallback + Demo_Mode | unset/unreachable | false | local JSON | Regex fallback | `hindsight_connected=false` + `groq_live=false` |

The Next.js cockpit reads `/health` on load and surfaces the four flag
combinations as badges in the header.

## Data Boundaries

- `data/seed_incidents.json` — 18 synthetic seed memories carrying
  `triage_decision` and `dead_ends`. Safe demo data.
- `data/seed_alerts.json` — 100 synthetic alerts (50 repeats / 30 false
  positives / 15 novel real / 5 ambiguous). Generated deterministically by
  `scripts/generate_seed_alerts.py`. Safe demo data.
- `data/local_memory.json` — generated by the learning loop. Should be
  gitignored in production deployments because it can carry retained
  triage decisions, dead ends, and analyst IDs.
- `data/decision_cache.json` — generated by the FastAPI alert hash cache.
  Process-local, gitignored.
- `.env` — never committed. Carries the live Hindsight Cloud API key and
  Groq API key.
