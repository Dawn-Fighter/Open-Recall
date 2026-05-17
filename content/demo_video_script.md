# 2-minute demo script — OpenRecall

0:00 - 0:10 — Pre-flight. Show two terminals: `uvicorn api:app --reload`
on :8000 and `npm run dev` in `frontend/` on :3000. Hit
`http://127.0.0.1:8000/health` and read out `hindsight_connected: true`,
`groq_live: true`.

Cue: "OpenRecall is an alert triage co-pilot. Memory first, LLM only
when memory says so."

0:10 - 0:30 — Open `http://localhost:3000`. Paste a checkout-service
crashloop alert into the chat input. Hit submit. Narrate the streaming
agent steps as they appear:
- Normalize → service detected
- Fingerprint → six structured fields extracted
- Memory query → hits / no hits
- Routing → strong model OR memory-bypass
- Triage decision pill rendered

Cue: "Watch the agent's first move. It's the memory query, not the
LLM."

0:30 - 0:55 — Inspect the triage card:
- Decision pill (color-coded).
- Fingerprint section (Alert DNA, six fields).
- Prior incidents list (top three matches with score + prior decision).
- Cost line: actual cost, savings, latency.
- Skip-these-paths panel (the dead ends from prior responders).

Cue: "Cascadeflow earns its keep on every memory hit. The cost line is
zero when memory bypasses."

0:55 - 1:20 — Click the override flow on the card. Set decision to
`false_positive`. Add a dead end: "restarted DB pods, made it worse."
Save & retain. Watch the success toast.

Cue: "That decision and the dead end are now in Hindsight Cloud. The
next analyst won't restart DB pods."

1:20 - 1:45 — Paste the same alert again. Show:
- The agent step trace shortcuts to "memory bypass" / "served from
  decision cache".
- Decision pill matches the override.
- Cost line reads `$0.00` with full savings.
- Hit `GET /cost-curve` in another tab, point to the new bypass point
  with `cost: 0` and `baseline` preserved.

Cue: "Strong model never ran. Property test P6 enforces this invariant
across every release."

1:45 - 2:00 — Submit a security-flavoured alert (WAF SQL injection on
api-gateway). Show that even with consistent memory, the card surfaces
`requires_human_approval: true` and a security-novel rationale.

Close on the rubric:
- Innovation: counterfactual memory + memory-bypass RouteTrace.
- Hindsight + cascadeflow centrality: memory is the agent's first move,
  cost is visible per alert via the API.
- Technical: 15 Hypothesis property tests under a deterministic CI seed.
- UX: streaming agent steps, color-coded triage pills, inline override
  flow, structured triage card.
- Real-world: SOC analysts and on-call SREs both stare at alert queues.

Cue: "Stop rediscovering the same triage decisions every on-call shift."
