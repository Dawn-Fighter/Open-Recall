# OpenRecall: Memory-First Alert Triage with Hindsight + cascadeflow

Every on-call shift starts the same way: an alert fires, the responder
checks if it's the same false-positive scanner from last week, and ten
minutes go into rediscovering what the previous shift already knew. SOC
analysts triage 200-500 alerts a shift, 30-50% of them false positives,
each one re-investigated from scratch.

OpenRecall flips the workflow. It fingerprints every alert as structured
"alert DNA" — error class, service role, dependency pattern, signal shape,
attack pattern, environment — and asks Hindsight Cloud what we decided
last time we saw this fingerprint. If three previous analysts all marked
it `false_positive` with consistent reasoning, OpenRecall proposes the
same decision and skips the LLM call entirely. The strong model never
runs. Cost drops to zero for that alert.

The trick is counterfactual memory. Most AI ops products store "what
fixed it"; OpenRecall stores "what we already proved isn't it" — the
dead ends. When a real incident does fire, the next responder reads
"don't restart DB pods, the team tried that on 2026-03-15 and made it
worse" before they touch a kubectl. Memory of failure is asymmetrically
valuable: one successful fix is one path; one disproven hypothesis prunes
the entire search tree below it.

The runtime intelligence comes from cascadeflow. Every alert produces a
`RouteTrace` with model, route reason, confidence, latency, estimated
cost, strong-model baseline, savings, live-call status, and budget
remaining. The cockpit renders a layered Altair chart: red line for
strong-model-only baseline, blue line for actual OpenRecall cost, green
band between them for the savings memory earned. As the demo runs 100
synthetic alerts, the green band grows visibly — that's cascadeflow
making its case in real time.

Three production-grade safety rails ride alongside. First, the
security-novel kill switch: any alert with a non-empty `attack_pattern`
field forces `requires_human_approval=True` regardless of memory
consistency. Second, per-batch budget enforcement on the cumulative live
cost — when the budget hits, the in-flight call completes and every
subsequent call drops to deterministic mode with `budget_exhausted=True`
on the trace. Third, audit trace completeness: every alert produces
exactly one `AuditTraceEntry` per `RouteTrace` so the operator can
inspect every decision the agent made. All three are validated by
Hypothesis property tests under a deterministic CI seed.

The wedge is narrow but sharp: the agent's first move is memory, not
inference. Every existing AI ops product treats memory as a sidebar; we
made it the routing decision. With Hindsight Cloud as the persistent
substrate and cascadeflow as the runtime cost layer, OpenRecall stops
the next on-call shift from rediscovering what the previous shift
already learned.
