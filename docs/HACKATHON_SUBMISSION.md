# Hackathon Submission Notes — OpenRecall

## One-Line Pitch

OpenRecall is an alert triage co-pilot for SOC analysts and on-call
SRE/devs. It fingerprints every alert as structured "alert DNA", recalls
prior triage decisions and the dead ends behind them from Hindsight
Cloud, and bypasses the strong model entirely when memory is consistent.

## Rubric Mapping

### Innovation (30%)

- **Counterfactual memory + auto-triage.** Each retained alert carries
  `triage_decision` (false_positive | duplicate | known_benign | real |
  escalated) and a `dead_ends` list. Future analysts inherit both.
- **Memory-bypass RouteTrace.** When memory is consistent, OpenRecall
  emits a synthetic `model="memory-bypass"` RouteTrace and skips the LLM
  entirely. The audit panel shows the bypass; the cost curve shows the
  savings.
- **Security-novel kill switch.** Any non-empty `attack_pattern`
  forces `requires_human_approval=True` regardless of memory consistency.
  Stops the demo from auto-dismissing a real attack.

### Use of Hindsight & cascadeflow (25%)

- **Hindsight Cloud is the agent's first move.** `recall_by_fingerprint`
  runs before any LLM call. If memory is silent, OpenRecall escalates;
  if memory is consistent, OpenRecall bypasses.
- **cascadeflow does real economic work.** The router tracks cumulative
  live-cost, enforces the per-batch budget, and emits the synthetic
  `memory-bypass` RouteTrace so cost-vs-baseline is observable per alert.
- The cost curve chart is a direct visualization of the cascadeflow value
  proposition.

### Technical Implementation (20%)

- **15 correctness properties** validated by Hypothesis property tests
  under a deterministic CI seed (`OPENRECALL_PBT_SEED=20260101`):
  fingerprint determinism, fingerprint round-trip, triage proposal
  determinism, triage confidence bounds, confidence-reflects-history
  metamorphic property, strong-model bypass invariant (P6), idempotent
  retain, cost-curve monotonicity, cost-curve baseline invariant,
  fallback-vs-cloud structural parity, no-strong-match-implies-escalated,
  security-novel-implies-escalated, recall-then-retain consistency,
  budget enforcement, audit-trace completeness.
- **Pydantic v2 models** throughout, with frozen `AlertFingerprint` so it
  can be a hash key for the in-process retain dedupe index.
- **Backward compatibility** preserved: `IncidentWorkflow.analyze(raw_alert)`
  signature unchanged; legacy `recall(query, limit)` still works; new
  `AnalysisResult` fields are optional with safe defaults.

### User Experience (15%)

- Two-process cockpit: **FastAPI backend** (`api.py`) holds the
  workflow singletons; **Next.js 16 frontend** (`frontend/`) renders
  the analyst UI with shadcn + Tailwind.
- Triage card with color-coded decision pills (`false_positive` green,
  `duplicate` / `known_benign` green, `escalated` red, `real` amber)
  plus per-section collapsible panels for fingerprint, prior incidents,
  root causes, dead ends, verification commands, and remediation.
- Inline override flow that calls `POST /retain` with decision, dead
  ends, and an optional analyst note — closing the learning loop in one
  click.
- Streaming agent step trace rendered as the workflow progresses, so the
  operator sees normalize → fingerprint → memory query → routing →
  triage in the order they happen.

### Real-world Impact (10%)

- Real personas: SOC Tier 1 analysts and on-call SREs both stare at
  alert queues; both rebuild tribal knowledge every shift.
- Real cost: OpenRecall's cost curve makes the LLM-spend-vs-savings
  conversation concrete in dollars rather than handwavy "AI is
  expensive" generalities.
- Real safety: the security-novel kill switch and the always-on
  `requires_human_approval=True` posture mean the agent recommends, the
  human decides.

## Suggested Evaluation Path

1. Start the backend with the live env vars: `uvicorn api:app --reload --port 8000`.
2. Sanity check: `curl http://127.0.0.1:8000/health` should return
   `hindsight_connected: true` and `groq_live: true`.
3. Start the frontend: `cd frontend && npm run dev`.
4. Open `http://localhost:3000` and submit a fresh alert. Inspect the
   triage card.
5. Override an escalated row to `false_positive` with a dead end.
6. Re-submit the same alert. Confirm cost drops to `$0.00` and the
   agent step trace shows the memory bypass.
7. Submit a security-flavoured alert. Confirm the security-novel kill
   switch fires (`requires_human_approval=true`).
8. Run the Hypothesis suite: `python -m pytest tests/property -q --hypothesis-profile=ci`.

## Production Extensions (Out of Scope)

- Slack ingestion bot that joins incident channels and turns the
  debugging conversation into structured memory.
- Cross-organization federation: anonymized incident DNA shared across
  orgs. The CVE database for production failures.
- Pre-deploy risk score using memory: "PR #142 risk score 0.71, here are
  the 3 prior incidents that drove the score."
- Multi-tenancy and per-team memory bank isolation.
