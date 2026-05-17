---
name: openrecall-mode-debug
description: Diagnose which of the four OpenRecall mode-matrix quadrants is currently active and why. Use when the cockpit's badge row shows an unexpected mode, when bypass isn't firing, when the cost curve looks wrong, or when fallback mode is engaging unexpectedly.
---

# Diagnose OpenRecall mode-matrix issues

OpenRecall has four operating quadrants. Most "weird behavior" reports
trace back to running in the wrong quadrant. Use this skill to pinpoint
which one is active and what's gating the desired one.

## The four quadrants

| Quadrant | `HINDSIGHT_API_KEY` | `CASCADEFLOW_LIVE_GROQ` | Recall path | Fingerprint path | UI badges |
|---|---|---|---|---|---|
| **A: Cloud + Live** | set, host reachable | `true` + `GROQ_API_KEY` | Hindsight Cloud first | Live cheap-model JSON | Hindsight connected + Live model calls |
| **B: Cloud + Demo** | set, host reachable | `false` | Hindsight Cloud first | Regex fallback | Hindsight connected + Deterministic model output |
| **C: Local + Live** | unset OR unreachable | `true` + key set | local JSON | Live cheap-model JSON | Fallback memory + Live model calls |
| **D: Local + Demo** | unset OR unreachable | `false` | local JSON | Regex fallback | Fallback memory + Deterministic model output |

For the hackathon recording, you want quadrant **A**. For CI and offline
demos, quadrant **D**. Quadrants B and C are useful intermediate-debug
modes.

## Diagnostic flowchart

```
Step 1: cockpit badge row reads "Hindsight connected" or "Fallback memory"?
  Hindsight connected   → memory is in cloud quadrant (A or B)
  Fallback memory       → memory is in local quadrant (C or D)

Step 2: cockpit badge row reads "Live model calls" or "Deterministic model output"?
  Live model calls          → router is in live quadrant (A or C)
  Deterministic model output → router is in demo quadrant (B or D)

Step 3: cross-reference these two answers in the table above to identify
the quadrant.
```

## Common quadrant-switch scenarios

### Expected A, got B (Hindsight ok, but Demo)

`CASCADEFLOW_LIVE_GROQ` is `false` or `GROQ_API_KEY` is unset.

Fix:
```bash
# in incident-memory-agent/.env
CASCADEFLOW_LIVE_GROQ=true
GROQ_API_KEY=gsk_...   # ensure this is set
```
Restart Streamlit (`Ctrl+C` then `streamlit run app.py`). Streamlit's
`load_dotenv` runs at startup; in-flight env edits don't take effect.

### Expected A, got C (Live Groq ok, but Fallback memory)

`HINDSIGHT_API_KEY` is unset, OR Hindsight Cloud is unreachable, OR a
per-request failure already flipped the session to fallback.

Run this diagnostic from `incident-memory-agent/`:

```python
import os, httpx
key = os.environ.get("HINDSIGHT_API_KEY", "")
print(f"key set: {bool(key)}, prefix: {key[:8] if key else 'NONE'}")
url = os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io")
print(f"base url: {url}")
try:
    r = httpx.head(url, timeout=5, headers={"Authorization": f"Bearer {key}"}, follow_redirects=True)
    print(f"HEAD status: {r.status_code}")
except Exception as e:
    print(f"HEAD failed: {e.__class__.__name__}: {e}")
```

Interpret:

- `key set: False` → set `HINDSIGHT_API_KEY` in `.env` and restart.
- `HEAD status: 200/401/403` → host is up. If 401/403, the key is invalid;
  rotate at Vectorize.
- `HEAD status: 5xx` or `HEAD failed: ConnectError/ConnectTimeout` →
  network issue. The 2-second probe timeout in `_init_hindsight` is what
  flips fallback in this case.

### Expected A, got D (everything fallback)

Both above checks fail. Most likely explanations in order:

1. The `.env` file isn't being loaded (working directory mismatch). The
   `app.py` `load_dotenv(ROOT / ".env")` line uses `ROOT =
   Path(__file__).resolve().parent` so it loads
   `incident-memory-agent/.env`. Run streamlit FROM `incident-memory-agent/`.
2. The session was previously flipped to fallback after a per-request
   failure (`_flip_to_fallback` closes the client for the rest of the
   session). Restart Streamlit to re-init.
3. `cascadeflow` package isn't installed. Run `pip install
   cascadeflow[groq]>=0.1.0`.

## Why bypass isn't firing (most common report)

The bypass condition is:

```python
bypass = (
    triage_result.proposed_decision in {"false_positive", "duplicate", "known_benign"}
    and triage_result.triage_confidence >= BYPASS_CONFIDENCE_THRESHOLD  # 0.85
    and not fingerprint.attack_pattern
)
```

If you expected bypass and didn't get it, check in this order:

1. **Triage decision.** Open the audit-trace expander on the alert. Look
   at `proposed_decision`. If it's `escalated` or `real`, bypass won't
   fire by design — that's the spec contract.

2. **Triage confidence.** Look at the confidence value on the queue row.
   If it's below 0.85, the bypass threshold isn't crossed.

   Reference table for `confidence(c=1.0, n)`:

   | n_strong | confidence | bypass eligible? |
   |---|---|---|
   | 1 | 0.667 | no |
   | 2 | 0.750 | no |
   | 3 | 0.800 | no |
   | 4 | 0.833 | no |
   | 5 | 0.857 | yes |
   | 6 | 0.875 | yes |

   With local fallback recall capped at `limit=5`, you need 5 fully-agreeing
   strong matches (consistency=1.0) for the bypass to trigger. With cloud
   semantic recall, more matches are typically returned and the threshold
   is easier to clear.

3. **Strong matches presence.** Confidence requires Strong_Matches
   (`score >= 0.85`). In offline keyword recall, this means the alert text
   needs ≥2 keyword overlaps with the seed memory text. Long alert
   descriptions overlap better than short ones.

4. **`attack_pattern`.** If the alert text contains `sql injection`,
   `credential stuffing`, `jwt`, `waf`, `attack`, `csrf`, or `xss`, the
   regex extractor sets `attack_pattern` to a non-empty value, which
   forces the security-novel kill switch and prevents auto-bypass even
   with consistent memory. This is by design (R5.6, P12).

## Why the cost curve is flat (second most common report)

The cost curve renders only when `len(tracker.series()) >= 2`. With one
analyzed alert, no chart shows.

If you have ≥2 alerts and the curve is still flat:

- In quadrant D (Local + Demo), every alert costs $0.0 because no live
  LLM calls happen. The chart shows two horizontal lines at zero. This is
  EXPECTED for offline mode.
- In quadrant A (Cloud + Live), the chart should show meaningful cost.
  If both series sit at the same y-value (no green band), bypass isn't
  firing — go through the bypass diagnostic above.

## Why retain isn't surfacing in the next analysis

After clicking `Save & retain`, the cockpit immediately re-runs
`workflow.analyze` for that row. The new memory should appear in the
result.

If it doesn't:

1. Check the retain status returned by the form. Should say `"retained in
   Hindsight"` or `"retained in local JSON fallback"`. If it says
   `"skipped duplicate"`, the dedupe key already existed (correct
   behavior — P7 idempotence).
2. In quadrant A/B, verify the cloud retain succeeded by checking the
   Hindsight UI for the new memory in the `openrecall` bank.
3. In quadrant C/D, check `incident-memory-agent/data/local_memory.json`
   was written to.

## Mode badge cheat sheet

| Badge color | Meaning |
|---|---|
| Green `Hindsight connected` | Cloud OK, mid-A or mid-B |
| Yellow `Fallback memory` | Cloud unreachable or key unset, mid-C or mid-D |
| Plain `Live model calls` | Real Groq calls firing |
| Plain `Deterministic model output` | Demo_Mode, no live Groq |
| Plain `Standard route` | Last RouteTrace was not escalated |
| Plain `Escalated route` | Last RouteTrace was escalated |

The bottom-left of the cockpit also shows the **memory status string**
(e.g., `connected to Hindsight Cloud at https://api.hindsight.vectorize.io
/ bank openrecall`) and the **router status string** (e.g., `cascadeflow
initialized in observe mode`). These are the most authoritative source —
the badges are a UI summary.

## When all else fails

```bash
cd incident-memory-agent
python scripts/smoke_test.py
```

If smoke is green, the code is fine. The issue is environmental — most
likely an env var, network, or Streamlit caching glitch. Restart everything:
quit Streamlit, clear `__pycache__/`, re-run smoke, re-launch cockpit.

If smoke is red, you have a real regression. Run the property-test suite
(`make pbt`) to identify which invariant broke and which file owns it
(see `#correctness-properties` for the touch-points table).
