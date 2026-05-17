# OpenRecall — Full Feature Demo Script

A step-by-step video demo script covering every feature. Total runtime: ~5 minutes.

---

## Pre-requisites

```bash
cd incident-memory-agent
cp .env.example .env
# Edit .env with your real GROQ_API_KEY and HINDSIGHT_API_KEY
# Set CASCADEFLOW_LIVE_GROQ=true
```

---

## Part 1: Starting the Servers (0:00 – 0:30)

### Terminal 1 — Backend

```bash
cd incident-memory-agent
source .venv/bin/activate
uvicorn api:app --reload --port 8000
```

### Terminal 2 — Frontend

```bash
cd incident-memory-agent/frontend
npm run dev
```

### Terminal 3 — Verify

```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
```

**Show on screen:** `hindsight_connected: true`, `groq_live: true`

**Narration:** "OpenRecall is running with live Hindsight Cloud memory and Groq LLM routing. Let's open the cockpit."

Open **http://localhost:3000** in browser.

**Show on screen:** The header badges showing "● Hindsight" (green) and "● Groq Live" (blue).

---

## Part 2: Triage Tab — First Alert (0:30 – 1:30)

### 2a. Submit a fresh alert

Click the **"CrashLoopBackOff"** quick-send pill, or paste:

```
SEV-2 prod checkout-service CrashLoopBackOff after deploy 2026.05.16. Pods restart every 40s. Last log: KeyError PAYMENT_PROVIDER_URL. Recent ConfigMap cleanup removed env var. 5xx on checkout started at 14:07 UTC.
```

**Show on screen:** Watch the agent steps stream in one by one:
1. Normalizing alert → service detected
2. Fingerprinting → Alert DNA extracted
3. Querying Hindsight memory bank
4. Memory confidence sufficient → Strong LLM bypassed
5. Triage decision: False Positive (85.7%)

**Narration:** "The agent fingerprinted the alert, found consistent prior decisions in Hindsight Cloud, and bypassed the expensive strong model entirely. Cost: $0.00004 instead of $0.0004."

### 2b. Inspect the triage card

Point to:
- **Decision pill** (green "False Positive 85.7%")
- **Alert DNA Fingerprint** section (6 structured fields)
- **Prior Incidents** (3 matches, all `false_positive`)
- **Cost line** ($0.00004, savings shown)
- **Dead Ends** ("restarted pods, made it worse")
- **Route Trace** showing `model=memory-bypass, llm_skipped=true`

**Narration:** "Every prior analyst's decision and dead ends are surfaced before investigation begins. The next responder won't restart pods."

---

## Part 3: Security Alert — Kill Switch (1:30 – 2:15)

Click the **"WAF SQL Injection"** quick-send pill, or paste:

```
HIGH prod waf SQL injection alert grouped 63 requests against api-gateway /search?q=' OR 1=1--. Source ASN repeated across 12 IPs. Some 500s observed.
```

**Show on screen:**
- Decision: **Escalated** (red pill)
- `requires_human_approval: true`
- Escalation reason: "security-novel: human approval required"
- Router: `openai/gpt-oss-120b` (strong model forced)
- Fingerprint shows `attack_pattern: sql injection`

**Narration:** "Even though memory has prior decisions, the non-empty attack pattern fires the security-novel kill switch. The strong model is forced, and human approval is required. The system recommends — the human decides."

---

## Part 4: Override & Retain — Learning Loop (2:15 – 2:45)

On the triage card from Part 2 (the CrashLoopBackOff alert):

1. Click **"Override & Retain"**
2. Change decision to `known_benign`
3. Add dead end: "scaled replicas to 10, no improvement"
4. Click **Save & Retain**

**Show on screen:** Success message "Retained to memory. The next analyst will inherit this decision."

**Narration:** "That decision and dead end are now in Hindsight Cloud. The next analyst on the next shift will see them immediately."

---

## Part 5: Cost Curve (2:45 – 3:00)

Look at the **mini cost curve** in the header (green line below red baseline).

Or open Terminal 3:
```bash
curl -s http://127.0.0.1:8000/cost-curve | python3 -m json.tool
```

**Show on screen:** Points where bypassed alerts have `cost: 0` with `baseline` preserved. The green savings band grows.

**Narration:** "Every bypassed alert saves the full strong-model cost. The savings band grows as memory accumulates."

---

## Part 6: Calibration Tab (3:00 – 3:30)

Click the **"Calibration"** tab.

**Show on screen:**
- Total Decisions tracked
- Accuracy percentage
- Override Rate
- Auto-Close eligibility status ("Need 50+ decisions, >90% accuracy")
- Confidence calibration buckets (when populated)

**Narration:** "The calibration dashboard tracks every proposed decision against analyst overrides. Once accuracy exceeds 90% over 50+ decisions, the SOC lead can enable auto-close for low-risk categories."

---

## Part 7: SOAR Webhooks Tab (3:30 – 4:15)

Click the **"SOAR Webhooks"** tab.

### 7a. Test Splunk SOAR

1. Select **"Splunk SOAR"** platform
2. The template payload auto-fills
3. Click **"Send Test Webhook"**

**Show on screen:** Enrichment response with:
- `status: enriched`
- `recommended_action: close_with_review` or `auto_close`
- `memory_bypassed: true`
- `dead_ends` from prior analysts
- `cost` and `latency`

### 7b. Test Sentinel

1. Select **"Sentinel"**
2. Template shows a SQL injection incident
3. Click **"Send Test Webhook"**

**Show on screen:** Response shows `recommended_action: escalate_to_tier2`

**Narration:** "Any SOAR platform — Splunk, Sentinel, or custom — can POST alerts to these webhooks and get back enrichment data inline. The analyst sees the proposed decision, dead ends, and recommended action without leaving their existing tool."

### 7c. Show the endpoint URL

Point to the endpoint display: `POST http://localhost:8000/webhook/splunk`

**Narration:** "Configure this URL as an action in your SOAR playbook. No code changes needed on the SOAR side."

---

## Part 8: Tenants & Users Tab (4:15 – 4:45)

Click the **"Tenants & Users"** tab.

### 8a. Show existing tenants

**Show on screen:** "Default Team" with bank `openrecall`

### 8b. Create a new team

1. Type "Security Operations" in the name field
2. Type "openrecall-secops" in the bank ID field
3. Click **"Create"**

**Show on screen:** New tenant appears in the list with its own memory bank.

### 8c. Create a user

1. Select "Security Operations" tenant
2. Select "SOC Lead" role
3. Enter email: `maya@corp.com`
4. Enter name: `Maya Chen`
5. Click **"Create"**

**Show on screen:** API key generated — "Save this key, it won't be shown again."

**Narration:** "Each team gets an isolated Hindsight memory bank. A security team's false positives don't pollute the SRE team's memory. Role-based access controls who can override, who can enable auto-close, and who can manage tenants."

---

## Part 9: Stats Summary (4:45 – 5:00)

Point to the header stats:
- **Alerts Processed:** growing count
- **LLM Cost Saved:** dollar amount
- **Savings Rate:** percentage

**Narration:** "OpenRecall makes prior triage decisions and dead ends available before the next investigation begins, while keeping every routing and cost decision visible in real time. Memory first, LLM only when memory says so."

---

## Key Talking Points Throughout

| Feature | What to emphasize |
|---|---|
| Memory bypass | "Zero LLM cost on consistent repeats" |
| Dead ends | "Don't try what already failed" |
| Security kill switch | "The system recommends, the human decides" |
| SOAR webhooks | "Embed in existing workflow, no copy-paste" |
| Calibration | "Earn trust before enabling auto-close" |
| Multi-tenant | "Team isolation, role-based access" |
| Cost curve | "Visible savings that grow over time" |

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Header shows "○ Fallback" | Check `HINDSIGHT_API_KEY` in `.env` |
| Header shows "○ Deterministic" | Set `CASCADEFLOW_LIVE_GROQ=true` in `.env` |
| Everything escalates | Run `POST /seed` to populate memory, then retain consistent decisions |
| SOAR webhook returns error | Confirm backend is running on port 8000 |
| Calibration shows 0 decisions | Submit alerts via SOAR webhooks (they auto-track) |
