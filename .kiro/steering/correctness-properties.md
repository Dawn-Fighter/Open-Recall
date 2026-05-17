---
inclusion: manual
---

# OpenRecall — Correctness Properties Reference

This file is the single canonical reference for the 15 correctness properties
the OpenRecall PBT suite enforces. Pull it in via `#correctness-properties`
when reasoning about behavior, regressions, or test coverage.

The full doc-source-of-truth is
`#[[file:.kiro/specs/openrecall/requirements.md]]` § Correctness Properties.

---

## P1 — Fingerprint determinism (Demo_Mode)

**Statement.** For any `raw_alert` string in Demo_Mode, two consecutive
`FingerprintGenerator.generate(raw_alert)` calls return AlertFingerprint
instances that compare equal.

**Test.** `tests/property/test_fingerprint.py::test_fingerprint_determinism_demo_mode`
**Validates.** R3.3, R3.4
**Touch points.** `incident_agent/fingerprint.py` (regex_fallback)

---

## P2 — Fingerprint round-trip

**Statement.** For any AlertFingerprint `fp`,
`parse_fingerprint(format_fingerprint(fp)) == fp`.

**Test.** `tests/property/test_fingerprint.py::test_fingerprint_round_trip`
**Validates.** R3.6, R3.7
**Touch points.** `_FINGERPRINT_FIELDS` tuple, the regex `_FINGERPRINT_RE`,
`format_fingerprint` and `parse_fingerprint` functions.

---

## P3 — Triage proposal determinism

**Statement.** Given the same AlertFingerprint and frozen MemoryMatch list,
two consecutive `TriageEngine.triage(...)` calls return TriageResult
instances whose `proposed_decision`, `triage_confidence`, and
`requires_human_approval` fields compare equal.

**Test.** `tests/property/test_triage.py::test_triage_proposal_determinism`
**Validates.** R5.1, R5.2, R5.3
**Touch points.** `decision_consistency` (sort by score desc for
deterministic Counter tie-break), `confidence` clamp.

---

## P4 — Triage confidence bounds

**Statement.** `0.0 <= triage_confidence <= 1.0` for every TriageResult.

**Test.** `tests/property/test_triage.py::test_triage_confidence_bounds`
**Validates.** R5.2
**Touch points.** `TriageEngine.confidence` clamp formula.

---

## P5 — Confidence reflects history (metamorphic)

**Statement.** When Decision_Consistency is `c` over `n >= 1` Strong_Matches,
`c * (n / (n + 1)) <= triage_confidence <= c`.

**Test.** `tests/property/test_triage.py::test_confidence_reflects_history`
**Validates.** R5.2, R5.5
**Touch points.** Clamp formula `min(c, max(c * n/(n+1), c * (1 - 1/(n+2))))`.

The lower bound `c * n/(n+1)` is the contract. The actual returned value
sits between this lower bound and `c` itself. Confidence increases monotonically
with `n` for fixed `c`.

---

## P6 — Strong-model bypass invariant ⭐ (rubric-critical)

**Statement.** When recall has at least one Strong_Match (`score >= 0.85`)
AND Decision_Consistency over Strong_Matches is `>= 0.9` AND
`fp.attack_pattern` is empty AND the dominant decision is in
`{false_positive, duplicate, known_benign}` AND `triage_confidence >= 0.85`,
then `AnalysisResult.route_trace`:

- contains zero entries with `model == "openai/gpt-oss-120b"` AND
  `live_model_call == True`
- contains exactly one entry with `model == "memory-bypass"` AND
  `llm_skipped == True`

**Test.** `tests/property/test_triage.py::test_strong_model_bypass_invariant`
**Validates.** R6.1, R6.4, R6.5
**Touch points.** Workflow's bypass-condition expression, `triage_with_trace`,
the `BYPASS_CONFIDENCE_THRESHOLD` constant.

**Why `n_total >= 6` is required in the test.** Confidence at `c=1.0` first
crosses 0.85 at `n=5` (value 0.857). The PBT uses `n_total >= 6` for
deterministic fire even after Hypothesis shrinking. In production with
local recall (capped at 5 matches), 5 fully-consistent strong matches just
barely cross the bypass threshold.

---

## P7 — Idempotent retain

**Statement.** Calling `retain(fingerprint, decision, content, ...)` twice in
succession leaves the underlying store with exactly one record matching the
dedupe key `(format_fingerprint(fp), decision, sha256(content))`.

**Test.** `tests/property/test_memory.py::test_retain_idempotent`
**Validates.** R8.3
**Touch points.** `IncidentMemory._dedupe_index` set, `_match_local_dedupe`
function for cross-process check on `data/local_memory.json`.

---

## P8 — Cost-curve monotonicity (metamorphic)

**Statement.** Given a finite alert distribution `D` and two batches `B1, B2`
sampled iid from `D` and processed in order with retain enabled between
batches, `mean_cost_per_alert(B2) <= mean_cost_per_alert(B1)`.

**Test.** `tests/property/test_cost_curve.py::test_cost_curve_monotonic_repeating_distribution`
**Validates.** R9.5
**Touch points.** `CostCurveTracker.mean_cost_per_alert(batch_id)`,
workflow's per-bypass `cost_usd=0.0` recording.

**Note.** In offline fallback the keyword-overlap recall scorer rarely
crosses the bypass threshold, so the workflow-level monotonicity isn't
visible without seeded memory. The PBT exercises the tracker directly with
synthetic batches.

---

## P9 — Cost-curve never exceeds baseline

**Statement.** For every CostCurvePoint `p`, `p.cost_usd <= p.baseline_cost_usd`,
AND the series returned by `series()` is sorted by `alert_index` with no gaps.

**Test.** `tests/property/test_cost_curve.py::test_cost_curve_never_exceeds_baseline`
**Validates.** R9.1, R9.4
**Touch points.** `CostCurveTracker.record`, the workflow's bypass-case
recording (cost=0.0, baseline=preserved-from-strong-model-prompt).

---

## P10 — Fallback-vs-cloud structural parity

**Statement.** For any `raw_alert` in Demo_Mode, the AnalysisResult instances
produced by the Hindsight Cloud path and the Local_Fallback_Store path share
the same Pydantic class, the same set of field names, and the same nested
model classes per field. Value equality is NOT required.

**Test.** `tests/property/test_memory.py::test_fallback_vs_cloud_structural_parity`
**Validates.** R11.4
**Touch points.** `AnalysisResult` Pydantic schema, the per-method symmetry
between cloud and fallback paths in `IncidentMemory`.

---

## P11 — No-Strong-Match implies escalation

**Statement.** When recall returns zero MemoryMatch with `score >= 0.85`,
`TriageResult.proposed_decision == "escalated"`.

**Test.** `tests/property/test_triage.py::test_no_strong_match_escalates`
**Validates.** R5.4
**Touch points.** First branch of `TriageEngine.triage`.

---

## P12 — Security-novel bypass refusal

**Statement.** When `fp.attack_pattern` is non-empty AND no MemoryMatch has
`score >= 0.85`, `TriageResult.proposed_decision == "escalated"`.

**Test.** `tests/property/test_triage.py::test_security_novel_escalates`
**Validates.** R5.6
**Touch points.** `TriageEngine.triage` (security-novel kill switch path).

This is a **derived corollary** of P11 — when there are no strong matches,
P11 already forces escalation. P12 is kept as a separate property because
the security-novel kill switch ALSO fires when strong matches exist (in
which case the workflow proposes the dominant decision but flags
`requires_human_approval=True`, never auto-bypassing).

---

## P13 — Recall-then-retain consistency

**Statement.** After `retain(content, fingerprint=fp, decision=decision,
dead_ends=dead_ends, ...)` succeeds, the next `recall_by_fingerprint(fp)`
call returns at least one MemoryMatch whose metadata reflects `decision`
AND whose `metadata.dead_ends` contains every entry of the retained
`dead_ends`.

**Test.** `tests/property/test_memory.py::test_recall_then_retain_consistency`
**Validates.** R7.4, R7.5, R8.5
**Touch points.** `_DictBackedMemory.retain` (which inserts the new match
into `_canned_recall` so the next recall surfaces it), production
`IncidentMemory.retain` writing into `data/local_memory.json`.

---

## P14 — Budget enforcement

**Statement.** Sum of `estimated_cost_usd` across all `live_model_call=True`
RouteTrace entries within a single batch is
`<= CASCADEFLOW_RUN_BUDGET_USD + estimated_cost_usd_of_final_in_flight_call`.
After the budget is reached, every subsequent RouteTrace has
`budget_exhausted=True` AND `live_model_call=False`.

**Test.** `tests/property/test_cost_curve.py::test_budget_enforcement`
**Validates.** R6.6
**Touch points.** Router's `_cum_live_cost`, `_budget_exhausted`, the
`_call_model` budget-check branch.

---

## P15 — Audit trace completeness ⭐ (cross-cutting)

**Statement.** For every analyzed alert,
`len(AnalysisResult.audit_trace) == len(AnalysisResult.route_trace)`, AND
every AuditTraceEntry has non-None `step`, `model`, `route_reason`,
`live_model_call`, `cost_usd`, `baseline_cost_usd`.

**Test.** `tests/property/test_workflow.py::test_audit_trace_completeness`
**Validates.** R10.1, R10.3
**Touch points.** `AuditTraceRecorder.build` (one entry per RouteTrace
guarantee), every site that appends a RouteTrace must ALSO ensure the
audit invariant holds.

**This is the meta-invariant.** Any time you add a new RouteTrace step
anywhere, you MUST emit a matching AuditTraceEntry, otherwise P15 breaks.

---

## When you change code, run this checklist

| Touched | Re-run these properties |
|---|---|
| `fingerprint.py` | P1, P2 |
| `triage.py` | P3, P4, P5, P6, P11, P12 |
| `memory.py` | P7, P10, P13 |
| `cost_curve.py` | P8, P9 (P14 only if router edited) |
| `router.py` | P6, P14, P15 |
| `workflow.py` | P6, P9, P15 (and the queue-ordering + e2e tests) |
| `audit.py` | P15 |
| `models.py` (extending RouteTrace or AnalysisResult) | P10, P15 |

Run command:

```bash
python -m pytest tests/property -q --hypothesis-profile=ci
```

Set `OPENRECALL_PBT_SEED=20260101` for deterministic CI reproduction.
