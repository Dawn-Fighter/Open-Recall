I built an open-source Incident Memory Agent for SRE/security response.

Stack:
- Streamlit UI
- Hindsight running locally in Docker for persistent incident memory
- cascadeflow for model routing, confidence escalation, cost estimates, and audit traces
- Groq models for fast alert normalization and RCA

The demo shows the agent recalling past incidents, recommending verification commands before remediation, escalating ambiguous/security cases to a stronger model, and retaining a cold incident RCA so the next similar alert has memory-backed context.

It also shows estimated run cost, strong-model baseline savings, latency, budget remaining, route reason, and the live-call audit trail.

The goal: stop rediscovering the same incident lessons every on-call rotation.
