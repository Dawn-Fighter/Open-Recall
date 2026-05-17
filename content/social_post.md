I built OpenRecall — an alert triage co-pilot for SOC analysts and on-call SREs.

Stack:
- Streamlit cockpit with two tabs: Single alert + Queue
- Hindsight Cloud (api.hindsight.vectorize.io) for persistent memory
- cascadeflow for cost-aware routing + per-batch budget enforcement
- Groq qwen3-32b (cheap) and openai/gpt-oss-120b (strong)

Three pillars:

1. Counterfactual memory + auto-triage. Every retained alert carries the
   triage decision plus dead ends. The agent's FIRST move is memory,
   not the LLM.

2. Cost curve visibility. Live Altair chart shows OpenRecall cost vs
   strong-model-only baseline, green band growing as memory accumulates.
   When memory is consistent, the strong model bypasses and the trace
   shows model="memory-bypass".

3. Alert DNA fingerprinting. Six-field structured fingerprint
   (error_class, service_role, dependency_pattern, signal_shape,
   attack_pattern, environment) keyed into Hindsight Cloud recall.

15 correctness properties validated by Hypothesis under a deterministic
CI seed: fingerprint determinism, round-trip, triage determinism, bypass
invariant, retain idempotence, cost-curve monotonicity, security-novel
kill switch, recall-then-retain consistency, budget enforcement, audit
trace completeness.

Open source. Self-hosted memory + Cloud option. Property-tested. Built
for the Hindsight x cascadeflow hackathon.
