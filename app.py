from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from incident_agent.cost_curve import CostCurveTracker
from incident_agent.fingerprint import format_fingerprint
from incident_agent.memory import IncidentMemory
from incident_agent.models import Alert, AuditTraceEntry
from incident_agent.router import CascadeFlowRouter
from incident_agent.workflow import IncidentWorkflow


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


@st.cache_data
def load_samples() -> list[dict]:
    return json.loads(
        (ROOT / "data" / "sample_alerts.json").read_text(encoding="utf-8")
    )


@st.cache_resource
def memory() -> IncidentMemory:
    return IncidentMemory()


@st.cache_resource
def router() -> CascadeFlowRouter:
    return CascadeFlowRouter()


@st.cache_resource
def cost_tracker() -> CostCurveTracker:
    return CostCurveTracker()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #f8fafc;
            --panel: #ffffff;
            --panel-soft: #f1f5f9;
            --panel-tint: #eff6ff;
            --border: #dbe4ef;
            --border-strong: #cbd5e1;
            --text: #0f172a;
            --muted: #475569;
            --subtle: #64748b;
            --primary: #0f172a;
            --accent: #0369a1;
            --accent-soft: #e0f2fe;
            --ok: #15803d;
            --ok-soft: #dcfce7;
            --warn: #b45309;
            --warn-soft: #fef3c7;
            --danger: #b91c1c;
            --danger-soft: #fee2e2;
            --shadow: 0 1px 2px rgba(15, 23, 42, .06), 0 10px 28px rgba(15, 23, 42, .06);
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
            font-family: Inter, "Source Sans 3", "Segoe UI", system-ui, -apple-system, sans-serif;
        }
        header[data-testid="stHeader"] {
            background: rgba(248, 250, 252, .86);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(219, 228, 239, .75);
        }
        .block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--border);
            box-shadow: 8px 0 28px rgba(15, 23, 42, .04);
        }
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: var(--text);
            letter-spacing: 0;
        }
        [data-testid="stSidebar"] label { color: var(--muted) !important; font-weight: 650; }
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background: #ffffff !important;
            border: 1px solid var(--border-strong) !important;
            color: var(--text) !important;
            border-radius: 8px !important;
            box-shadow: none !important;
        }
        textarea,
        input,
        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea {
            background: #ffffff !important;
            color: var(--text) !important;
            border-color: var(--border-strong) !important;
            border-radius: 8px !important;
        }
        textarea:focus,
        input:focus,
        div[data-baseweb="input"] input:focus,
        div[data-baseweb="textarea"] textarea:focus {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px rgba(3, 105, 161, .12) !important;
        }

        h1, h2, h3 { letter-spacing: 0; color: var(--text); }
        h1 { font-size: 2rem !important; line-height: 1.16 !important; margin: 0 !important; font-weight: 760 !important; }
        h2 { font-size: 1.22rem !important; margin-top: .4rem !important; }
        h3 { font-size: .82rem !important; color: var(--subtle); text-transform: uppercase; letter-spacing: .08em; }
        p { color: var(--text); }

        .hero {
            padding: 22px 24px 20px;
            border: 1px solid var(--border);
            background: var(--panel);
            border-radius: 8px;
            margin-bottom: 16px;
            box-shadow: var(--shadow);
        }
        .hero-top { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; }
        .eyebrow { color: var(--accent); font-weight: 780; font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; }
        .subtitle { color: var(--muted); font-size: .98rem; max-width: 780px; margin-top: 8px; line-height: 1.45; }
        .badge-row { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; max-width: 560px; }
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            border: 1px solid var(--border);
            background: var(--panel-soft);
            color: var(--muted);
            padding: 6px 10px;
            border-radius: 999px;
            font-size: .78rem;
            font-weight: 680;
            white-space: nowrap;
        }
        .badge::before {
            content: "";
            width: 7px;
            height: 7px;
            border-radius: 999px;
            background: currentColor;
        }
        .badge.ok { color: var(--ok); border-color: #bbf7d0; background: var(--ok-soft); }
        .badge.warn { color: var(--warn); border-color: #fde68a; background: var(--warn-soft); }
        .badge.info { color: var(--accent); border-color: #bae6fd; background: var(--accent-soft); }

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 10px;
            margin-top: 22px;
        }
        .metric-card {
            background: #fbfdff;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 13px 14px;
            min-width: 0;
        }
        .metric-label { color: var(--subtle); font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; font-weight: 720; }
        .metric-value { color: var(--text); font-size: 1.02rem; font-weight: 760; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

        .dashboard-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(340px, .85fr);
            gap: 16px;
            align-items: start;
            margin-top: 16px;
        }
        .stack { display: grid; gap: 16px; align-items: start; }
        .split-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
        }
        .panel {
            border: 1px solid var(--border);
            background: var(--panel);
            border-radius: 8px;
            padding: 16px;
            box-shadow: var(--shadow);
            min-width: 0;
        }
        .panel.full { grid-column: 1 / -1; }
        .section-title { font-weight: 780; font-size: 1rem; margin-bottom: 3px; color: var(--text); }
        .section-subtitle { color: var(--subtle); font-size: .86rem; margin-bottom: 14px; line-height: 1.35; }
        .kv { display: grid; grid-template-columns: minmax(0, 1fr); gap: 4px; font-size: .92rem; }
        .kv-key { color: var(--muted); font-size: .82rem; margin-top: 6px; }
        .kv-key:first-child { margin-top: 0; }
        .kv-value { color: var(--text); font-weight: 690; overflow-wrap: anywhere; }
        .pill { display: inline-flex; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border); background: var(--panel-soft); color: var(--text); font-size: .78rem; font-weight: 700; }
        .pill.high { color: var(--danger); border-color: #fecaca; background: var(--danger-soft); }
        .pill.medium { color: var(--warn); border-color: #fde68a; background: var(--warn-soft); }
        .pill.low { color: var(--ok); border-color: #bbf7d0; background: var(--ok-soft); }
        /* OpenRecall triage decision pills */
        .pill.fp { color: #15803d; border-color: #bbf7d0; background: #dcfce7; }
        .pill.dup { color: #1d4ed8; border-color: #bfdbfe; background: #dbeafe; }
        .pill.kb { color: #0e7490; border-color: #a5f3fc; background: #cffafe; }
        .pill.real { color: #b45309; border-color: #fde68a; background: #fef3c7; }
        .pill.esc { color: #b91c1c; border-color: #fecaca; background: #fee2e2; }
        .pill.novel { color: #6d28d9; border-color: #ddd6fe; background: #ede9fe; }
        .fingerprint-mono {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
            font-size: .78rem;
            color: var(--muted);
            background: var(--panel-soft);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 4px 8px;
            display: inline-block;
            overflow-wrap: anywhere;
            margin-bottom: 6px;
        }
        .alert-excerpt { color: var(--text); font-size: .88rem; line-height: 1.4; margin-top: 4px; }

        .list { margin: 0; padding-left: 1.1rem; color: var(--text); }
        .list li { margin-bottom: 7px; }
        .muted { color: var(--muted); }
        .callout { border-left: 3px solid var(--accent); background: var(--accent-soft); padding: 11px 13px; border-radius: 8px; color: #0c4a6e; line-height: 1.42; }
        .hypothesis { margin: 0 0 10px; color: var(--text); font-weight: 720; line-height: 1.45; }
        .evidence { color: var(--muted); line-height: 1.5; margin: 0 0 14px; }
        .match { border: 1px solid var(--border); border-radius: 8px; padding: 12px; background: #fbfdff; margin-bottom: 10px; }
        .match-head { display:flex; justify-content:space-between; gap: 12px; font-weight: 700; }
        .match-head span:first-child { overflow-wrap: anywhere; }
        .match-source { color: var(--subtle); font-size:.78rem; margin-top: 4px; }
        .bar { height: 7px; background:#e2e8f0; border-radius:999px; overflow:hidden; margin-top: 10px; }
        .bar-fill { height: 100%; background: var(--accent); border-radius:999px; }
        .trace-scroll { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; background: #ffffff; box-shadow: var(--shadow); }
        .trace-table { width: 100%; border-collapse: collapse; min-width: 980px; font-size: .84rem; }
        .trace-table th {
            background: #f8fafc;
            color: var(--subtle);
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid var(--border);
            font-weight: 760;
            letter-spacing: .04em;
            text-transform: uppercase;
            font-size: .7rem;
        }
        .trace-table td {
            color: var(--text);
            padding: 11px 12px;
            border-bottom: 1px solid #edf2f7;
            vertical-align: top;
            white-space: nowrap;
        }
        .trace-table tr:last-child td { border-bottom: 0; }
        .trace-table td.reason { white-space: normal; min-width: 280px; color: var(--muted); }
        div[data-testid="stCodeBlock"] pre {
            background: #0f172a !important;
            border: 1px solid #1e293b;
            border-radius: 8px;
            font-size: .84rem !important;
            line-height: 1.55 !important;
        }
        .panel pre {
            margin: 0;
            overflow-x: auto;
            background: #0f172a;
            color: #e5e7eb;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 13px 14px;
            font-size: .86rem;
            line-height: 1.55;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .panel code { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; }
        .stButton > button {
            border-radius: 8px;
            border: 1px solid var(--border-strong);
            font-weight: 760;
            min-height: 42px;
            transition: background .18s ease, border-color .18s ease, box-shadow .18s ease;
        }
        .stButton > button p { color: inherit !important; }
        .stButton > button:hover { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(3, 105, 161, .10); }
        .stButton > button[kind="primary"] { background: var(--primary); border-color: var(--primary); color: #ffffff; }
        .stButton > button[kind="primary"]:hover { background: #1e293b; border-color: #1e293b; }
        .stDataFrame { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; box-shadow: var(--shadow); }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--border) !important;
            border-radius: 8px !important;
            background: #ffffff !important;
            box-shadow: var(--shadow);
        }
        [data-testid="stExpander"] {
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
            background: #ffffff !important;
        }
        [data-testid="stAlert"] { border-radius: 8px; }
        div[data-testid="stMarkdownContainer"] { line-height: 1.45; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid var(--border); }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            color: var(--muted);
            font-weight: 720;
            padding: 10px 14px;
        }
        .stTabs [aria-selected="true"] { color: var(--text) !important; background: #ffffff; }
        div[data-testid="column"] { min-width: 0; }

        @media (max-width: 900px) {
            .hero-top { flex-direction: column; }
            .badge-row { justify-content: flex-start; }
            .kv { grid-template-columns: 1fr; gap: 4px; }
            .dashboard-grid,
            .split-grid { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="section-title">{escape(title)}</div>'
        f'<div class="section-subtitle">{escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def header_html(title: str, subtitle: str = "") -> str:
    return (
        f'<div class="section-title">{escape(title)}</div>'
        f'<div class="section-subtitle">{escape(subtitle)}</div>'
    )


def html_list(items: list[str]) -> str:
    return (
        '<ul class="list">'
        + "".join(f"<li>{escape(item)}</li>" for item in items)
        + "</ul>"
    )


def html_memory_matches(matches) -> str:
    if not matches:
        return '<p class="muted">No similar memory found yet.</p>'
    html = ""
    for match in matches[:3]:
        width = max(4, min(100, int(match.score * 100)))
        html += f"""
        <div class="match">
          <div class="match-head"><span>{escape(match.title)}</span><span>{match.score:.2f}</span></div>
          <div class="match-source">{escape(match.source)}</div>
          <div class="bar"><div class="bar-fill" style="width:{width}%"></div></div>
        </div>
        """
    return html


def confidence_class(value: str) -> str:
    text = str(value).lower()
    if text in {"high", "critical", "sev-1", "sev-0", "p1", "p0"}:
        return "high"
    if text in {"medium", "sev-2", "sev-3", "p2", "p3"}:
        return "medium"
    return "low"


def money(value: float) -> str:
    return f"${value:.6f}"


def trace_rows(result) -> list[dict[str, str | bool | float]]:
    rows = []
    for trace in result.route_trace:
        rows.append(
            {
                "Step": trace.step,
                "Model": trace.model,
                "Route": "Escalated" if trace.escalated else "Standard",
                "Confidence": trace.confidence,
                "Latency": f"{trace.latency_ms:.1f} ms",
                "Cost": money(trace.estimated_cost_usd),
                "Saved vs strong": money(trace.savings_vs_strong_usd),
                "Budget left": money(trace.budget_remaining_usd or 0.0),
                "Live call": trace.live_model_call,
                "Issue": trace.model_error or "",
                "Reason": trace.route_reason,
            }
        )
    return rows


def trace_table(rows: list[dict[str, str | bool | float]]) -> str:
    headers = [
        "Step",
        "Model",
        "Route",
        "Confidence",
        "Latency",
        "Cost",
        "Saved vs strong",
        "Budget left",
        "Live call",
        "Issue",
        "Reason",
    ]
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = ""
    for row in rows:
        cells = ""
        for header in headers:
            value = str(row.get(header, ""))
            cls = "reason" if header == "Reason" else ""
            cells += f'<td class="{cls}">{escape(value)}</td>'
        body += f"<tr>{cells}</tr>"
    return f'<div class="trace-scroll"><table class="trace-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


# OpenRecall queue helpers ---------------------------------------------------

TRIAGE_PILL_CLASS = {
    "false_positive": "fp",
    "duplicate": "dup",
    "known_benign": "kb",
    "real": "real",
    "escalated": "esc",
}

TRIAGE_DECISION_OPTIONS = [
    "false_positive",
    "duplicate",
    "known_benign",
    "real",
    "escalated",
]


def triage_pill_html(decision: str) -> str:
    cls = TRIAGE_PILL_CLASS.get(decision, "")
    return f'<span class="pill {cls}">{escape(decision)}</span>'


def is_novel(result) -> bool:
    """Return True when there is no Strong_Match and the engine escalated for that reason."""
    triage = result.triage_result
    if triage is None:
        return False
    if triage.proposed_decision != "escalated":
        return False
    if triage.consistent_decision_count != 0:
        return False
    return "no Strong_Match" in (triage.escalation_reason or "")


def _render_audit_entry(entry: AuditTraceEntry) -> str:
    return (
        f"Step: {entry.step}\n"
        f"Model: {entry.model} | live: {entry.live_model_call} | skipped: {entry.llm_skipped}\n"
        f"Route reason: {entry.route_reason}\n"
        f"Decision: {entry.proposed_decision} | escalation reason: {entry.escalation_reason}\n"
        f"Cost: {money(entry.cost_usd)} | baseline: {money(entry.baseline_cost_usd)} "
        f"| savings: {money(entry.savings_usd)}\n"
        f"Memory hits: {entry.memory_hit_count}"
    )


def render_override_form(idx: int, result) -> None:
    """Render the analyst Override_Flow form for queue row ``idx``."""
    triage = result.triage_result
    proposed = triage.proposed_decision if triage else "escalated"
    try:
        default_index = TRIAGE_DECISION_OPTIONS.index(proposed)
    except ValueError:
        default_index = TRIAGE_DECISION_OPTIONS.index("escalated")

    with st.form(f"override_form_{idx}"):
        st.markdown("**Override decision**")
        decision = st.selectbox(
            "Decision",
            options=TRIAGE_DECISION_OPTIONS,
            index=default_index,
        )
        dead_ends_text = st.text_area("Dead ends (one per line)", value="")
        analyst_id = st.text_input("Analyst id", value="")
        business_impact_minutes = st.number_input(
            "Business impact (minutes)",
            min_value=0,
            value=0,
            step=1,
        )
        cols = st.columns([1, 1])
        with cols[0]:
            submitted = st.form_submit_button("Save & retain", type="primary")
        with cols[1]:
            cancel = st.form_submit_button("Cancel")

    if cancel:
        st.session_state.override_drafts.pop(idx, None)
        st.rerun()
        return

    if not submitted:
        return

    dead_ends_list = [
        line.strip() for line in dead_ends_text.split("\n") if line.strip()
    ]
    fp = result.alert_fingerprint
    fp_canonical = format_fingerprint(fp) if fp is not None else "unknown fingerprint"
    content = (
        f"Triage decision for {result.incident.service}: {decision}.\n"
        f"Alert fingerprint: {fp_canonical}\n"
        f"Raw alert: {result.incident.raw_alert}\n"
        f"Dead ends:\n" + "\n".join(f"- {d}" for d in dead_ends_list)
    )
    status = mem.retain(
        content,
        fingerprint=fp,
        decision=decision,
        dead_ends=dead_ends_list,
        analyst_id=analyst_id or None,
        business_impact_minutes=(
            int(business_impact_minutes) if business_impact_minutes > 0 else None
        ),
    )
    st.success(f"Retained: {status}")
    st.session_state.override_drafts.pop(idx, None)
    # Re-run the workflow for this row so the persisted decision becomes visible.
    st.session_state.queue_results[idx] = workflow.analyze(result.incident.raw_alert)
    st.rerun()


def render_queue_row(idx: int, result) -> None:
    """Render one queue table row inside a bordered container."""
    with st.container(border=True):
        cols = st.columns([3, 2, 2, 1])

        with cols[0]:
            fp = result.alert_fingerprint
            fp_text = format_fingerprint(fp) if fp is not None else "fingerprint unavailable"
            raw_excerpt = (result.incident.raw_alert or "")[:90]
            if result.incident.raw_alert and len(result.incident.raw_alert) > 90:
                raw_excerpt += "…"
            st.markdown(
                f'<div class="fingerprint-mono">{escape(fp_text)}</div>'
                f'<div class="alert-excerpt">{escape(raw_excerpt)}</div>',
                unsafe_allow_html=True,
            )

        with cols[1]:
            triage = result.triage_result
            if triage is not None:
                pill = triage_pill_html(triage.proposed_decision)
                novel_pill = (
                    '<span class="pill novel">Novel — no prior memory</span>'
                    if is_novel(result)
                    else ""
                )
                reason_text = triage.escalation_reason or ""
                reason_html = (
                    f'<div class="muted" style="font-size:.74rem;margin-top:6px;'
                    f"line-height:1.35;\">reason: {escape(reason_text)}</div>"
                    if reason_text
                    else ""
                )
                st.markdown(
                    f'<div>{pill} {novel_pill}</div>'
                    f'<div class="muted" style="font-size:.78rem;margin-top:6px;">'
                    f"confidence {triage.triage_confidence:.3f}</div>"
                    f"{reason_html}",
                    unsafe_allow_html=True,
                )
                st.progress(min(max(triage.triage_confidence, 0.0), 1.0))
            else:
                st.caption("no triage result")

        with cols[2]:
            if result.dead_ends:
                with st.expander(f"Skip these paths ({len(result.dead_ends)})"):
                    for d in result.dead_ends:
                        st.markdown(f"- {d}")
            else:
                st.caption("no dead ends recorded")

        with cols[3]:
            if st.button("Override", key=f"override_btn_{idx}"):
                st.session_state.override_drafts[idx] = {
                    "decision": (
                        result.triage_result.proposed_decision
                        if result.triage_result
                        else "escalated"
                    )
                }
                st.rerun()

        if idx in st.session_state.override_drafts:
            render_override_form(idx, result)

        with st.expander(f"Audit trace ({len(result.audit_trace)} steps)"):
            if not result.audit_trace:
                st.caption("no audit entries")
            for entry in result.audit_trace:
                st.code(_render_audit_entry(entry), language="text")


def queue_summary_html(results: list, tracker: CostCurveTracker) -> str:
    auto = sum(
        1
        for r in results
        if r.triage_result
        and r.triage_result.proposed_decision
        in {"false_positive", "duplicate", "known_benign"}
        and r.triage_result.requires_human_approval
    )
    escalated = sum(
        1
        for r in results
        if r.triage_result and r.triage_result.proposed_decision == "escalated"
    )
    total_cost, total_baseline, pct_saved = tracker.savings()
    savings_value = max(0.0, total_baseline - total_cost)
    return f"""
    <div class="metric-grid">
      <div class="metric-card"><div class="metric-label">Alerts</div><div class="metric-value">{len(results)}</div></div>
      <div class="metric-card"><div class="metric-label">Auto-decided by memory</div><div class="metric-value">{auto}</div></div>
      <div class="metric-card"><div class="metric-label">Escalated to strong model</div><div class="metric-value">{escalated}</div></div>
      <div class="metric-card"><div class="metric-label">Total cost</div><div class="metric-value">{escape(money(total_cost))}</div></div>
      <div class="metric-card"><div class="metric-label">Total baseline</div><div class="metric-value">{escape(money(total_baseline))}</div></div>
      <div class="metric-card"><div class="metric-label">Total savings</div><div class="metric-value">{escape(money(savings_value))}</div></div>
      <div class="metric-card"><div class="metric-label">Percent saved</div><div class="metric-value">{pct_saved:.1f}%</div></div>
    </div>
    """


def render_cost_curve_chart(tracker: CostCurveTracker) -> None:
    points = tracker.series()
    if len(points) < 2:
        return
    df = pd.DataFrame([p.model_dump() for p in points])
    chart = (
        alt.Chart(df)
        .transform_fold(
            ["cost_usd", "baseline_cost_usd"], as_=["series", "value"]
        )
        .mark_line()
        .encode(
            x=alt.X("alert_index:Q", title="Alert index"),
            y=alt.Y("value:Q", title="USD per alert"),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(
                    domain=["cost_usd", "baseline_cost_usd"],
                    range=["#0369a1", "#b91c1c"],
                ),
            ),
        )
    )
    band = (
        alt.Chart(df)
        .mark_area(opacity=0.18, color="#15803d")
        .encode(
            x=alt.X("alert_index:Q"),
            y=alt.Y("cost_usd:Q"),
            y2=alt.Y2("baseline_cost_usd:Q"),
        )
    )
    st.altair_chart(band + chart, use_container_width=True)


def collect_all_dead_ends(results: list) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for r in results:
        for d in r.dead_ends:
            text = str(d).strip()
            if text and text not in seen:
                seen.add(text)
                deduped.append(text)
    return deduped


def parse_alerts_payload(payload: list) -> list[Alert]:
    if not isinstance(payload, list):
        raise ValueError("expected a JSON array of alerts")
    alerts: list[Alert] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("each alert must be a JSON object")
        raw = str(entry.get("raw_alert") or "")
        title = entry.get("title")
        alerts.append(Alert(raw_alert=raw, title=str(title) if title else None))
    return alerts


# Streamlit page setup -------------------------------------------------------

st.set_page_config(page_title="OpenRecall", layout="wide", page_icon="OR")
inject_css()

mem = memory()
rt = router()
tracker = cost_tracker()
workflow = IncidentWorkflow(mem, rt, tracker)
samples = load_samples()

# Session-state init for queue tab
if "queue_results" not in st.session_state:
    st.session_state.queue_results = []
if "override_drafts" not in st.session_state:
    st.session_state.override_drafts = {}
if "batch_id" not in st.session_state:
    st.session_state.batch_id = 0

with st.sidebar:
    st.markdown("## Single-alert intake")
    sample_title = st.selectbox("Sample alert", [s["title"] for s in samples])
    selected = next(s for s in samples if s["title"] == sample_title)
    raw_alert = str(st.text_area("Raw signal", value=selected["raw_alert"], height=260))
    analyze = st.button("Analyze incident", type="primary", width="stretch")
    if st.button("Seed 5 memories into Hindsight", width="stretch"):
        os.environ["HINDSIGHT_SEED_LIMIT"] = "5"
        os.environ.setdefault("HINDSIGHT_SEED_DELAY_SECONDS", "65")
        st.success(mem.seed())

    st.markdown("---")
    st.markdown("### Runtime")
    st.caption(mem.status)
    st.caption(rt.status)
    st.caption(
        "live Groq calls enabled"
        if rt.live_groq and rt.api_key
        else "deterministic model output; routing/cost trace still shown"
    )

memory_state_changed = st.session_state.get("memory_fallback") != mem.fallback_mode
if analyze or "result" not in st.session_state or memory_state_changed:
    st.session_state.result = workflow.analyze(raw_alert)
    st.session_state.memory_fallback = mem.fallback_mode

result = st.session_state.result
top_trace = result.route_trace[-1]
total_cost = sum(trace.estimated_cost_usd for trace in result.route_trace)
baseline_cost = sum(trace.strong_model_baseline_cost_usd for trace in result.route_trace)
savings = max(0.0, baseline_cost - total_cost)
savings_pct = round((savings / baseline_cost) * 100, 1) if baseline_cost else 0.0
memory_badge = "warn" if result.fallback_mode else "ok"
memory_label = "Fallback memory" if result.fallback_mode else "Hindsight connected"
escalation_label = "Escalated route" if top_trace.escalated else "Standard route"
live_label = (
    "Live model calls"
    if any(t.live_model_call for t in result.route_trace)
    else "Deterministic model output"
)

if "retain_message" in st.session_state:
    st.success(st.session_state.pop("retain_message"))

tab_single, tab_queue = st.tabs(["Single alert", "Queue"])

with tab_single:
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-top">
            <div>
              <div class="eyebrow">OpenRecall</div>
              <h1>Alert triage co-pilot</h1>
              <div class="subtitle">Queue alerts, fingerprint them as alert DNA, recall prior triage decisions, and bypass the strong model when memory is consistent. Cost-aware. Counterfactual. Auditable.</div>
            </div>
            <div class="badge-row">
              <span class="badge {memory_badge}">{escape(memory_label)}</span>
              <span class="badge info">{escape(escalation_label)}</span>
              <span class="badge">{escape(live_label)}</span>
              <span class="badge">{escape(top_trace.model)}</span>
            </div>
          </div>
          <div class="metric-grid">
            <div class="metric-card"><div class="metric-label">Service</div><div class="metric-value">{escape(result.incident.service)}</div></div>
            <div class="metric-card"><div class="metric-label">Environment</div><div class="metric-value">{escape(result.incident.environment)}</div></div>
            <div class="metric-card"><div class="metric-label">Severity</div><div class="metric-value">{escape(result.incident.severity)}</div></div>
            <div class="metric-card"><div class="metric-label">Classification</div><div class="metric-value">{escape(result.incident_type)}</div></div>
            <div class="metric-card"><div class="metric-label">Memory hits</div><div class="metric-value">{len(result.memory_matches)}</div></div>
            <div class="metric-card"><div class="metric-label">Run cost</div><div class="metric-value">{escape(money(total_cost))}</div></div>
            <div class="metric-card"><div class="metric-label">Saved vs strong-only</div><div class="metric-value">{escape(money(savings))} / {savings_pct}%</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    role_items = [
        f"{role.replace('_', ' ').title()}: {duty}" for role, duty in result.roles.items()
    ]
    cause_blocks = ""
    for cause in result.likely_root_causes:
        confidence = escape(str(cause.get("confidence", "n/a")))
        cause_blocks += (
            f'<p class="hypothesis">{escape(str(cause.get("cause", "unknown")))} '
            f'<span class="pill medium">confidence {confidence}</span></p>'
            f'<p class="evidence">{escape(str(cause.get("evidence", "Evidence pending")))}</p>'
        )

    dashboard_html = f"""
    <div class="dashboard-grid">
      <div class="stack">
        <div class="panel">
          {header_html("RCA and runbook", "Evidence-backed hypothesis with verification first")}
          {cause_blocks}
          <pre><code>{escape(chr(10).join(result.verification_commands))}</code></pre>
        </div>
        <div class="split-grid">
          <div class="panel">
            {header_html("Evidence to preserve", "Collect context before changing state")}
            {html_list(result.evidence_to_preserve)}
          </div>
          <div class="panel">
            {header_html("Containment notes", "Lowest-impact reversible actions")}
            {html_list(result.containment_notes)}
          </div>
          <div class="panel">
            {header_html("Remediation plan", "Suggested next actions after confirmation")}
            {html_list(result.remediation_suggestions)}
          </div>
          <div class="panel">
            {header_html("Postmortem actions", "Follow-up items to prevent recurrence")}
            {html_list(result.postmortem_action_items)}
          </div>
        </div>
        <div class="panel">
          {header_html("Audit trace", "Routing, cost, latency, and model decisions")}
          {trace_table(trace_rows(result))}
        </div>
      </div>
      <div class="stack">
        <div class="panel">
          {header_html("Incident brief", "Normalized signal and operational impact")}
          <div class="kv">
            <div class="kv-key">Error type</div><div class="kv-value">{escape(result.incident.error_type)}</div>
            <div class="kv-key">Dependency</div><div class="kv-value">{escape(result.incident.affected_dependency or "not detected")}</div>
            <div class="kv-key">Recent change</div><div class="kv-value">{escape(result.incident.suspected_recent_change or "not detected")}</div>
            <div class="kv-key">Security</div><div class="kv-value"><span class="pill {confidence_class(result.incident.security_relevance)}">{escape(result.incident.security_relevance)}</span></div>
          </div>
          <br>
          <div class="callout">{escape(result.impact_level)}</div>
          <p class="muted"><b>Blast radius:</b> {escape(result.blast_radius_guess)}</p>
        </div>
        <div class="panel">
          {header_html("Memory recall", "Closest Hindsight incidents and reusable lessons")}
          {html_memory_matches(result.memory_matches)}
          <div class="callout">{escape(result.memory_reflection)}</div>
        </div>
        <div class="panel">
          {header_html("Operating model", "Roles and decision checkpoints")}
          <b>Response roles</b>
          {html_list(role_items)}
          <b>Timeline</b>
          {html_list(result.timeline_notes)}
        </div>
      </div>
    </div>
    """
    st.markdown(dashboard_html, unsafe_allow_html=True)

    with st.container(border=True):
        section_header("Learning loop", "Retain the final incident memory")
        if not result.memory_matches:
            st.info(
                "No close memory matched this alert. Retain the final RCA, then analyze the same alert again to show the before/after memory delta."
            )
        root_cause = st.text_input(
            "Final root cause",
            value=result.likely_root_causes[0].get("cause", "")
            if result.likely_root_causes
            else "",
        )
        lessons = st.text_area(
            "Lessons learned",
            value="Add alert annotation, update runbook, and retain exact verification commands.",
            height=90,
        )
        if st.button("Mark resolved and retain memory", type="primary", width="stretch"):
            content = (
                f"Resolved incident for {result.incident.service}. Final root cause: {root_cause}.\n"
                f"Incident object: {result.incident.model_dump_json()}\n"
                f"Verification commands: {'; '.join(result.verification_commands)}\n"
                f"Remediation: {'; '.join(result.remediation_suggestions)}\n"
                f"Lessons learned: {lessons}"
            )
            st.success(
                (
                    msg := mem.retain(
                        content,
                        context=f"resolved incident: {result.incident.service} {result.incident.error_type}",
                    )
                )
            )
            st.session_state.result = workflow.analyze(raw_alert)
            st.session_state.memory_fallback = mem.fallback_mode
            st.session_state.retain_message = (
                f"{msg}; analysis reran so the new memory is now visible"
            )
            st.rerun()


with tab_queue:
    header_cols = st.columns([5, 1])
    with header_cols[0]:
        section_header(
            "Batch triage",
            "Upload a queue of alerts, watch fingerprint-keyed memory pre-judge the repeats, and see the cost curve drop in real time.",
        )
    with header_cols[1]:
        if st.button("Reset cost curve", key="reset_cost_curve"):
            tracker.reset()
            st.session_state.queue_results = []
            st.session_state.override_drafts = {}
            st.session_state.batch_id = 0
            st.rerun()

    intake_cols = st.columns([1, 1])
    with intake_cols[0]:
        uploaded = st.file_uploader("Upload alerts JSON", type=["json"])
        use_seed = st.button(
            "Use packaged seed alerts (100)",
            help="Loads data/seed_alerts.json directly for the demo.",
        )
    with intake_cols[1]:
        pasted = st.text_area("Or paste alerts JSON", height=160)

    analyze_queue_clicked = st.button("Analyze queue", type="primary")

    # Source resolution: the seed button is a one-click demo shortcut that
    # both loads and analyzes; the "Analyze queue" button picks the most
    # specific source available — uploaded file > pasted JSON > seed alerts.
    payload: list | None = None
    source_label = ""

    if use_seed or analyze_queue_clicked:
        try:
            if analyze_queue_clicked and uploaded is not None:
                payload = json.loads(uploaded.getvalue().decode("utf-8"))
                source_label = "uploaded file"
            elif analyze_queue_clicked and pasted.strip():
                payload = json.loads(pasted)
                source_label = "pasted JSON"
            else:
                # Seed button OR analyze-queue with no other input → load seed file.
                payload = json.loads(
                    (ROOT / "data" / "seed_alerts.json").read_text(encoding="utf-8")
                )
                source_label = "packaged seed alerts"
        except json.JSONDecodeError as exc:
            st.error(f"Could not parse JSON: {exc}")
            payload = None

        if payload is not None:
            try:
                alerts = parse_alerts_payload(payload)
            except ValueError as exc:
                st.error(f"Invalid alerts payload: {exc}")
                alerts = []

            if alerts:
                limit = max(1, int(os.getenv("OPENRECALL_BATCH_SIZE_LIMIT", "200")))
                if len(alerts) > limit:
                    st.warning(
                        f"Batch trimmed from {len(alerts)} to {limit} (OPENRECALL_BATCH_SIZE_LIMIT)"
                    )
                with st.spinner(
                    f"Analyzing {min(len(alerts), limit)} alerts from {source_label}…"
                ):
                    st.session_state.queue_results = workflow.analyze_queue(alerts)
                st.session_state.batch_id += 1
                st.session_state.override_drafts = {}

    queue_results = st.session_state.queue_results

    if queue_results:
        st.markdown(
            queue_summary_html(queue_results, tracker), unsafe_allow_html=True
        )

        st.markdown("#### Cost curve")
        if len(tracker.series()) >= 2:
            render_cost_curve_chart(tracker)
        else:
            st.caption("Cost curve appears once at least two alerts have been recorded.")

        all_dead_ends = collect_all_dead_ends(queue_results)
        if all_dead_ends:
            with st.expander("Skip these paths across this batch"):
                for d in all_dead_ends:
                    st.markdown(f"- {d}")

        st.markdown("#### Queue")
        for idx, queue_result in enumerate(queue_results):
            render_queue_row(idx, queue_result)
    else:
        st.info(
            "No queue results yet. Upload alerts JSON, paste a JSON array, or click 'Use packaged seed alerts (100)', then 'Analyze queue'."
        )
