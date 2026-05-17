# Requirements Document

## Introduction

OpenRecall is an alert triage co-pilot for SOC analysts and on-call SRE/developers, built on top of the existing `incident-memory-agent/` Streamlit cockpit for the Hindsight x cascadeflow hackathon. OpenRecall reframes the project from a one-incident-at-a-time RCA workspace into a queue-driven triage workflow with **counterfactual memory**: every retained alert carries the analyst's final triage decision (false_positive, duplicate, known_benign, real, escalated) and the dead ends that prior responders already explored.

Three pillars earn rubric points and constrain every requirement below:

1. **Counterfactual memory + auto-triage.** Hindsight is consulted before any expensive model call. When prior decisions are consistent enough, OpenRecall proposes an auto-triage decision and the strong model is bypassed entirely.
2. **Cost curve visibility.** The cockpit renders cost-per-alert dropping over time as memory grows, with an explicit comparison against a strong-model-only baseline.
3. **Alert DNA fingerprinting.** Alerts are reduced to a structured fingerprint (error_class, service_role, dependency_pattern, signal_shape, attack_pattern, environment) instead of free-text keyword overlap, and Hindsight retrieval keys on that fingerprint.

OpenRecall extends the existing repository (`incident-memory-agent/`) rather than replacing it. All current files (`app.py`, `incident_agent/models.py`, `incident_agent/memory.py`, `incident_agent/router.py`, `incident_agent/workflow.py`, `data/seed_incidents.json`, `data/sample_alerts.json`, `scripts/smoke_test.py`, `.github/workflows/ci.yml`, `Makefile`) remain in place, are extended, and continue to compile and pass the deterministic smoke test in offline mode.

The primary memory backend changes from local Hindsight Docker to **Hindsight Cloud** at `https://api.hindsight.vectorize.io`, accessed through the `hindsight-client` SDK. The local JSON fallback is preserved and must produce structurally identical analysis output so judges can demo offline.

### Personas Covered

- **Maya, SOC Analyst (Tier 1).** Triages 200-500 SIEM alerts per shift, of which 40-50% are false positives from misconfigured scanners, scheduled jobs, and internal pen tests. Wants memory to pre-judge low-risk repeats.
- **Devon, Senior SRE on-call.** Wakes up at 2am to PagerDuty pages. Wants instant context on whether the team has seen this signature before, what was tried, and what made it worse.
- **Orchestrator (system role).** The OpenRecall workflow itself, responsible for fingerprint generation, memory recall, auto-triage proposal, escalation, retention, and cost/audit reporting.

### Out of Scope

The following are explicitly excluded from this spec:

- Slack, Teams, or email ingestion adapters.
- Real PagerDuty, Datadog, Splunk, Sentinel, or Chronicle webhooks. Synthetic data only.
- Cross-organization memory federation or a public commons.
- Healthcare, aviation, or customer-support pivots.
- Multi-tenancy, authentication, SSO, or per-analyst access control. Single-user demo only.
- Pre-deploy incident prediction (Cassandra-style features).

## Glossary

- **OpenRecall_System** — The end-to-end Streamlit cockpit plus `incident_agent` package that ingests alerts, fingerprints them, consults memory, proposes triage decisions, escalates when needed, and retains decisions.
- **Alert** — A single incoming triage signal (raw text payload plus optional metadata) representing one SIEM/pager event for Maya or Devon.
- **AlertFingerprint** — A structured Pydantic v2 record with fields `error_class`, `service_role`, `dependency_pattern`, `signal_shape`, `attack_pattern`, and `environment`, used as the canonical key for memory retrieval.
- **Fingerprint_Generator** — The component (`incident_agent/fingerprint.py`) that produces an AlertFingerprint from raw alert text using the cheap model first, with a deterministic regex fallback.
- **TriageDecision** — Enumerated string value: one of `false_positive`, `duplicate`, `known_benign`, `real`, `escalated`.
- **TriageResult** — A Pydantic v2 record carrying the proposed TriageDecision, a `triage_confidence` in `[0.0, 1.0]`, the supporting MemoryMatch list, the count of consistent prior decisions, and a `requires_human_approval` flag.
- **Triage_Engine** — The component (`incident_agent/triage.py`) that converts an AlertFingerprint plus recalled memory into a TriageResult and decides whether to bypass the strong model.
- **Memory_Adapter** — The extended `IncidentMemory` class in `incident_agent/memory.py` that stores and retrieves memories by fingerprint and TriageDecision, talks to Hindsight Cloud, and falls back to `data/local_memory.json`.
- **Hindsight_Client** — The `hindsight-client` SDK instance configured for `https://api.hindsight.vectorize.io` with API key sourced from `HINDSIGHT_API_KEY`.
- **Local_Fallback_Store** — The deterministic JSON-backed memory implementation (`data/seed_incidents.json` plus `data/local_memory.json`) that services recall and retain when Hindsight Cloud is unreachable.
- **CascadeFlow_Router** — The extended `CascadeFlowRouter` (`incident_agent/router.py`) that selects between the cheap model (`qwen/qwen3-32b`) and the strong model (`openai/gpt-oss-120b`) on Groq, records each call as a RouteTrace, and exposes a `triage_with_trace` fast-path that may emit zero LLM calls.
- **RouteTrace** — Existing Pydantic record extended for OpenRecall to include `triage_decision_proposed`, `memory_match_score`, `decision_consistency`, and `llm_skipped` fields.
- **Workflow_Orchestrator** — The extended `IncidentWorkflow` (`incident_agent/workflow.py`) exposing both `analyze(raw_alert)` (single) and `analyze_queue(alerts)` (batch) entry points.
- **Cost_Curve_Tracker** — The component that aggregates RouteTrace cost data across an alert batch and exposes a time-ordered series of (alert_index, cost_usd, baseline_cost_usd) tuples for the UI chart.
- **Audit_Trace_Recorder** — The serializer that produces the visible per-alert decision log (model used, route reason, memory hits, decision proposed, escalation reason, live-call status).
- **Streamlit_Cockpit** — The extended `app.py` UI that adds a queue/batch view, per-alert auto-triage badges, the cost curve chart, dead_ends capture in the retain flow, and the analyst override flow.
- **Override_Flow** — The UI affordance that lets an analyst accept the proposed TriageDecision, override it with a different decision, and optionally attach `dead_ends`.
- **DeadEnd** — A free-text string captured during retain that records a hypothesis or remediation that was tried and disproven during a prior incident (e.g., "tried restarting DB pods, made it worse").
- **AnalysisResult** — The existing top-level Pydantic record returned by the workflow, extended for OpenRecall with `alert_fingerprint`, `triage_result`, and `cost_curve_point` fields.
- **Pretty_Printer** — The function that serializes an AlertFingerprint back into its canonical string form, paired with the parser to support the round-trip property.
- **Fingerprint_Parser** — The function that parses a serialized fingerprint string back into an AlertFingerprint instance.
- **Strong_Match** — A MemoryMatch whose score is `>= 0.85`.
- **Decision_Consistency** — The fraction in `[0.0, 1.0]` of recalled prior decisions that share the dominant TriageDecision among Strong_Matches for an alert.
- **Run_Budget** — The per-batch USD ceiling enforced by CascadeFlow_Router, sourced from `CASCADEFLOW_RUN_BUDGET_USD`.
- **Demo_Mode** — Operating mode where `CASCADEFLOW_LIVE_GROQ=false`; deterministic outputs are produced and live API calls are suppressed while routing/cost trace is still emitted.

## Requirements

### Requirement 1: Single-Alert Ingestion (Backwards Compatibility)

**User Story:** As Devon (on-call SRE), I want to paste a single PagerDuty page into the cockpit and get an analysis back, so that the existing single-alert workflow continues to work after OpenRecall is added.

#### Acceptance Criteria

1. WHEN an analyst submits a single raw alert string through the Streamlit_Cockpit, THE Workflow_Orchestrator SHALL produce an AnalysisResult whose schema is a strict superset of the pre-OpenRecall AnalysisResult.
2. THE Workflow_Orchestrator SHALL expose an `analyze(raw_alert: str) -> AnalysisResult` method that preserves the existing call signature.
3. WHEN the existing `data/sample_alerts.json` fixtures are submitted one at a time, THE OpenRecall_System SHALL produce a non-empty `route_trace`, a non-empty `verification_commands` list, and a populated `incident` field for every fixture.
4. WHEN a single alert is analyzed, THE Workflow_Orchestrator SHALL populate `alert_fingerprint`, `triage_result`, and `cost_curve_point` on the AnalysisResult.

### Requirement 2: Batch and Queue Alert Ingestion

**User Story:** As Maya (SOC analyst), I want to upload a batch of alerts at once and watch them stream through triage, so that I can see memory pre-judge the repeats while I focus only on the novel cases.

#### Acceptance Criteria

1. THE Workflow_Orchestrator SHALL expose an `analyze_queue(alerts: list[Alert]) -> list[AnalysisResult]` method that processes alerts in submission order.
2. WHEN an analyst uploads a batch of alerts through the Streamlit_Cockpit, THE OpenRecall_System SHALL accept either a JSON file conforming to `data/seed_alerts.json` schema or a paste-in JSON array.
3. WHEN a batch is submitted, THE Streamlit_Cockpit SHALL render one row per alert in queue order, each row showing fingerprint summary, proposed TriageDecision, triage_confidence, escalation reason, and an Override_Flow control.
4. WHILE a batch is being processed, THE Workflow_Orchestrator SHALL make memory written by alert N available to recall calls for alert N+1 within the same batch.
5. IF the batch input is malformed JSON or an entry is missing the `raw_alert` field, THEN THE OpenRecall_System SHALL display a per-row validation error and continue processing the remaining valid entries.
6. THE OpenRecall_System SHALL ship a synthetic `data/seed_alerts.json` fixture containing approximately 100 alerts spanning repeats, false positives, novel real incidents, and security signals across both personas.

### Requirement 3: Alert Fingerprint Generation

**User Story:** As the Orchestrator, I want every alert reduced to a structured AlertFingerprint, so that memory retrieval keys on alert DNA instead of fragile keyword overlap.

#### Acceptance Criteria

1. WHEN an alert enters the workflow, THE Fingerprint_Generator SHALL produce an AlertFingerprint with the fields `error_class`, `service_role`, `dependency_pattern`, `signal_shape`, `attack_pattern`, and `environment`.
2. THE Fingerprint_Generator SHALL first attempt cheap-model fingerprint extraction via the CascadeFlow_Router using model `qwen/qwen3-32b`.
3. IF the cheap-model call fails, returns malformed JSON, or `CASCADEFLOW_LIVE_GROQ` is `false`, THEN THE Fingerprint_Generator SHALL produce a deterministic regex-based AlertFingerprint from the raw alert text.
4. WHEN identical raw alert text is passed to the Fingerprint_Generator twice within the same process and Demo_Mode is active, THE Fingerprint_Generator SHALL return AlertFingerprint values that compare equal.
5. THE Fingerprint_Generator SHALL emit one RouteTrace entry for the fingerprinting step, populated with model name, latency_ms, estimated_cost_usd, and `step="alert fingerprint"`.
6. THE Pretty_Printer SHALL serialize an AlertFingerprint into a canonical string form whose ordering of fields is stable across runs.
7. WHEN a serialized AlertFingerprint string is passed to the Fingerprint_Parser, THE Fingerprint_Parser SHALL produce an AlertFingerprint that compares equal to the original (round-trip property).

### Requirement 4: Memory Recall Keyed on Fingerprint

**User Story:** As the Orchestrator, I want recall to return prior alerts whose fingerprint matches the incoming alert, so that retrieval surfaces the right precedents instead of loose keyword neighbors.

#### Acceptance Criteria

1. THE Memory_Adapter SHALL expose `recall_by_fingerprint(fingerprint: AlertFingerprint, limit: int = 5) -> list[MemoryMatch]`.
2. WHEN `recall_by_fingerprint` is called, THE Memory_Adapter SHALL query Hindsight Cloud first if the Hindsight_Client is initialized.
3. THE Memory_Adapter SHALL expose `recall_by_decision(fingerprint: AlertFingerprint, decision: TriageDecision, limit: int = 5) -> list[MemoryMatch]` that filters recall results by the prior TriageDecision.
4. WHEN Hindsight Cloud is unreachable, returns an error, or `HINDSIGHT_API_KEY` is unset, THE Memory_Adapter SHALL fall back to the Local_Fallback_Store for the same recall query and SHALL set `fallback_mode=True` on the resulting AnalysisResult.
5. THE Memory_Adapter SHALL return MemoryMatch objects whose `score` field is a float in the closed interval `[0.0, 1.0]`.
6. WHEN no fingerprint field overlap exists between the query and any stored memory, THE Memory_Adapter SHALL return an empty list rather than raising.

### Requirement 5: Auto-Triage Decision Engine

**User Story:** As Maya, I want the system to pre-judge an alert based on memory before invoking expensive models, so that obvious repeats are dispatched in seconds.

#### Acceptance Criteria

1. WHEN the Workflow_Orchestrator receives an alert, THE Triage_Engine SHALL compute a TriageResult before any strong-model call is issued.
2. THE Triage_Engine SHALL compute `triage_confidence` as a float in the closed interval `[0.0, 1.0]`.
3. WHEN at least one MemoryMatch is a Strong_Match (score `>= 0.85`) AND Decision_Consistency among Strong_Matches is `>= 0.9`, THE Triage_Engine SHALL set `proposed_decision` to the dominant prior TriageDecision and set `requires_human_approval` to `True`.
4. IF no MemoryMatch is a Strong_Match OR Decision_Consistency is `< 0.9`, THEN THE Triage_Engine SHALL set `proposed_decision` to `escalated`.
5. THE Triage_Engine SHALL include the source MemoryMatch list and the integer count of consistent prior decisions in the TriageResult.
6. WHEN the alert AlertFingerprint has `attack_pattern` populated with a non-empty value AND no Strong_Match exists in memory, THE Triage_Engine SHALL set `proposed_decision` to `escalated` regardless of any other signal.

### Requirement 6: Strong-Model Escalation Rules

**User Story:** As Devon, I want the strong model invoked only when memory is genuinely weak or the alert is security-novel, so that the cost curve actually drops as memory grows.

#### Acceptance Criteria

1. WHEN the TriageResult `proposed_decision` is one of `false_positive`, `duplicate`, or `known_benign` AND `triage_confidence >= 0.85`, THE CascadeFlow_Router SHALL skip the strong-model call and SHALL emit a RouteTrace with `llm_skipped=True` and `model="memory-bypass"`.
2. WHEN the TriageResult `proposed_decision` is `escalated`, THE CascadeFlow_Router SHALL invoke the strong model `openai/gpt-oss-120b` for full RCA generation.
3. WHEN the TriageResult `proposed_decision` is `real`, THE CascadeFlow_Router SHALL invoke the strong model and SHALL surface `dead_ends` from the matched memories in the strong-model prompt.
4. THE CascadeFlow_Router SHALL never invoke the strong model when memory match score is `>= 0.85` AND Decision_Consistency is `>= 0.9` AND `attack_pattern` is empty.
5. THE CascadeFlow_Router SHALL record one RouteTrace per LLM step taken, including the bypass step when no LLM is called.
6. IF the per-batch accumulated cost reaches the Run_Budget, THEN THE CascadeFlow_Router SHALL log a `budget_exhausted=True` RouteTrace flag and SHALL fall back to deterministic outputs for the remainder of the batch.

### Requirement 7: Dead-Ends Capture and Retrieval

**User Story:** As Devon, I want to know which hypotheses prior responders already disproved on similar alerts, so that I do not re-walk dead paths at 2am.

#### Acceptance Criteria

1. THE Workflow_Orchestrator SHALL include a `dead_ends: list[str]` field on the AnalysisResult, populated from the union of `dead_ends` on all MemoryMatch records returned by recall.
2. WHEN the Streamlit_Cockpit renders an AnalysisResult, THE Streamlit_Cockpit SHALL display the `dead_ends` list in a dedicated "Skip these paths" panel.
3. THE Override_Flow SHALL accept zero or more free-text DeadEnd entries from the analyst at retain time.
4. WHEN an analyst retains a memory with non-empty `dead_ends`, THE Memory_Adapter SHALL persist them as part of the memory record's metadata.
5. WHEN recall returns prior memories whose metadata contains `dead_ends`, THE Memory_Adapter SHALL preserve them in the MemoryMatch metadata field for downstream rendering.

### Requirement 8: Retain Flow with Triage Decision

**User Story:** As Maya, I want my final triage decision and any disproven hypotheses written back to memory, so that the next analyst inherits my conclusion instead of re-deriving it.

#### Acceptance Criteria

1. THE Memory_Adapter SHALL expose `retain(fingerprint: AlertFingerprint, decision: TriageDecision, dead_ends: list[str], analyst_id: str | None, business_impact_minutes: int | None, ...)` that stores the triage outcome.
2. WHEN an analyst submits a retain action through the Override_Flow, THE Streamlit_Cockpit SHALL pass the chosen TriageDecision, captured DeadEnd list, optional analyst_id, and optional business_impact_minutes to the Memory_Adapter.
3. WHEN a retain call targets a memory whose `(fingerprint, decision, content)` tuple already exists in the store, THE Memory_Adapter SHALL not create a duplicate record (idempotent retain).
4. THE Memory_Adapter SHALL return a status string indicating whether the memory was retained in Hindsight Cloud, retained in the Local_Fallback_Store, or skipped as a duplicate.
5. WHEN retain succeeds in either backend, THE Memory_Adapter SHALL make the new memory visible to the next `recall_by_fingerprint` call within the same process without requiring a restart.
6. THE OpenRecall_System SHALL extend `data/seed_incidents.json` so every seed record exposes a `triage_decision` field and a `dead_ends` list (empty by default).

### Requirement 9: Cost Curve Visibility

**User Story:** As a hackathon judge, I want to see live cost-per-alert dropping as the queue grows, so that the cascadeflow value is unmistakable in 60 seconds.

#### Acceptance Criteria

1. THE Cost_Curve_Tracker SHALL maintain an in-memory time-ordered series of `(alert_index: int, cost_usd: float, baseline_cost_usd: float)` tuples for every analyzed alert in the current cockpit session.
2. THE Streamlit_Cockpit SHALL render a chart of OpenRecall cost-per-alert versus strong-model-only baseline cost-per-alert across the analyzed alerts.
3. THE Streamlit_Cockpit SHALL display a numeric "savings vs strong-model-only" panel showing total cost, total baseline, and percentage saved for the current session.
4. WHEN an alert is analyzed and its TriageResult triggers an LLM-bypass per Requirement 6.1, THE Cost_Curve_Tracker SHALL record `cost_usd=0.0` for that alert while preserving the strong-model baseline_cost_usd.
5. WHEN multiple batches are processed in sequence within the same cockpit session, THE running mean cost-per-alert SHALL be available as `mean_cost_per_alert(batch_id)` for downstream assertions and the cost chart SHALL reflect the cumulative series.

### Requirement 10: Audit Trace and Route Visibility

**User Story:** As a judge, I want every triage decision auditable end-to-end, so that I can see which model ran, why, and what memory was consulted.

#### Acceptance Criteria

1. THE Audit_Trace_Recorder SHALL produce, per alert, a record containing: AlertFingerprint, list of recalled MemoryMatch summaries with scores, TriageResult, every RouteTrace emitted, total cost, baseline cost, savings, and live-call status.
2. THE Streamlit_Cockpit SHALL render the audit record under each alert row in collapsible form, showing model name, route reason, memory hit count, proposed decision, and escalation reason.
3. WHEN an LLM bypass occurs, THE Audit_Trace_Recorder SHALL record `llm_skipped=True`, `model="memory-bypass"`, and a route_reason string referencing the matched memory titles.
4. THE RouteTrace records SHALL preserve the existing fields (`step`, `model`, `route_reason`, `confidence`, `latency_ms`, `estimated_cost_usd`, `strong_model_baseline_cost_usd`, `savings_vs_strong_usd`, `escalated`, `cascadeflow_enabled`, `live_model_call`, `model_error`, `budget_remaining_usd`) and SHALL add `triage_decision_proposed`, `memory_match_score`, `decision_consistency`, and `llm_skipped`.

### Requirement 11: Hindsight Cloud Primary, Local Fallback Parity

**User Story:** As a judge running offline, I want the demo to behave identically when Hindsight Cloud is unreachable, so that a flaky network never breaks the cockpit.

#### Acceptance Criteria

1. THE Memory_Adapter SHALL read `HINDSIGHT_BASE_URL` defaulting to `https://api.hindsight.vectorize.io`, `HINDSIGHT_API_KEY` from environment only, and `HINDSIGHT_BANK_ID` defaulting to `openrecall`.
2. WHEN `HINDSIGHT_API_KEY` is set and Hindsight Cloud is reachable, THE Memory_Adapter SHALL initialize the Hindsight_Client and SHALL set `fallback_mode=False` on AnalysisResult instances it produces.
3. WHEN `HINDSIGHT_API_KEY` is unset, the Hindsight_Client raises during initialization, or any Hindsight Cloud request fails, THE Memory_Adapter SHALL switch to the Local_Fallback_Store for the remainder of the session and SHALL set `fallback_mode=True` on subsequent AnalysisResult instances.
4. WHEN the same alert is analyzed twice with identical AlertFingerprint, once with the Hindsight_Client active and once in fallback mode, THE OpenRecall_System SHALL produce AnalysisResult instances whose Pydantic schemas are structurally identical (same field names, same field types, same nested model classes).
5. THE Local_Fallback_Store SHALL service `recall_by_fingerprint`, `recall_by_decision`, and `retain` with the same method signatures and return types as the Hindsight Cloud path.
6. WHEN the deterministic smoke test runs with `HINDSIGHT_BASE_URL` set to an unreachable host, THE OpenRecall_System SHALL complete the queue/batch flow, the auto-triage flow, and the dead_ends capture flow without error.

### Requirement 12: Secrets and Configuration Handling

**User Story:** As a maintainer, I want all credentials handled outside source control, so that no live key gets pushed to the public hackathon repo.

#### Acceptance Criteria

1. THE OpenRecall_System SHALL read every API key (`GROQ_API_KEY`, `HINDSIGHT_API_KEY`) from process environment variables only.
2. THE repository `.gitignore` SHALL include `.env`, `.streamlit/secrets.toml`, and `data/local_memory.json`.
3. THE `.env.example` file SHALL list `HINDSIGHT_BASE_URL`, `HINDSIGHT_API_KEY`, `HINDSIGHT_BANK_ID`, `GROQ_API_KEY`, `CASCADEFLOW_MODE`, `CASCADEFLOW_LIVE_GROQ`, `CASCADEFLOW_RUN_BUDGET_USD`, `CASCADEFLOW_CHEAP_MODEL`, and `CASCADEFLOW_STRONG_MODEL` with placeholder values only and SHALL contain no live keys.
4. IF a tracked file in the repository contains a string matching `gsk_[A-Za-z0-9_]{20,}` or `hsk_[A-Za-z0-9_]{20,}`, THEN the repository SHALL be considered non-compliant and the value SHALL be moved to `.env` before the spec is considered complete.
5. WHEN a required environment variable is unset and a code path needs it, THE OpenRecall_System SHALL log a non-fatal warning, fall back to deterministic or fallback behavior per the relevant requirement, and SHALL NOT crash the cockpit.

### Requirement 13: Streamlit Cockpit Queue View and Override Flow

**User Story:** As Maya, I want a queue UI that shows me at a glance which alerts memory has already pre-judged, so that I can accept-all the obvious false positives and focus on the rest.

#### Acceptance Criteria

1. THE Streamlit_Cockpit SHALL expose a "Queue" view that lists analyzed alerts in submission order with columns for fingerprint summary, proposed TriageDecision badge, triage_confidence, escalation reason, and an Override_Flow control.
2. WHEN an analyst clicks the Override_Flow control on a queue row, THE Streamlit_Cockpit SHALL render a form that accepts: chosen TriageDecision, optional dead_ends, optional analyst_id, optional business_impact_minutes.
3. WHEN the analyst submits the Override_Flow, THE Streamlit_Cockpit SHALL invoke `Memory_Adapter.retain(...)` with the chosen values and SHALL refresh the queue row to reflect the persisted decision.
4. THE Streamlit_Cockpit SHALL render a per-batch summary showing alert count, count auto-decided by memory, count escalated to the strong model, total cost, and total savings vs strong-only.
5. WHEN no AlertFingerprint matches any prior memory, THE Streamlit_Cockpit SHALL clearly mark the alert "Novel — no prior memory" so the analyst knows to invest the full investigation effort.

### Requirement 14: Repository Hygiene and Existing Targets

**User Story:** As a maintainer, I want CI and the existing make targets to keep working after OpenRecall lands, so that the hackathon submission stays demo-ready.

#### Acceptance Criteria

1. THE repository SHALL pass `python -m compileall app.py incident_agent seed_memory.py scripts/smoke_test.py` after OpenRecall is added.
2. THE existing `make install`, `make run`, and `make smoke` targets SHALL remain functional and SHALL not require live network access for `make smoke`.
3. WHEN `scripts/smoke_test.py` runs in CI with `HINDSIGHT_BASE_URL` pointed at an unreachable host and `CASCADEFLOW_LIVE_GROQ=false`, THE smoke test SHALL exercise the queue/batch entry point, assert at least one auto-triage bypass occurs against seeded memory, and SHALL exit zero.
4. THE OpenRecall_System SHALL ship a `make pbt` target (or equivalent invocation in CI) that runs the property-based tests defined in Requirement 15 with a deterministic seed.
5. THE existing `data/seed_incidents.json` and `data/sample_alerts.json` files SHALL remain readable, and any new fields added to seed records SHALL default to safe values for existing consumers.

### Requirement 15: Property-Based Test Coverage for Correctness Properties

**User Story:** As a maintainer, I want the central correctness invariants of OpenRecall expressed as Hypothesis property tests, so that regressions in fingerprinting, retain idempotence, and cost-curve monotonicity get caught before the demo.

#### Acceptance Criteria

1. THE OpenRecall_System SHALL ship Hypothesis-based property tests covering each correctness property listed in the "Correctness Properties" section of this document.
2. THE property test suite SHALL be runnable via a single command (`make pbt` or `python -m pytest tests/property/`) and SHALL exit zero on a clean working tree.
3. THE property test suite SHALL use a fixed random seed in CI to keep failure cases reproducible.
4. WHEN a property test fails, THE test runner SHALL surface the falsifying input from Hypothesis verbatim in the failure message.

## Correctness Properties

These are the central invariants OpenRecall must preserve. Each is testable as a Hypothesis property unless flagged otherwise.

1. **Fingerprint determinism (Demo_Mode).** For any raw_alert string, two consecutive calls to `Fingerprint_Generator.generate(raw_alert)` in Demo_Mode SHALL return AlertFingerprint instances that compare equal. (Pattern: invariant.)

2. **Fingerprint round-trip.** For any AlertFingerprint `fp`, `Fingerprint_Parser.parse(Pretty_Printer.format(fp))` SHALL equal `fp`. (Pattern: round-trip.)

3. **Triage proposal determinism.** Given the same AlertFingerprint `fp` and the same persisted memory state `M`, `Triage_Engine.triage(fp, recall_by_fingerprint(fp))` SHALL produce a TriageResult whose `proposed_decision`, `triage_confidence`, and `requires_human_approval` fields are equal across two consecutive invocations. (Pattern: invariant.)

4. **Triage confidence bounds.** For every TriageResult produced by `Triage_Engine.triage(...)`, `0.0 <= triage_confidence <= 1.0`. (Pattern: invariant.)

5. **Confidence reflects history.** WHEN Decision_Consistency is `c` over `n >= 1` Strong_Matches, THE TriageResult `triage_confidence` SHALL satisfy `triage_confidence <= c` and `triage_confidence >= c * (n / (n + 1))`. (Pattern: metamorphic — confidence is monotonic in agreement and grows with evidence count.)

6. **Strong-model bypass invariant.** For any alert whose recall set contains at least one Strong_Match (`score >= 0.85`) AND Decision_Consistency `>= 0.9` AND `attack_pattern` is empty, the resulting AnalysisResult `route_trace` SHALL contain zero entries with `model == "openai/gpt-oss-120b"` and `live_model_call == True`. (Pattern: invariant.)

7. **Idempotent retain.** For any retain inputs `(fingerprint, decision, content, dead_ends, analyst_id)`, calling `Memory_Adapter.retain(...)` twice in succession SHALL leave the underlying store with exactly one matching record. (Pattern: idempotence.)

8. **Cost-curve monotonicity under repeating distribution.** Given a finite alert distribution `D` and two batches `B1, B2` sampled iid from `D` and processed in order with retain enabled between batches, the mean OpenRecall cost-per-alert over `B2` SHALL be `<= mean_cost_per_alert(B1)`. (Pattern: metamorphic — memory growth never raises mean cost on the same distribution.)

9. **Cost-curve never exceeds baseline.** For every alert processed, `cost_usd <= baseline_cost_usd` recorded in the corresponding cost-curve point. (Pattern: invariant.)

10. **Fallback-vs-cloud structural parity.** For any alert and any memory state replayable in both backends, AnalysisResult instances produced in Demo_Mode by the Hindsight Cloud path and the Local_Fallback_Store path SHALL share the same Pydantic class, the same set of field names, and the same nested model classes per field. (Pattern: invariant — schema parity, value equality is not required.)

11. **No-Strong-Match implies escalation.** For any alert whose recall set contains zero Strong_Matches, the resulting TriageResult `proposed_decision` SHALL equal `escalated`. (Pattern: invariant — derived from Requirement 5.4.)

12. **Security-novel bypass refusal.** For any alert whose AlertFingerprint has a non-empty `attack_pattern` AND zero Strong_Matches in recall, the Triage_Engine SHALL set `proposed_decision = escalated`. (Pattern: invariant — derived from Requirement 5.6.)

13. **Recall-then-retain consistency.** After `retain(fp, decision, content, ...)` succeeds for fingerprint `fp`, the next `recall_by_fingerprint(fp)` call SHALL return at least one MemoryMatch whose metadata reflects the retained `decision`. (Pattern: round-trip — write-then-read.)

14. **Budget enforcement.** The sum of `estimated_cost_usd` across all `live_model_call=True` RouteTrace entries within a single batch SHALL be `<= CASCADEFLOW_RUN_BUDGET_USD + estimated_cost_usd_of_final_in_flight_call`. (Pattern: invariant — best-effort enforcement allows the call in flight when the budget is hit, but no further live calls are issued.)

15. **Audit trace completeness.** For every analyzed alert, the AuditTrace SHALL contain exactly one entry per LLM step taken (including bypass), and `len(audit_trace_entries) == len(route_trace)`. (Pattern: invariant.)
