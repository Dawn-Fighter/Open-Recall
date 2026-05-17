---
inclusion: always
---

# OpenRecall — Product Steering

## What this project is

OpenRecall is an alert triage co-pilot for SOC analysts and on-call SRE/devs.
It is the hackathon submission for the **Hindsight x cascadeflow** challenge,
built on top of the existing `incident-memory-agent/` Streamlit cockpit.

The project converts a one-incident-at-a-time RCA workspace into a queue-driven
triage workflow with **counterfactual memory**: every retained alert carries
the analyst's final triage decision (`false_positive | duplicate | known_benign
| real | escalated`) and the dead ends prior responders already explored.

## The three pillars (every change must reinforce at least one)

1. **Counterfactual memory + auto-triage.** Hindsight Cloud is consulted
   *before* any expensive model call. When prior decisions are consistent
   enough (`Strong_Match score >= 0.85` AND `Decision_Consistency >= 0.9`),
   OpenRecall proposes the dominant decision and the strong model is bypassed
   entirely. When the decision is in the bypass-eligible set
   (`{false_positive, duplicate, known_benign}`) AND
   `triage_confidence >= 0.85` AND `attack_pattern` is empty, a synthetic
   `model="memory-bypass"` RouteTrace is emitted and zero LLM cost is incurred.

2. **Cost curve visibility.** The cockpit renders a layered Altair chart of
   per-alert OpenRecall cost vs strong-model-only baseline. The shaded green
   savings band grows as memory accumulates. Bypassed alerts record
   `cost_usd=0.0` while preserving `baseline_cost_usd` so the savings band
   remains meaningful.

3. **Alert DNA fingerprinting.** Each alert is reduced to a structured
   `AlertFingerprint` with six fields (`error_class`, `service_role`,
   `dependency_pattern`, `signal_shape`, `attack_pattern`, `environment`).
   Memory retrieval keys on this structured fingerprint, not on free-text
   keyword overlap.

## Personas

- **Maya, SOC Analyst (Tier 1).** Triages 200-500 SIEM alerts per shift,
  40-50% of which are false positives. Wants memory to pre-judge low-risk
  repeats so she focuses on the novel cases.
- **Devon, Senior SRE on-call.** Wakes up at 2am to PagerDuty pages. Wants
  instant context on whether the team has seen this signature, what was
  tried, and what made it worse.
- **Orchestrator (system role).** The OpenRecall workflow itself, responsible
  for fingerprint generation, memory recall, auto-triage proposal, escalation,
  retention, and cost/audit reporting.

## Hard non-goals

- No Slack, Teams, or email ingestion adapters in this milestone.
- No real PagerDuty/Datadog/Splunk/Sentinel/Chronicle webhooks. Synthetic
  data only.
- No cross-organization memory federation or public commons.
- No multi-tenancy, authentication, SSO, or per-analyst access control.
  Single-user demo only.
- No pre-deploy incident prediction.

## Hackathon scoring guidance

Every change is judged against these weights:

| Criterion | Weight |
|---|---|
| Innovation | 30% |
| Use of Hindsight & cascadeflow (memory + runtime intelligence) | 25% |
| Technical Implementation | 20% |
| User Experience | 15% |
| Real-world Impact | 10% |

Bias your suggestions toward changes that visibly strengthen one of those.

## Spec is the contract

All work must trace to `.kiro/specs/openrecall/{requirements,design,tasks}.md`.
Requirements use IDs `R<N>.<M>`. Correctness properties use IDs `P1`–`P15`.
When you propose code changes, cite the requirement IDs and property IDs the
change satisfies or affects.

## Default operating modes

- **Demo_Mode** = `CASCADEFLOW_LIVE_GROQ=false`. Deterministic outputs, no
  live API calls, full routing/cost trace still emitted.
- **Live mode** = `CASCADEFLOW_LIVE_GROQ=true` + `GROQ_API_KEY` set + reachable
  Hindsight Cloud. Real Groq calls, real Hindsight retrieval.
- **Local fallback** = `HINDSIGHT_API_KEY` unset OR `HINDSIGHT_BASE_URL`
  unreachable. Falls back to `data/seed_incidents.json` + `data/local_memory.json`.

The four mode-matrix quadrants are documented in
`#[[file:.kiro/specs/openrecall/design.md]]` under "Mode Matrix".
