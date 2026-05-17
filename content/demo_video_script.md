# 2-minute demo script — OpenRecall

0:00 - 0:10 — Open the cockpit. Confirm `Hindsight connected` and `Live model
calls` badges. Cue: "OpenRecall is an alert triage co-pilot. Memory first,
LLM only when memory says so."

0:10 - 0:35 — Click `Queue` tab. Click `Use packaged seed alerts (100)`. Click
`Analyze queue`. Wait for the cost curve to render. Point to:
- Per-batch summary: alert count, auto-decided by memory, escalated, total
  savings, percent saved.
- The Altair chart with the green savings band.
- Queue table rows with triage badges (green for false_positive, red for
  escalated).

Cue: "Cascadeflow earns its keep on every memory hit. Red line is the
strong-model-only baseline; blue line is what we actually paid; green
band is the savings memory bought us."

0:35 - 0:55 — Pick an escalated row. Click `Override`. Set decision to
`false_positive`. Add a dead end: "restarted DB pods, made it worse". Click
`Save & retain`. Watch the row update.

Cue: "That decision and the dead end are now in Hindsight Cloud. The next
analyst won't restart DB pods."

0:55 - 1:25 — Click `Analyze queue` again. Point to:
- The same fingerprint family now reads `false_positive` with high
  confidence.
- The cost curve flattens near zero for the repeats.
- Open one row's audit trace expander. Show `model: memory-bypass`,
  `llm_skipped: True`, `cost: $0.000000`.

Cue: "Strong model never ran for those alerts. Property test P6 enforces
this invariant across every release."

1:25 - 1:50 — Switch to `Single alert` tab. Pick `Security: WAF SQL
injection`. Run analysis. Show the audit trace and the security-novel
kill switch in the escalation reason.

Cue: "Attack pattern non-empty means human-approval required regardless
of memory state. The agent never auto-dismisses a real attack."

1:50 - 2:00 — Close on the rubric:
- Innovation: counterfactual memory + memory-bypass RouteTrace.
- Hindsight + cascadeflow centrality: memory is the agent's first move,
  cost is visible per alert.
- Technical: 15 Hypothesis property tests, deterministic CI seed,
  21 tests passing.
- UX: two-tab cockpit, color-coded triage pills, Altair cost curve.
- Real-world: SOC analysts and on-call SREs both stare at alert queues.

Cue: "Stop rediscovering the same triage decisions every on-call shift."
