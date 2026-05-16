# Building an Incident Memory Agent with Hindsight and cascadeflow

Incidents repeat themselves: a missing ConfigMap key, a bad liveness probe, a saturated database pool, an expired credential. The expensive part is not only fixing them; it is rediscovering what the team already learned last time.

This project is a Streamlit Incident Memory Agent for SRE and security responders. It uses open-source Hindsight as persistent incident memory and cascadeflow as the runtime intelligence layer that decides when to stay on a cheaper Groq model and when to escalate to a stronger one.

The demo follows a real incident lifecycle: intake, triage, memory recall, investigation, runbook generation, containment notes, and post-incident learning. The agent is intentionally an assistant, not an auto-fixer. It recommends verification commands first, preserves evidence, and stores the final root cause only when the user marks the incident resolved.

The key moment in the demo is the learning loop. A known CrashLoopBackOff alert recalls a similar previous incident and stays on the cheaper model. An ambiguous incident gets a weak memory match, so cascadeflow escalates the RCA step and shows the decision trace. A security-flavored WAF alert recommends enrichment and containment rather than blind remediation. Then a cold fraud-scoring outage starts with no close memory, gets resolved, is retained, and immediately becomes reusable context for the next similar alert.

Hindsight makes memory central: every resolved incident becomes future operational context. cascadeflow makes runtime control visible: model, confidence, route reason, latency, estimated cost, strong-model baseline savings, budget state, live-call status, and escalation are shown in the UI. Together, they turn a generic chatbot into a responder that remembers, routes intelligently, and improves after every postmortem.
