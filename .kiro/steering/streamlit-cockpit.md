---
inclusion: fileMatch
fileMatchPattern: ["**/app.py"]
---

# OpenRecall — Streamlit Cockpit Steering

## Two-tab structure (mandatory)

```python
tab_single, tab_queue = st.tabs(["Single alert", "Queue"])
```

- **Tab 1 (Single alert)** — the original RCA cockpit. Hero + metric grid
  + dashboard_html + learning loop. Backward compat per R1.1, R13.1.
- **Tab 2 (Queue)** — the OpenRecall flagship. File uploader + paste-in JSON
  + "Use packaged seed alerts (100)" button + Analyze button + per-batch
  summary + Altair cost-curve chart + queue table + audit-trace expanders.

The sidebar serves both tabs (single-alert intake controls). Streamlit does
not support per-tab sidebars natively, so a shared sidebar is the chosen
pattern.

## CSS framework — preserve, never rewrite

`inject_css()` defines the entire visual system as CSS variables. **Append
new classes, never remove or rewrite the existing ones.**

The OpenRecall additions to the framework are:

```css
/* Triage decision pills */
.pill.fp     { color:#15803d; border-color:#bbf7d0; background:#dcfce7; }  /* false_positive — green */
.pill.dup    { color:#1d4ed8; border-color:#bfdbfe; background:#dbeafe; }  /* duplicate — blue */
.pill.kb     { color:#0e7490; border-color:#a5f3fc; background:#cffafe; }  /* known_benign — teal */
.pill.real   { color:#b45309; border-color:#fde68a; background:#fef3c7; }  /* real — orange */
.pill.esc    { color:#b91c1c; border-color:#fecaca; background:#fee2e2; }  /* escalated — red */
.pill.novel  { color:#6d28d9; border-color:#ddd6fe; background:#ede9fe; }  /* Novel — no prior memory */

/* Queue row decorations */
.fingerprint-mono { ... }   /* monospace badge for canonical fingerprint */
.alert-excerpt    { ... }   /* 90-char alert preview */
```

The pill-class palette is the **single source of truth** for triage
decision colors; if you add a new TriageDecision value you must add the
matching `.pill.<short-name>` class here.

## Page setup

```python
st.set_page_config(page_title="OpenRecall", layout="wide", page_icon="OR")
inject_css()
```

Hero copy is intentionally OpenRecall-branded:

- `eyebrow` → `"OpenRecall"`
- `<h1>` → `"Alert triage co-pilot"`
- `subtitle` → starts with "Queue alerts, fingerprint them as alert DNA…"

## Session-state model

| `st.session_state` key | Type | Purpose |
|---|---|---|
| `result` | `AnalysisResult` | Last single-alert result. |
| `memory_fallback` | `bool` | Mirror of `mem.fallback_mode` for badge rendering. |
| `retain_message` | `str` | One-shot success toast after retain. |
| `queue_results` | `list[AnalysisResult]` | Most recent batch in submission order. |
| `batch_id` | `int` | Monotonic counter; increments per Analyze-queue submission. |
| `override_drafts` | `dict[int, dict]` | Keyed by alert index in current queue; in-progress override form drafts. |

All four queue-related keys are initialized at the top of `app.py` so a
fresh session starts with empty containers.

## Cached resources

```python
@st.cache_data
def load_samples() -> list[dict]: ...

@st.cache_resource
def memory() -> IncidentMemory: ...

@st.cache_resource
def router() -> CascadeFlowRouter: ...

@st.cache_resource
def cost_tracker() -> CostCurveTracker: ...
```

The same `cost_tracker()` instance is passed into `IncidentWorkflow(mem, rt,
cost_tracker())` so cumulative cost-curve state survives across Streamlit
reruns. The "Reset cost curve" button calls `tracker.reset()` to clear it
mid-session without re-creating the instance.

## Queue row layout (4 columns, 3:2:2:1 ratio)

```python
cols = st.columns([3, 2, 2, 1])
# cols[0]: fingerprint badge (mono) + 90-char alert excerpt
# cols[1]: triage pill + (optional) Novel pill + escalation reason + confidence + progress bar
# cols[2]: dead_ends expander OR "no dead ends recorded" caption
# cols[3]: Override button
```

Below the 4-column row, render the audit-trace expander
(`st.expander(f"Audit trace ({len(audit_trace)} steps)")`) and any open
override form (per-row).

## Override form rules (R8, R13.2-13.3)

- Build with `st.form(f"override_form_{idx}")` so submit is atomic.
- Decision selectbox **defaults to the currently proposed decision** so the
  most-common path is one click ("accept and retain").
- On submit:
  1. Build `dead_ends_list` by splitting the textarea on newlines.
  2. Compose a traceable `content` string referencing fingerprint + raw_alert.
  3. Call `mem.retain(content, fingerprint=fp, decision=..., dead_ends=...,
     analyst_id=..., business_impact_minutes=...)`.
  4. Show `st.success(f"Retained: {status}")`.
  5. Pop `override_drafts[idx]`.
  6. Re-run `workflow.analyze(...)` for that row, replace
     `queue_results[idx]` with the fresh result.
  7. `st.rerun()` to refresh layout (so the row visually reflects the new
     persisted decision).

## Cost curve chart (Altair only)

`st.line_chart` cannot render the dual-line + shaded-band layout cleanly.
Always use Altair:

```python
chart = alt.Chart(df).transform_fold(
    ["cost_usd", "baseline_cost_usd"], as_=["series", "value"]
).mark_line().encode(
    x="alert_index:Q",
    y=alt.Y("value:Q", title="USD per alert"),
    color=alt.Color("series:N",
        scale=alt.Scale(domain=["cost_usd", "baseline_cost_usd"],
                        range=["#0369a1", "#b91c1c"])),
)
band = alt.Chart(df).mark_area(opacity=0.18, color="#15803d").encode(
    x="alert_index:Q",
    y=alt.Y("cost_usd:Q"),
    y2=alt.Y2("baseline_cost_usd:Q"),
)
st.altair_chart(band + chart, use_container_width=True)
```

Render only when `len(tracker.series()) >= 2`. With one point the chart is
visually empty.

## Novel-alert detection

`is_novel(result)` returns `True` when:

1. `result.triage_result is not None`
2. `result.triage_result.proposed_decision == "escalated"`
3. `result.triage_result.consistent_decision_count == 0`
4. `"no Strong_Match" in (result.triage_result.escalation_reason or "")`

Renders the purple `Novel — no prior memory` pill alongside the regular
triage pill, per R13.5.

## Don'ts

- ❌ Don't add new tabs. Two tabs is the design contract; more tabs
  fragment the demo flow.
- ❌ Don't use `st.line_chart` for the cost curve — the savings band
  doesn't render.
- ❌ Don't rebuild `inject_css` from scratch. Append the new class blocks at
  the end inside the existing `<style>` element.
- ❌ Don't break the legacy `result = workflow.analyze(raw_alert)` flow in
  Tab 1. The single-alert hero, metric grid, RCA panel, and learning loop
  must render exactly as before.
- ❌ Don't add a confirm dialog before retain. Retain is idempotent (P7);
  duplicates short-circuit to `"skipped duplicate"` so over-clicking is safe.
