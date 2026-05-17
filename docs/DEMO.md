# Demo Runbook

A 60-second demo script that hits every rubric criterion. Use the live
Hindsight Cloud + Live Groq mode for the strongest recording.

## 0. Pre-flight (10 seconds before recording)

```bash
# Terminal 1 — backend
export HINDSIGHT_API_KEY=hsk_your_key_here
export GROQ_API_KEY=gsk_your_key_here
export CASCADEFLOW_LIVE_GROQ=true
uvicorn api:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

In a third shell, sanity-check the live mode:

```bash
curl -s http://127.0.0.1:8000/health | jq
```

`hindsight_connected` and `groq_live` should both be `true`. If either is
`false` the workflow still demos, but the live integration is not proven.

Open `http://localhost:3000` in the browser.

## 1. Submit a fresh alert (0:00 - 0:15)

Paste a raw alert into the chat input — for example a checkout-service
crashloop after a configmap deploy. Click submit.

Cue: *"Memory first, LLM only when memory says so. Watch the agent steps
unfold in order."*

Watch the streaming agent steps:
- Normalize → service detected
- Fingerprint → six-field Alert DNA extracted
- Memory query → recall hits surfaced (or "novel pattern")
- Routing decision → strong model or memory-bypass
- Triage → decision pill rendered

## 2. Inspect the triage card (0:15 - 0:30)

Point to:
- The decision pill (color-coded: green for `false_positive` / `known_benign` / `duplicate`, red for `escalated`, amber otherwise).
- The fingerprint section — six structured fields, not free-text keywords.
- The prior incidents block — top three memory matches with score and prior decision.
- The cost line — actual cost, savings, latency.
- The dead-ends panel — paths prior responders already disproved.

Cue: *"This is what counterfactual memory looks like. The agent doesn't
just say 'try X'; it tells the next responder 'don't try Y, the team
already disproved that.'"*

## 3. Override and retain (0:30 - 0:45)

Open the override flow on the triage card. Set the decision to
`false_positive`. Add a dead end: *"restarted DB pods, made it worse."*
Click save & retain.

Behind the scenes the cockpit calls `POST /retain`. The decision and
dead end are written to Hindsight Cloud (or the local fallback store
when offline).

Cue: *"That decision and the dead end are now in Hindsight Cloud. The
next analyst won't restart DB pods."*

## 4. Re-submit the same alert (0:45 - 0:55)

Paste the same raw alert again. Watch:
- The agent step trace shortcuts to "memory bypass" / "served from
  decision cache".
- The decision pill matches the override.
- The cost line reads `$0.00` with full savings.

Cue: *"The strong model didn't run. Property test P6 enforces this
invariant across every release."*

Optional: hit `GET /cost-curve` to confirm the curve has the new bypass
point with `cost: 0` and the original `baseline` preserved — that's the
Property 9 invariant (`cost_usd <= baseline_cost_usd`).

## 5. Single alert security demo (0:55 - 1:00)

Submit a security-flavoured alert (e.g. WAF SQL injection signature on
the api-gateway). Even if memory is consistent, the agent should set
`requires_human_approval=true` and surface "security novel — analyst
must review" in the escalation reason.

Cue: *"Attack pattern non-empty fires the security-novel kill switch
regardless of memory state. The agent recommends, the human decides."*

## What to point to throughout

- `/health` badges — proves live cloud integration.
- Cost line dropping to `$0.00` after retain — proves cascadeflow value.
- Memory-bypass step in the agent trace — proves zero LLM cost on
  memory-consistent repeats.
- Skip-these-paths panel — proves counterfactual memory works
  end-to-end.

## Offline fallback

If the demo machine has no network, omit the live env vars before
starting the backend. The cockpit falls back to local JSON memory and
deterministic regex fingerprints. The triage card, override flow, cost
line, and audit trace all still work — only the `/health` flags flip to
`hindsight_connected: false` and `groq_live: false`.
