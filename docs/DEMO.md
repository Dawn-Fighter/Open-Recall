# Demo Runbook

A 60-second demo script that hits every rubric criterion. Use the live
Hindsight Cloud + Live Groq mode for the strongest recording.

## 0. Pre-flight (10 seconds before recording)

```bash
export HINDSIGHT_API_KEY=hsk_your_key_here
export GROQ_API_KEY=gsk_your_key_here
export CASCADEFLOW_LIVE_GROQ=true
streamlit run app.py
```

Confirm the badges read **Hindsight connected** and **Live model calls** in the
single-alert tab. If they read fallback or deterministic, the workflow still
demos but the live integration is not proven.

## 1. Open the Queue tab (0:00 - 0:10)

Click the `Queue` tab. Click **`Use packaged seed alerts (100)`**, then
**`Analyze queue`**.

Cue: *"This is 100 real-shaped alerts mixed across 8 repeating fingerprint
families plus 30 false positives, 15 novel reals, and 5 ambiguous."*

## 2. The cost curve (0:10 - 0:30)

Point to the **Cost curve** chart that appears above the queue table:
- Red line: strong-model-only baseline cost per alert.
- Blue line: actual cost paid by OpenRecall.
- Green band: savings from memory.

Cue: *"This is cascadeflow earning its keep. Every memory hit collapses one
red point onto the blue line. The wider the green band, the more we saved."*

Point to the per-batch summary metrics: **Auto-decided by memory** and
**Total savings**. Read out the percentages.

## 3. Override an escalated alert (0:30 - 0:45)

Pick any row whose triage badge reads `escalated`. Click **`Override`**.
- Decision: `false_positive`
- Dead ends: `restarted DB pods, made it worse`
- Click **`Save & retain`**

Watch the row update. Cue: *"This decision and the dead end are now in
Hindsight Cloud. The next analyst won't waste time restarting DB pods."*

## 4. Re-run the queue (0:45 - 0:55)

Click **`Analyze queue`** again. Watch:
- The same fingerprint family that was escalated last time now reads
  `false_positive` with high confidence.
- The cost curve flattens near zero for those rows.
- The audit trace expander shows `model: memory-bypass` and `llm_skipped: True`.

Cue: *"The strong model didn't run for those alerts. Hindsight + cascadeflow
caught it before the LLM call. Property test P6 enforces this invariant
across every release."*

## 5. Single alert security demo (0:55 - 1:00)

Switch to the **Single alert** tab. Pick `Security: WAF SQL injection`.
Show the **Hindsight connected**, **Live model calls** badges, and the
audit trace.

Cue: *"`attack_pattern` is non-empty, so the security-novel kill switch
fires regardless of memory state. Even if we had 50 consistent strong
matches, the analyst gets human-approval prompted before the decision is
applied."*

## What to point to

Throughout the demo, call out:
- **Hindsight connected** badge — proves live cloud integration.
- **Cost curve drop** — proves cascadeflow value.
- **Memory-bypass RouteTrace** in the audit expander — proves zero LLM
  cost on memory-consistent repeats.
- **Skip these paths** panel — proves counterfactual memory works
  end-to-end.

## Offline fallback

If the demo machine has no network, omit the live env vars. The cockpit
falls back to local JSON memory and deterministic regex fingerprints. The
cost curve, queue table, override flow, and audit trace all still work —
only the `Live model calls` badge flips to `Deterministic model output`.
