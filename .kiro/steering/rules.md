---
inclusion: always
---

# OpenRecall — Master Rules

This is the **authoritative rules contract** for every change made in this
workspace. It is loaded on every turn. When any other steering file, hook,
skill, or chat instruction conflicts with these rules, **rules.md wins**
unless the user explicitly overrides a specific rule by ID in the same
turn (e.g., "ignore RULE-SEC-04 for this commit").

Rules are grouped by domain and given stable IDs. Cite the rule ID (e.g.,
`RULE-SPEC-02`) when you invoke or override a rule in a response.

---

## 0. How to use this file

- **MUST** = hard requirement; refuse the request or stop and ask the user
  if it cannot be satisfied.
- **MUST NOT** = absolute prohibition; refuse and explain.
- **SHOULD** = strong preference; deviate only with a stated reason.
- **MAY** = explicitly permitted optional behavior.

When a rule references a requirement (`R<X>.<Y>`) or property (`P<N>`),
the source of truth is `.kiro/specs/openrecall/requirements.md`. When a
rule references an idiom or anti-pattern, the source is
`.kiro/steering/tech.md`.

---

## 1. Spec is the contract — `RULE-SPEC-*`

- **RULE-SPEC-01 (MUST).** Every code change must trace to at least one
  requirement ID (`R<X>.<Y>`) or property ID (`P<N>`). Cite the IDs in the
  PR description, the commit message, or the chat reply that proposes the
  change. If a change has no spec anchor, **first** propose the requirement
  edit, get user approval, then code.
- **RULE-SPEC-02 (MUST).** Do not silently expand scope. The hard non-goals
  in `product.md` (no Slack/Teams/email ingestion, no real PD/Datadog/Splunk
  webhooks, no multi-tenancy, no auth, no pre-deploy prediction) are
  off-limits unless the user explicitly opens scope.
- **RULE-SPEC-03 (MUST).** When you change a Pydantic model, a triage
  threshold, an env var, or a `RouteTrace` field, also update every
  downstream cell in the **"Where things live" decision matrix** in
  `structure.md`. Use that table as a checklist; do not skip rows.
- **RULE-SPEC-04 (SHOULD).** When the user asks for analysis, comparison,
  or options, answer with analysis only. Implement only after the user
  picks a direction.
- **RULE-SPEC-05 (MUST).** Backward-compat surface is frozen:
  `IncidentWorkflow.analyze(raw_alert: str) -> AnalysisResult`. New
  `AnalysisResult` fields must have safe defaults. The signature tests in
  `tests/test_signatures.py` are the gate.

## 2. Code style and idioms — `RULE-CODE-*`

- **RULE-CODE-01 (MUST).** All Python files start with
  `from __future__ import annotations`. Target Python 3.11+.
- **RULE-CODE-02 (MUST).** Pydantic v2 only. Use `ConfigDict`,
  `Field(default_factory=...)`, `model_dump()`, `model_fields`. Refuse
  v1 patterns (`class Config:`, `.dict()`, `.json()`).
- **RULE-CODE-03 (MUST).** Use built-in generics (`list[X]`,
  `dict[str, Y]`, `X | None`). Never import `Optional`, `List`, `Dict`
  from `typing`.
- **RULE-CODE-04 (MUST).** Triage thresholds live as module-level
  `Final[float]` constants in `incident_agent/triage.py`
  (`STRONG_MATCH_THRESHOLD=0.85`, `DECISION_CONSISTENCY_THRESHOLD=0.9`,
  `BYPASS_CONFIDENCE_THRESHOLD=0.85`). **MUST NOT** inline a threshold
  literal anywhere else; reference the named constant.
- **RULE-CODE-05 (MUST).** Construct deterministic RNGs as
  `random.Random(seed)`. **MUST NOT** call `random.seed(...)` (mutates
  global state).
- **RULE-CODE-06 (MUST).** `format_fingerprint` is imported **inside**
  `IncidentMemory` method bodies, not at module top, to avoid the
  fingerprint↔memory cycle. Preserve this pattern.
- **RULE-CODE-07 (MUST).** Streamlit adapters (`IncidentMemory`,
  `CascadeFlowRouter`, `CostCurveTracker`) are wrapped in
  `@st.cache_resource`. Static data files load via `@st.cache_data`.
- **RULE-CODE-08 (SHOULD).** Public methods on `incident_agent/*.py`
  carry full type annotations on parameters and return types.
- **RULE-CODE-09 (MUST).** Follow the import order specified in
  `structure.md`: future, stdlib, third-party, first-party (relative).
- **RULE-CODE-10 (MUST NOT).** Never hard-code the strings
  `"qwen/qwen3-32b"`, `"openai/gpt-oss-120b"`, or
  `"https://api.hindsight.vectorize.io"` outside of
  `.env.example` and the configuration table. Read them from env vars.

## 3. Triage and bypass invariants — `RULE-TRIAGE-*`

- **RULE-TRIAGE-01 (MUST).** A `model="memory-bypass"` `RouteTrace` step
  is emitted **iff** all four conditions hold:
  (a) `Strong_Match.score >= STRONG_MATCH_THRESHOLD`,
  (b) `Decision_Consistency >= DECISION_CONSISTENCY_THRESHOLD`,
  (c) `triage_confidence >= BYPASS_CONFIDENCE_THRESHOLD`,
  (d) `attack_pattern` is empty AND the dominant decision is in
  `{false_positive, duplicate, known_benign}`.
  This is `P11` + `P12`.
- **RULE-TRIAGE-02 (MUST).** When the bypass step is emitted, the strong
  model **MUST NOT** be called and `cost_usd` for that alert **MUST** be
  `0.0`. `baseline_cost_usd` is preserved so the savings band stays
  meaningful (`R9.4`, `P9`).
- **RULE-TRIAGE-03 (MUST).** When the proposed decision is `escalated` or
  `real`, the workflow **MUST** pass `force_strong_model=True` to
  `rca_with_trace`, regardless of any other heuristic (`R6.2`, `R6.3`).
- **RULE-TRIAGE-04 (MUST).** `len(audit_trace) == len(route_trace)` for
  every analysis. Adding a `RouteTrace` step without a matching
  `AuditTraceEntry` is a P15 violation.
- **RULE-TRIAGE-05 (MUST).** Attack-pattern presence (non-empty string)
  blocks bypass unconditionally. No exceptions, no overrides.

## 4. Memory + Hindsight Cloud — `RULE-MEMORY-*`

- **RULE-MEMORY-01 (MUST).** Every `client.recall` and `client.retain`
  call is wrapped in try/except. On failure, call `_flip_to_fallback`,
  which **MUST** close the Hindsight client and drop the reference for
  the rest of the session (`R11.3`).
- **RULE-MEMORY-02 (MUST).** `retain` is idempotent on the dedupe key.
  Re-running `retain` with the same `(fingerprint, decision)` does not
  duplicate the row (`P7`, `P13`).
- **RULE-MEMORY-03 (MUST).** Local fallback reads from
  `data/seed_incidents.json` and writes to `data/local_memory.json`.
  Both files are gitignored.
- **RULE-MEMORY-04 (MUST).** Memory matches retrieved from Hindsight
  Cloud are scored client-side; never trust a server-supplied score
  field that bypasses the local thresholding logic.

## 5. Cost curve — `RULE-COST-*`

- **RULE-COST-01 (MUST).** `CostCurveTracker.record()` is called once
  per analyzed alert, with `(cost_usd, baseline_cost_usd)` both populated.
  Bypass alerts pass `cost_usd=0.0`.
- **RULE-COST-02 (MUST).** Cumulative cost is monotonic non-decreasing
  (`P8`). The savings band `baseline_cumulative - actual_cumulative` is
  monotonic non-decreasing (`P14`).
- **RULE-COST-03 (MUST).** Altair chart uses the layered framework in
  `app.py`. Do not introduce a second charting library.

## 6. Security and secrets — `RULE-SEC-*`

- **RULE-SEC-01 (MUST).** Every API key is read from environment
  variables only. **MUST NOT** be hard-coded, logged, or echoed back in
  responses (`R12.1`).
- **RULE-SEC-02 (MUST).** `.gitignore` must include `.env`,
  `.streamlit/secrets.toml`, and `data/local_memory.json` (`R12.2`).
- **RULE-SEC-03 (MUST).** `.env.example` carries placeholder values only.
  A live key in `.env.example` is a P0 incident — fix immediately
  (`R12.3`).
- **RULE-SEC-04 (MUST).** Any tracked file matching the regex
  `gsk_[A-Za-z0-9_]{20,}` or `hsk_[A-Za-z0-9_]{20,}` is non-compliant
  (`R12.4`). The smoke check `smoke_env_example` in
  `scripts/smoke_test.py` enforces this on `.env.example` every CI run.
- **RULE-SEC-05 (MUST).** Reference secrets by env-var name, not value.
  Bad: "the key starts with hsk_fa7..." Good: "the value of
  `HINDSIGHT_API_KEY`."
- **RULE-SEC-06 (MUST).** The current `.env` retains live Hindsight +
  Groq keys for hackathon demo. Before publishing the repo publicly,
  rotate **both** keys at the provider consoles. Use the
  `openrecall-secret-rotate` skill.

## 7. Tests and verification — `RULE-TEST-*`

- **RULE-TEST-01 (MUST).** PBTs run under `OPENRECALL_PBT_SEED=20260101`,
  `HINDSIGHT_BASE_URL=http://127.0.0.1:9`, `CASCADEFLOW_LIVE_GROQ=false`.
  CI is the source of truth for these values.
- **RULE-TEST-02 (MUST).** Every property test docstring carries the tag
  `Feature: openrecall, Property N: <text>` for traceability.
- **RULE-TEST-03 (MUST).** Hypothesis strategies are named
  `<noun>_strategy` and live in `tests/property/conftest.py`.
- **RULE-TEST-04 (MUST).** After any code change, run
  `make compile && make pbt` before declaring done. For changes touching
  the Streamlit cockpit, also run `make smoke`.
- **RULE-TEST-05 (SHOULD).** When fixing a bug, add or extend a property
  test that would have caught it. Cite the property ID in the test
  docstring.
- **RULE-TEST-06 (MUST NOT).** Skip, xfail, or weaken a property test to
  make CI green. If a property is wrong, fix the property; if the code
  is wrong, fix the code. Do not silence the test.

## 8. Git, branches, commits — `RULE-GIT-*`

- **RULE-GIT-01 (MUST).** Push to a new branch; never push to
  `main`/`master` directly.
- **RULE-GIT-02 (MUST).** Stage specific files. **MUST NOT** use
  `git add .` blindly — it can sweep in `.env`, `data/local_memory.json`,
  or `.hypothesis/` cruft.
- **RULE-GIT-03 (MUST).** Commit messages cite at least one R or P ID
  affected by the commit (e.g.,
  `triage: fix bypass on empty attack_pattern (R6.4, P11)`).
- **RULE-GIT-04 (MUST).** Destructive git operations (force push,
  `reset --hard`, `clean -f`, `branch -D`) require explicit user
  permission in the same turn.
- **RULE-GIT-05 (MUST NOT).** Use `--no-verify` to skip hooks. Hooks
  exist for a reason. If a hook fails, fix the cause.
- **RULE-GIT-06 (MUST).** Only commit when the user explicitly asks. If
  intent is unclear, ask first.

## 9. Streamlit cockpit — `RULE-UI-*`

- **RULE-UI-01 (MUST).** `inject_css()` is the styling framework. **MUST
  NOT** replace it; extend it.
- **RULE-UI-02 (MUST).** Badge palette in `app.py` covers every
  `TriageDecision` Literal value. Adding a decision value without
  updating the palette is incomplete.
- **RULE-UI-03 (MUST).** Two tabs: Single Alert and Queue. Do not add a
  third tab without a spec edit.
- **RULE-UI-04 (MUST).** Escalation reason renders directly on the queue
  row (`R2.3`, `R13.1`).

## 10. Response discipline — `RULE-RESP-*`

- **RULE-RESP-01 (MUST).** When investigating, read code before making
  claims. State what was checked and what could not be verified. Do not
  present assumptions as facts.
- **RULE-RESP-02 (SHOULD).** Match response length to task. Simple
  question → short answer. Complex task → thorough response. End-of-task
  summaries: a few sentences unless the user asks for more.
- **RULE-RESP-03 (MUST).** When proposing changes, cite affected R and P
  IDs.
- **RULE-RESP-04 (MUST NOT).** Skip filler acknowledgments
  ("absolutely", "great question"). Respond directly to substance.
- **RULE-RESP-05 (MUST).** If the user is wrong, correct them
  respectfully. Honest feedback over agreement.
- **RULE-RESP-06 (MUST).** If an approach has failed twice, stop and
  diagnose root cause. Do not loop on incremental tweaks.

## 11. Toolkit hygiene — `RULE-KIRO-*`

- **RULE-KIRO-01 (MUST).** Workspace-level Kiro toolkit (steering, hooks,
  skills) lives in `.kiro/` at the workspace root, **never** inside
  `incident-memory-agent/`.
- **RULE-KIRO-02 (MUST).** Hook files use the `.kiro.hook` extension and
  follow the schema in the Kiro feature documentation.
- **RULE-KIRO-03 (MUST).** Skill folders live at `.kiro/skills/<name>/`
  and contain a `SKILL.md` with YAML front-matter (`name`, `description`,
  `keywords`).
- **RULE-KIRO-04 (SHOULD).** Prefer extending an existing steering file
  over creating a new one. New steering should have a clear scope (a
  domain or a file pattern) that no existing file covers.

## 12. Subagents and parallelism — `RULE-AGENT-*`

- **RULE-AGENT-01 (SHOULD).** For unfamiliar codebase exploration, use
  the `context-gatherer` subagent once at the start of a task.
- **RULE-AGENT-02 (SHOULD).** For independent work streams (e.g.,
  parallel file edits with no shared state), delegate to
  `general-task-execution` to preserve main context.
- **RULE-AGENT-03 (MUST NOT).** Re-read files a subagent has already
  analyzed. Trust the subagent's report unless it contradicts a known
  fact.

---

## Cross-references

- Requirements + properties: `.kiro/specs/openrecall/requirements.md`
- Design and decision matrix: `.kiro/specs/openrecall/design.md`,
  `.kiro/steering/structure.md`
- Idioms and anti-patterns: `.kiro/steering/tech.md`
- Property catalog: `.kiro/steering/correctness-properties.md`
  (manual: `#correctness-properties`)
- Skills: `openrecall-pbt-author`, `openrecall-spec-trace`,
  `openrecall-demo-record`, `openrecall-secret-rotate`,
  `openrecall-mode-debug`
- On-demand audit hook: `openrecall-rules-audit` (userTriggered)

## Override protocol

To override a rule for a single turn, the user writes:

> override RULE-<DOMAIN>-<NN>: <reason>

The override is scoped to that turn only. Overrides do not stack across
turns. Overrides of `RULE-SEC-*` always require an explicit reason and
are never carried over.
