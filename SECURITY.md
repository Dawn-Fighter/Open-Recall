# Security

This project handles incident notes, alert text, and optional API credentials.
Treat local runs as sensitive operational tooling.

## Reporting

For now, open a private issue or contact the maintainer directly before
publishing exploitable details. Do not include real secrets, production tokens,
customer data, request bodies, or account identifiers in public reports.

## Supported Scope

The repository is a demo implementation. Security fixes should prioritize:

- Secret handling in `.env`, the FastAPI process environment, and logs.
- Hindsight Cloud retain/recall payload safety.
- Prompt injection resistance for incident text passed to model providers.
- Clear separation between fallback demo data and real retained incident memory.

## Operational Guidance

- Use synthetic or redacted alerts in public demos.
- Keep `CASCADEFLOW_LIVE_GROQ=false` unless you intentionally want live model
  calls.
- Memory is backed by Hindsight Cloud at `https://api.hindsight.vectorize.io`,
  authenticated with a Bearer `HINDSIGHT_API_KEY`. The local Hindsight Docker
  setup is no longer the supported path; remove any leftover
  `HINDSIGHT_API_LLM_*` / `HINDSIGHT_API_CONSOLIDATION_*` /
  `HINDSIGHT_API_RETAIN_*` variables from local `.env` files. They are harmless
  but unused.
- When `HINDSIGHT_API_KEY` is unset or the cloud endpoint is unreachable, the
  backend falls back to the deterministic local store
  (`data/seed_incidents.json` plus `data/local_memory.json`). Treat
  `data/local_memory.json` and `data/decision_cache.json` as sensitive and do
  not commit them; the `.gitignore` enforces this.
- Review Hindsight and Groq deployment settings before using this with real
  production incidents.

### Secret rotation

Any committed `GROQ_API_KEY` or `HINDSIGHT_API_KEY` MUST be rotated at the end
of the project before publishing the repo publicly. The current development
`.env` carries live keys for hackathon demo use only. Rotate by issuing a new
key in the respective provider console, replacing the value in the local `.env`
(never in source control), and revoking the old credential.
