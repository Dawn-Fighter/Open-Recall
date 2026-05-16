# Demo Runbook

Use this script for a live or recorded walkthrough.

## 1. Start the App

```bash
source .venv/bin/activate
streamlit run app.py
```

The app works immediately in fallback mode. For the strongest integration demo,
start Hindsight first and set `CASCADEFLOW_LIVE_GROQ=true`.

## 2. Prove Memory Recall

Select `Known SRE: checkout CrashLoopBackOff`, then click `Analyze incident`.
The memory recall panel should show a prior checkout or ConfigMap incident. The
audit trace should include the normalized alert step and RCA investigation step.

## 3. Prove Escalation

Select `Security: WAF SQL injection`. The top badge and audit trace should show
an escalated route because security-relevant incidents require stronger review.

## 4. Prove Learning Loop

Select `Learning loop: cold fraud scoring outage`. If no close memory is shown,
enter the final root cause and click `Mark resolved and retain memory`. The app
reruns the analysis and the newly retained memory becomes visible.

## 5. Call Out Metrics

Point to:

- `Run cost`
- `Saved vs strong-only`
- `Memory hits`
- `Route`
- `Reason`
- `Live call`

These fields make the routing and cost decisions visible instead of hiding them
behind a chatbot response.
