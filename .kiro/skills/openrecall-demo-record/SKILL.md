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
   echo [] > data/local_memory.json
   echo {} > data/decision_cache.json
   ```
   This wipes any leftover retained memory + alert hash cache from previous
   demo runs so the "before/after" cost line is clean.

4. **Start the backend.**
   ```bash
   uvicorn api:app --reload --port 8000
   ```
   Then in a second terminal:
   ```bash
   cd frontend && npm run dev
   ```

5. **Verify mode flags.** Hit the API:
   ```bash
   curl -s http://127.0.0.1:8000/health | jq
   ```
   Confirm `hindsight_connected: true` and `groq_live: true`.

6. **Open the cockpit.** Navigate to `http://localhost:3000`. The header
   should reflect the same flags as `/health`.

## The 60-second beat sheet

### 0:00 — 0:10 — Hero shot

Camera frames the cockpit + browser tab title `OpenRecall Triage Copilot`.
Cue: *"OpenRecall is an alert triage co-pilot. Memory first, LLM only when
memory says so."*

In a small overlay, show the `/health` JSON response proving live cloud
integration.

### 0:10 — 0:35 — Submit a fresh alert

Paste a checkout-service crashloop alert into the chat input. Hit submit.
Narrate the streaming agent steps as they appear:

- Normalize: service detected
- Fingerprint: six-field Alert DNA
- Memory query: hit count
- Routing OR memory bypass
- Triage decision pill rendered

Cue: *"Watch the agent's first move. It's the memory query, not the LLM."*

### 0:35 — 0:55 — Inspect the triage card

Walk through the collapsible sections in order:

- Decision pill (color-coded).
- Fingerprint section — six structured fields (Alert DNA).
- Prior incidents — top three matches with score and prior decision.
- Cost line — actual cost, savings, latency.
- Skip-these-paths panel — the dead ends from prior responders.

Cue: *"Cascadeflow earns its keep on every memory hit. The cost line is
zero when memory bypasses."*

### 0:55 — 1:25 — Override + retain

Open the override flow on the card. Set decision to `false_positive`. Add a
dead end: *"restarted DB pods, made it worse"*. Click save & retain. Watch
the success toast and the card update with the new decision.

Cue: *"That decision and the dead end are now in Hindsight Cloud. The next
analyst won't waste time restarting DB pods."*

### 1:25 — 1:45 — Re-submit + bypass

Paste the same alert again. Show:
- Agent step trace shortcuts to "memory bypass" / "served from decision cache".
- Decision pill matches the override.
- Cost line reads `$0.00` with full savings.

Switch to a terminal and hit `GET /cost-curve`. Point to the new bypass
point with `cost: 0` and `baseline` preserved.

Cue: *"Strong model never ran. Property test P6 enforces this invariant
across every release."*

### 1:45 — 2:00 — Security-novel kill switch

Submit a security-flavoured alert (WAF SQL injection on api-gateway). Show
that even with consistent memory, the card surfaces:

- Decision pill: `escalated` or `real`
- Escalation reason: `security-novel: human approval required`
- `requires_human_approval: true`

Cue: *"Attack pattern non-empty fires the security-novel kill switch
regardless of memory state. The agent recommends, the human decides."*

### Rubric close

```
Innovation:      counterfactual memory + memory-bypass RouteTrace
Memory & flow:   memory is the agent's first move, cost is visible per alert
Technical:       17 Hypothesis property tests, deterministic CI seed
UX:              streaming agent steps, color-coded triage pills, structured triage card
Real-world:      SOC analysts and on-call SREs both stare at alert queues
```

Cue: *"Stop rediscovering the same triage decisions every on-call shift."*

## Troubleshooting

### "The cost line stays at the strong-model price / no bypass fires"

Likely cause: live mode is hitting Hindsight Cloud but the bank is empty
(no prior decisions to be consistent with). Fix: hit
`POST http://127.0.0.1:8000/seed` to push the seed incidents. Wait ~10
seconds. Re-submit the same alert.

If still flat: check that `/health` returns `hindsight_connected: true`.
If `false`, env vars are missing or the API key is revoked.

### "groq_live is false in /health"

`CASCADEFLOW_LIVE_GROQ=true` is required AND `GROQ_API_KEY` must be set in
the `.env` file. The `load_dotenv()` call in `api.py` reads from
`incident-memory-agent/.env`. Restart the FastAPI process after editing
`.env` (uvicorn `--reload` only watches `.py` files).

### "Smoke test reports `bypass_steps=0`"

Pre-OpenRecall this was acceptable. Post-audit-fix the smoke test STRICTLY
asserts `bypass_steps >= 1` after seeding 6 false_positive memories per
fingerprint family. If this fails, run the
`#correctness-properties.md` reference and re-verify P6 manually:

```bash
cd incident-memory-agent
python -m pytest tests/property/test_triage.py::test_strong_model_bypass_invariant -q --hypothesis-profile=ci -v
```

If that test passes but smoke fails, the local-recall keyword scorer
likely changed and no longer crosses 0.85 against the seeded memories. Add
more overlapping content text to the smoke seed list (in `smoke_queue()`).

### "Hindsight Cloud returns 401"

The API key has been revoked or rotated. Check the Vectorize dashboard.
Replace `HINDSIGHT_API_KEY` in `.env` and restart uvicorn.

### "/health returns hindsight_connected: false"

`HINDSIGHT_API_KEY` is unset OR `HINDSIGHT_BASE_URL` returned 5xx. The
2-second HEAD probe in `_init_hindsight` is what flips fallback. Check
connectivity and key validity, then restart uvicorn.

### "The frontend shows a network error on /analyze"

Confirm both processes are running: `curl http://127.0.0.1:8000/health`
should respond, and `http://localhost:3000` should load. If CORS is
blocking, confirm `api.py` still has `CORSMiddleware` with
`allow_origins=["*"]`.

## Recording hardware/software notes

- Use OBS Studio or any system screen recorder. Disable browser
  notifications and any notification trays.
- 1080p recommended.
- Include audio narration. Mute system sound effects.
- Keep the recording under 2:00. Hackathon judging panels skip videos
  longer than 2 minutes.
