---
name: openrecall-demo-record
description: Run, verify, and record the 60-second OpenRecall hackathon demo. Use when preparing for a live demo, recording the submission video, troubleshooting why the cost curve doesn't drop, or verifying the bypass step fires before judging.
---

# Record the OpenRecall hackathon demo

The OpenRecall demo has five mandatory beats. Each one maps to a specific
visible artifact that matches the rubric criteria.

## Pre-flight checklist (do these BEFORE hitting record)

```bash
cd incident-memory-agent
```

1. **Confirm the env file is wired for the live demo.**

   ```dotenv
   HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
   HINDSIGHT_API_KEY=hsk_...                  # live key
   HINDSIGHT_BANK_ID=openrecall
   GROQ_API_KEY=gsk_...                       # live key
   CASCADEFLOW_LIVE_GROQ=true
   CASCADEFLOW_RUN_BUDGET_USD=0.02
   CASCADEFLOW_CHEAP_MODEL=qwen/qwen3-32b
   CASCADEFLOW_STRONG_MODEL=openai/gpt-oss-120b
   ```

2. **Run the smoke test.** Must show 4 green lines:
   ```
   smoke ok: samples=6 fallback=False traces=18
   smoke queue ok: alerts=100 ... bypass_steps=1 ...
   smoke env.example ok: all keys present, no live secrets detected
   smoke seed_incidents schema ok: 18 records
   ```
   If `fallback=True` appears, the live env vars are not in effect — fix
   before recording.

3. **Reset local state.**
   ```bash
   echo [] > data\local_memory.json    # Windows
   ```
   This wipes any leftover retained memory from previous demo runs so the
   "before/after" cost curve is clean.

4. **Start the cockpit.**
   ```bash
   streamlit run app.py
   ```

5. **Verify the badges in the browser.** Top-right should show:
   - ✅ `Hindsight connected` (green)
   - ✅ `Live model calls` or `Deterministic model output` (whichever the
     env vars say)
   - Standard route OR Escalated route (depends on the sample alert loaded
     in the sidebar — fine either way)

## The 60-second beat sheet

### 0:00 — 0:10 — Hero shot

Open the cockpit. Camera frames the badge row + hero copy. Cue: *"OpenRecall
is an alert triage co-pilot. Memory first, LLM only when memory says so."*

Point to the `Hindsight connected` badge to prove live integration.

### 0:10 — 0:35 — Queue tab + cost curve

Click `Queue` tab. Click `Use packaged seed alerts (100)`. Click `Analyze
queue`.

When the table populates:

- Point to the **per-batch summary** metric grid (`Auto-decided by memory`,
  `Total savings`, `Percent saved`).
- Point to the **Altair cost-curve chart** — red baseline line + blue
  OpenRecall line + shaded green savings band. Cue: *"Red is what we'd
  have paid running everything on the strong model. Blue is what we
  actually paid. Green is cascadeflow earning its keep."*
- Optional: read out one of the auto-decided rows by triage pill color
  (green = false_positive auto-decided).

### 0:35 — 0:55 — Override + retain

Pick any row whose triage pill is `escalated` (red) or `real` (orange).
Click `Override`. In the form:

- Decision: `false_positive`
- Dead ends: `restarted DB pods, made it worse`
- Click `Save & retain`

Watch the row update. Cue: *"That decision and the dead end are now in
Hindsight Cloud. The next analyst won't waste time restarting DB pods."*

### 0:55 — 1:25 — Re-analyze + bypass

Click `Analyze queue` again. The same fingerprint family now reads
`false_positive` with high confidence. Open one such row's audit-trace
expander. Show:

```
Step: auto-triage bypass
Model: memory-bypass | live: False | skipped: True
Cost: $0.000000 | baseline: $0.000xxx | savings: $0.000xxx
```

Cue: *"Strong model never ran for those alerts. Property test P6 enforces
this invariant across every release."*

### 1:25 — 1:50 — Security-novel kill switch

Switch to the **Single alert** tab. From the sidebar dropdown, pick
`Security: WAF SQL injection`. Click `Analyze incident`.

Show the audit trace. Even with high memory consistency, the row shows:

- Triage pill: `escalated` or `real`
- Escalation reason: `security-novel: human approval required`
- `requires_human_approval: True`

Cue: *"Attack pattern non-empty means human approval required regardless of
memory state. The agent never auto-dismisses a real attack."*

### 1:50 — 2:00 — Rubric close

```
Innovation:      counterfactual memory + memory-bypass RouteTrace
Memory & flow:   memory is the agent's first move, cost is visible per alert
Technical:       17 Hypothesis property tests, deterministic CI seed,
                 21 tests passing in CI
UX:              two-tab cockpit, color-coded triage pills, Altair cost curve
Real-world:      SOC analysts and on-call SREs both stare at alert queues
```

Cue: *"Stop rediscovering the same triage decisions every on-call shift."*

## Troubleshooting

### "The cost curve is flat / no bypass fires"

Likely cause: live mode is hitting Hindsight Cloud but the bank is empty
(no prior decisions to be consistent with). Fix: in the sidebar, click
`Seed 5 memories into Hindsight`. Wait ~10 seconds. Re-run `Analyze queue`.

If still flat: check that the cockpit shows `Hindsight connected` (not
`Fallback memory`). If fallback, env vars are missing or the API key is
revoked.

### "Live model calls badge is missing"

`CASCADEFLOW_LIVE_GROQ=true` is required AND `GROQ_API_KEY` must be set in
the `.env` file. The `load_dotenv()` call in `app.py` reads from
`incident-memory-agent/.env`. Restart Streamlit after editing `.env`.

### "Streamlit shows AttributeError on a queue row"

Most likely the `cost_tracker` cached resource holds state from a previous
run. Click `Reset cost curve` in the queue tab header.

### "Smoke test reports `bypass_steps=0`"

Pre-OpenRecall this was acceptable. Post-audit-fix the smoke test STRICTLY
asserts `bypass_steps >= 1` after seeding 6 false_positive memories per
fingerprint family. If this fails, run the
`#correctness-properties.md` reference and re-verify P6 manually:

```bash
cd incident-memory-agent
python -m pytest tests/property/test_triage.py::test_strong_model_bypass_invariant -q --hypothesis-profile=ci -v
```

If that test passes but smoke fails, the `_local_recall` keyword scorer
likely changed and no longer crosses 0.85 against the seeded memories. Add
more overlapping content text to the smoke seed list (in `smoke_queue()`).

### "Hindsight Cloud returns 401"

The API key has been revoked or rotated. Check the Vectorize dashboard.
Replace `HINDSIGHT_API_KEY` in `.env`. The cockpit will pick up the new
value on the next Streamlit rerun.

### "Recording shows `Fallback memory` instead of `Hindsight connected`"

`HINDSIGHT_API_KEY` is unset OR `HINDSIGHT_BASE_URL` returned 5xx. The 2-second
HEAD probe in `_init_hindsight` is what flips the badge. Check connectivity
and key validity, then restart Streamlit.

## Recording hardware/software notes

- Use OBS Studio or Streamlit's built-in screenshot. Disable browser
  notifications and any notification trays.
- 1080p recommended. The Altair chart renders cleanly at that resolution.
- Include audio narration. Mute system sound effects.
- Keep the recording under 2:00. Hackathon judging panels skip videos
  longer than 2 minutes.
