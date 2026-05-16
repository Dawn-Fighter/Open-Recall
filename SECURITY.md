# Security

This project handles incident notes, alert text, and optional API credentials.
Treat local runs as sensitive operational tooling.

## Reporting

For now, open a private issue or contact the maintainer directly before
publishing exploitable details. Do not include real secrets, production tokens,
customer data, request bodies, or account identifiers in public reports.

## Supported Scope

The repository is a demo implementation. Security fixes should prioritize:

- Secret handling in `.env`, Streamlit settings, and logs.
- Hindsight retain/recall payload safety.
- Prompt injection resistance for incident text passed to model providers.
- Clear separation between fallback demo data and real retained incident memory.

## Operational Guidance

- Use synthetic or redacted alerts in public demos.
- Keep `CASCADEFLOW_LIVE_GROQ=false` unless you intentionally want live model
  calls.
- Do not commit `data/local_memory.json`; it can contain retained incident
  details from local testing.
- Review Hindsight and Groq deployment settings before using this with real
  production incidents.
