---
name: openrecall-secret-rotate
description: Rotate the Groq and Hindsight Cloud API keys safely before publishing the OpenRecall repo publicly. Use when preparing the public release, when a key is suspected compromised, or when the secret-handling smoke check is failing.
---

# Rotate OpenRecall API keys safely

OpenRecall holds two live secrets during hackathon development:

- `GROQ_API_KEY` (prefix `gsk_`) — Groq inference
- `HINDSIGHT_API_KEY` (prefix `hsk_`) — Hindsight Cloud memory

Per the hackathon agreement and `SECURITY.md`, both must be rotated before
publishing the repo publicly. Use this procedure.

## Step 1 — Inventory exposure

Run from workspace root:

```bash
cd incident-memory-agent
git log --all --full-history --source -- .env
```

If `.env` ever appeared in a commit (per the Git history check), the
secrets it carried at that point are public-domain leaked, not just present
in HEAD. They must be rotated regardless of any subsequent purge.

Also check for inline matches in tracked files:

```bash
cd incident-memory-agent
git grep -E "gsk_[A-Za-z0-9_]{20,}|hsk_[A-Za-z0-9_]{20,}"
```

If anything matches except `.env` itself, surface those files first — they
need scrubbing before continuing.

## Step 2 — Rotate at the provider consoles

### Groq

1. Open https://console.groq.com/keys
2. Identify the key matching the `gsk_DObPn...` prefix in
   `incident-memory-agent/.env`.
3. Click **Revoke** on the existing key.
4. Click **Create API Key** with a descriptive label (e.g.,
   `openrecall-public-release-YYYY-MM-DD`).
5. Copy the new `gsk_...` value to a temporary safe place.

### Hindsight (Vectorize)

1. Open https://ui.hindsight.vectorize.io (or the Hindsight Cloud admin
   page provided in the hackathon docs).
2. Go to API Keys / Tokens.
3. Revoke the `hsk_fa7bb7a6...` key currently in `.env`.
4. Generate a new key for the `openrecall` bank, scoped to read+write.
5. Copy the new `hsk_...` value.

## Step 3 — Update the local .env (NOT tracked)

Only the local `.env` file in `incident-memory-agent/.env` should hold live
keys. It is gitignored (`.env` and `.env.*` patterns in `.gitignore`).

Replace these two lines:

```dotenv
GROQ_API_KEY=gsk_<NEW_VALUE>
HINDSIGHT_API_KEY=hsk_<NEW_VALUE>
```

Leave `.env.example` alone — it must always carry only placeholders
(`gsk_your_key_here`, `hsk_your_key_here`). The smoke test enforces this:

```python
# smoke_test.py::smoke_env_example
pattern = re.compile(r"gsk_[A-Za-z0-9_]{20,}|hsk_[A-Za-z0-9_]{20,}")
assert not pattern.search(text), ".env.example contains a live-looking key"
```

## Step 4 — Verify the new keys work

```bash
cd incident-memory-agent
python scripts/smoke_test.py
```

Expected output:

```
smoke ok: samples=6 fallback=False traces=18      # fallback=False = Hindsight connected
smoke queue ok: alerts=100 ... bypass_steps=1 ...
smoke env.example ok: all keys present, no live secrets detected
smoke seed_incidents schema ok: 18 records
```

If you get `fallback=True`, the new Hindsight key didn't authenticate. Try
the inline check:

```bash
python -c "import httpx; r = httpx.head('https://api.hindsight.vectorize.io', timeout=5, headers={'Authorization': f'Bearer hsk_NEW_VALUE_HERE'}, follow_redirects=True); print(r.status_code)"
```

A `200`, `401`, or `403` means the host is up; the connection works. A
`5xx` or connection timeout means something else is wrong.

## Step 5 — Verify the FastAPI backend picks up the new keys

```bash
cd incident-memory-agent
uvicorn api:app --reload --port 8000
```

In a second terminal:

```bash
curl -s http://127.0.0.1:8000/health | jq
```

Confirm:

- `hindsight_connected: true` — confirms Hindsight key is valid.
- `groq_live: true` — confirms `CASCADEFLOW_LIVE_GROQ=true` and the Groq
  key is valid.

Submit any sample alert via `curl -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' -d '{"alert":"checkout-service crashloop after deploy"}'`.
The response audit trace should show real non-zero `latency_ms` and
`cost_usd` values for the live LLM calls.

## Step 6 — Optional: scrub from git history

If `.env` was ever committed (inspection in Step 1 found it), the live keys
that file carried at that point are leaked into git history. Rotation alone
is sufficient — old keys are revoked. But if you want to additionally purge
the file from history:

```bash
cd incident-memory-agent
git filter-repo --path .env --invert-paths    # requires git-filter-repo
# OR (legacy)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all
git push origin --force --all                 # destructive; coordinate with collaborators
```

This is OPTIONAL because the keys are already rotated. The rationale to do
it anyway: hides the historical bug from public scrutiny if the hackathon
submission is being reviewed for security hygiene.

## Step 7 — Document the rotation

Update `incident-memory-agent/SECURITY.md` with a single line under "Secret
rotation":

```markdown
- 2026-MM-DD: rotated GROQ_API_KEY and HINDSIGHT_API_KEY before public
  release. Old keys revoked at provider consoles.
```

Commit `SECURITY.md` only. Do NOT commit `.env`.

## Step 8 — Final smoke + push

```bash
cd incident-memory-agent
make compile && make pbt && make smoke
git status                                     # confirm .env NOT tracked
git push origin main                           # safe to push
```

## When something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| Smoke fails with `fallback=True` | New Hindsight key invalid OR cloud unreachable | Verify key in Vectorize dashboard; check `HINDSIGHT_BASE_URL` |
| Cockpit shows `Live model calls` but cost is `$0.000000` | Bypass fired (working as designed) OR Groq returned `model_error` | Check audit trace for `model_error` field |
| `.env.example` smoke check fails | A live-looking key leaked into the placeholder file | Restore placeholders to `gsk_your_key_here` / `hsk_your_key_here` |
| Live mode raised `RateLimitError` from Groq | Free tier exhausted | Switch `CASCADEFLOW_LIVE_GROQ=false` for the demo, fall back to Demo_Mode |

## What you must NEVER do during rotation

- ❌ Commit `.env` to fix the rotation. Always edit it locally.
- ❌ Replace `.env.example` placeholders with real keys "to test the smoke".
  The smoke check is specifically designed to catch this.
- ❌ Generate keys without a label/scope. Provider consoles allow scoped
  keys — use them so the next rotation has clear targets.
- ❌ Skip Step 2 (revoke) and only do Step 3 (replace). The old key remains
  valid until revoked at the provider.
