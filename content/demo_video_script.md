# 2-minute demo script

0:00-0:15 — Problem: incidents repeat, but responders lose context across rotations. Show app layout and confirm the badges say Hindsight connected and Live model calls for the recorded demo.

0:15-0:40 — Known SRE incident: select checkout CrashLoopBackOff. Run analysis. Point to normalized incident, Hindsight recall match, verification commands, cheap-model cascadeflow route, and Saved vs strong-only.

0:40-1:05 — Ambiguous incident: select payments latency/DB pool. Show weak confidence and cascadeflow escalation to stronger Groq model. Highlight route reason, latency, cost estimate, budget remaining, and audit trace.

1:05-1:25 — Security incident: select WAF SQL injection. Show evidence preservation, enrichment commands, containment notes, and no destructive auto-remediation.

1:25-2:00 — Learning loop: select cold fraud scoring outage. First pass shows no close memory. Mark resolved and retain the RCA. The app reruns, recalls the new resolved incident, and changes the hypothesis from generic to memory-backed. Close with judging criteria: memory is central, runtime intelligence is visible, and the workflow maps to real SRE/security incident response.
