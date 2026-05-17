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

- Two-tab cockpit: **Single alert** (the original RCA flow) and **Queue**
  (the new batch triage flow).
- Per-row triage decision pills color-coded by decision class
  (`false_positive` green, `duplicate` blue, `known_benign` teal,
  `real` orange, `escalated` red, plus a `Novel` purple pill for
  no-prior-memory).
- Inline override flow with decision, dead ends, analyst ID, business
  impact minutes — all written to the same retain path.
- Per-row audit trace expander rendering each `AuditTraceEntry` with
  model, route reason, decision, escalation reason, cost, baseline,
  savings, and live-call status.

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

1. Run the Streamlit app with the live env vars (Hindsight Cloud +
   Live Groq).
2. Queue tab → `Use packaged seed alerts (100)` → `Analyze queue`.
3. Inspect the cost curve, the per-batch summary, and a few queue rows.
4. Override one escalated row to `false_positive` with a dead end.
5. Re-run `Analyze queue`. Confirm the same fingerprint family now
   bypasses (audit trace shows `model: memory-bypass`).
6. Single alert tab → `Security: WAF SQL injection`. Confirm the
   security-novel kill switch in the audit trace.
7. Run the Hypothesis suite: `python -m pytest tests/property -q`.

## Production Extensions (Out of Scope)

- Slack ingestion bot that joins incident channels and turns the
  debugging conversation into structured memory.
- Cross-organization federation: anonymized incident DNA shared across
  orgs. The CVE database for production failures.
- Pre-deploy risk score using memory: "PR #142 risk score 0.71, here are
  the 3 prior incidents that drove the score."
- Multi-tenancy and per-team memory bank isolation.
