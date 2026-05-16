# Hackathon Submission Notes

## Project

Open-Source Hindsight Incident Memory Agent

## One-Line Pitch

An incident response cockpit that recalls prior production failures, routes RCA
work through cost-aware model paths, and retains the final fix so the next
on-call shift starts with memory instead of guesswork.

## What It Demonstrates

- Persistent operational memory through Hindsight retain/recall.
- CascadeFlow-style route traces with confidence, model, cost, latency, budget,
  and escalation reason.
- Verification-first runbooks for SRE, security, and hybrid incidents.
- A learning loop that turns resolved incidents into future response context.
- Deterministic fallback mode so the project can be reviewed without credentials.

## Suggested Evaluation Path

1. Run the Streamlit app.
2. Analyze the checkout sample to show memory-assisted RCA.
3. Analyze the SQL injection sample to show security escalation.
4. Analyze and retain the fraud scoring sample to show before/after memory.
5. Inspect the audit trace to verify route, cost, latency, and model decisions.

## Production Extensions

- Add auth and tenant separation around retained memory banks.
- Replace demo keyword matching with organization-specific alert taxonomy.
- Add redaction before sending incident text to any model provider.
- Export audit traces to the incident management system.
- Require human approval gates before applying containment actions.
