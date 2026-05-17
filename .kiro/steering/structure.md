---
inclusion: always
---

# OpenRecall — Project Structure Steering

## Repository layout

The project lives inside `incident-memory-agent/` (the original folder name
that the GitHub repo uses). The Python package directory `incident_agent/`
is intentionally **not renamed** so existing imports keep working. Only the
`pyproject.toml` `name` field moved to `openrecall`.

```text
incident-memory-agent/
├── app.py                          # Streamlit cockpit, two tabs (Single + Queue)
├── seed_memory.py                  # CLI: seed Hindsight Cloud
├── incident_agent/
│   ├── __init__.py                 # Public API re-exports
│   ├── models.py                   # All Pydantic models, shared types
│   ├── fingerprint.py              # AlertFingerprint generator + canonical (de)serializer
│   ├── triage.py                   # TriageEngine + STRONG_MATCH/CONSISTENCY/BYPASS thresholds
│   ├── memory.py                   # IncidentMemory: Hindsight Cloud + local JSON fallback
│   ├── router.py                   # CascadeFlowRouter: Groq + budget tracking + bypass trace
│   ├── cost_curve.py               # CostCurveTracker: in-memory series
│   ├── audit.py                    # AuditTraceRecorder: one entry per RouteTrace
│   └── workflow.py                 # IncidentWorkflow.analyze + analyze_queue
├── data/
│   ├── sample_alerts.json          # 6 demo alerts (single-alert tab)
│   ├── seed_alerts.json            # 100 synthetic alerts (queue demo)
│   ├── seed_incidents.json         # 18 synthetic incident memories
│   └── local_memory.json           # gitignored, retain learning-loop output
├── scripts/
│   ├── smoke_test.py               # 4 sub-checks (single + queue + schema + env)
│   └── generate_seed_alerts.py     # deterministic 100-alert generator
├── tests/
│   ├── __init__.py
│   ├── test_signatures.py          # 4 backward-compat signature checks
│   └── property/
│       ├── conftest.py             # Hypothesis strategies + frozen_router/memory fixtures
│       ├── test_fingerprint.py     # P1, P2
│       ├── test_triage.py          # P3, P4, P5, P6, P11, P12
│       ├── test_memory.py          # P7, P10, P13
│       ├── test_cost_curve.py      # P8, P9, P14
│       └── test_workflow.py        # P15 + queue ordering + Demo_Mode end-to-end
├── docs/
│   ├── ARCHITECTURE.md             # Mermaid diagrams, mode matrix
│   ├── DEMO.md                     # 60-second hackathon demo script
│   └── HACKATHON_SUBMISSION.md     # Rubric mapping
├── content/
│   ├── article_draft.md            # Long-form article
│   ├── social_post.md              # X/LinkedIn post
│   └── demo_video_script.md        # 2-minute video narration
├── .github/workflows/ci.yml        # compileall + pbt + signature + smoke
├── Makefile                        # install / run / seed / compile / pbt / smoke
├── pyproject.toml                  # name=openrecall, version=0.2.0
├── requirements.txt
├── .env.example                    # placeholder-only env vars
├── .env                            # GITIGNORED, holds live keys for demo
├── .gitignore                      # excludes .env, data/local_memory.json, .hypothesis/
└── README.md, SECURITY.md, HANDOVER.md, CONTRIBUTING.md, LICENSE
```

## Spec directory (workspace-level, outside the project)

```text
.kiro/
├── specs/openrecall/
│   ├── requirements.md             # 15 requirements, 15 correctness properties
│   ├── design.md                   # HLD + LLD with 5 Mermaid diagrams
│   ├── tasks.md                    # 17 top-level tasks, ~95 sub-tasks
│   └── .config.kiro                # specType=feature, workflowType=requirements-first
├── steering/                       # this directory
├── hooks/                          # automation triggers
└── skills/                         # on-demand workflows
```

## Naming conventions

- **Python files**: `snake_case.py`. Module names match the
  responsibility-noun (e.g., `fingerprint.py`, not `fingerprinting.py`).
- **Pydantic classes**: `PascalCase` (e.g., `AlertFingerprint`,
  `TriageResult`).
- **Threshold constants**: `SHOUTING_SNAKE_CASE` with `Final[float]`
  annotation.
- **Test functions**: `test_<property_or_behavior>` (e.g.,
  `test_fingerprint_round_trip`, `test_strong_model_bypass_invariant`).
- **Test docstrings**: must carry the tag
  `Feature: openrecall, Property N: <text>` for traceability.
- **Hypothesis strategies**: `<noun>_strategy` (lowercase, e.g.,
  `alert_fingerprint_strategy`, `memory_match_strategy`,
  `strong_match_set_strategy`, `raw_alert_strategy`).

## Import order

```python
from __future__ import annotations

# stdlib
import json, os, re, time
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, Final, Literal

# third-party
import altair as alt
import httpx
import pandas as pd
import streamlit as st
from hypothesis import given, settings, strategies as st_strat  # rename in tests
from pydantic import BaseModel, ConfigDict, Field

# first-party — relative imports inside the package
from .models import AlertFingerprint, MemoryMatch, RouteTrace, ...
from .router import CascadeFlowRouter, estimate_cost
```

## Where things live (decision matrix)

| If you're touching... | Edit here | Also update |
|---|---|---|
| Threshold value (0.85, 0.9, 0.85) | `incident_agent/triage.py` constants | `tests/property/test_triage.py` if values shift |
| AlertFingerprint field | `models.py` AND `fingerprint.py` (regex extractor + serializer) | `tests/property/test_fingerprint.py` round-trip |
| New TriageDecision value | `models.py` Literal AND `triage.py` (decision flow) AND `app.py` (badge palette) | All triage PBTs |
| New env var | `.env.example` AND `README.md` Configuration table AND `tech.md` AND `smoke_env_example()` in `smoke_test.py` | `design.md` Configuration table |
| New RouteTrace field | `models.py` (with safe default) AND `audit.py` (carry into AuditTraceEntry) AND `router.py` populate site | P15 test |
| Memory retain shape | `memory.py` (retain + dedupe key) AND test fixture `_DictBackedMemory.retain` | P7, P13 |
| Cost-curve invariant | `cost_curve.py` AND `workflow.py` (where `record()` is called) | P8, P9, P14 |
| Streamlit UI | `app.py` only — preserve `inject_css()` framework, never replace it | None |
| Spec contract | `.kiro/specs/openrecall/{requirements,design,tasks}.md` | All cross-references |
