# QuoteWise — Production setup guide (EC2 + Docker + Twilio)

End-to-end guide for a deployed QuoteWise stack: backend API, Celery worker, frontend, Postgres, Redis, Vertex AI, and **Twilio WhatsApp**.

**Your deployment (example):**

| Service | URL / port |
|---------|------------|
| Backend API | `https://api.shopveluna.in` |
| Frontend | your public site (e.g. `https://shopveluna.in`) |
| Health check | `GET https://api.shopveluna.in/healthz` → `{"status":"ok"}` |

**Docker services (expected):**

```
quotewise-backend-1         → :8000
quotewise-celery-worker-1   → (no public port)
quotewise-frontend-1        → :3000
quotewise-postgres-1        → internal
quotewise-redis-1           → internal
```

---

## 1. Architecture (what must work together)

```
WhatsApp user
    ↓
Twilio (inbound webhook)
    ↓ POST https://api.shopveluna.in/webhooks/twilio/whatsapp
FastAPI backend (ack + enqueue)
    ↓
Redis → Celery worker
    ↓
Postgres + Vertex AI (Gemini) + Twilio (outbound)
    ↓
PDF at https://api.shopveluna.in/pdfs/quote_<id>.pdf
```

The webhook **only enqueues** work. If Celery is down, messages are accepted but never processed.

---

## 2. Verify the stack is healthy

On the EC2 host:

```bash
cd ~/quotewise/backend   # or wherever docker-compose.yml lives
docker compose ps
```

All services should be `Up`. Postgres and Redis should be `healthy`.

From your laptop:

```bash
curl -s https://api.shopveluna.in/healthz
# → {"status":"ok"}
```

Check worker logs after sending a test message:

```bash
docker compose logs -f celery-worker
```

---

## 3. Production environment variables

Edit the env file used by **both** `backend` and `celery-worker` (same values in both services).

### 3.1 Core app

```bash
APP_ENV=prod
LOG_LEVEL=INFO

# Inside Docker Compose, use service names — not localhost
DATABASE_URL=postgresql+psycopg://quotewise:<STRONG_PASSWORD>@postgres:5432/quotewise
REDIS_URL=redis://redis:6379/0

PDF_STORAGE_DIR=data/pdfs
PDF_BASE_URL=https://api.shopveluna.in
QUOTE_VALIDITY_DAYS=30
SESSION_TTL_HOURS=72
```

### 3.2 LLM (Vertex AI — required for real conversations)

```bash
LLM_PROVIDER=vertex
GCP_PROJECT_ID=<your-gcp-project-id>
GCP_LOCATION=asia-south1
VERTEX_MODEL_FLASH=gemini-2.5-flash
VERTEX_MODEL_PRO=gemini-2.5-pro
LLM_CALL_TIMEOUT_SECONDS=20
```

**GCP credentials in Docker:** create a service account with **Vertex AI User**, download a JSON key, mount it into backend + celery containers:

```yaml
# In docker-compose.yml (backend + celery-worker)
volumes:
  - ./gcp-sa.json:/app/gcp-sa.json:ro
environment:
  GOOGLE_APPLICATION_CREDENTIALS: /app/gcp-sa.json
```

Enable **Vertex AI API** on the GCP project. Do not commit `gcp-sa.json` to git.

### 3.3 WhatsApp via Twilio

```bash
WA_PROVIDER=twilio

TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=<your-auth-token>
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886    # sandbox, or your approved sender

# Must match the URL configured in Twilio Console exactly (no trailing slash)
TWILIO_WEBHOOK_PUBLIC_URL=https://api.shopveluna.in/webhooks/twilio/whatsapp
```

Leave Meta `WA_*` vars empty when using Twilio.

### 3.4 Frontend container

```bash
NEXT_PUBLIC_BACKEND_URL=https://api.shopveluna.in
NEXT_PUBLIC_API_URL=https://api.shopveluna.in
NEXT_PUBLIC_WA_BOT_NUMBER=14155238886          # digits only, no + or spaces (wa.me link)
```

Rebuild/restart frontend after changing `NEXT_PUBLIC_*` (they are baked in at build time).

### 3.5 Apply changes

```bash
docker compose up -d --build backend celery-worker frontend
```

---

## 4. Database migrations

Run once per deploy (or after pulling new code with migrations):

```bash
docker compose exec backend alembic upgrade head
```

Expected migrations include:

- `0001` — core schema  
- `0002` — `wa_phone_number_id` on contractors  
- `0003` — contractor API keys  
- `0004` — contractor admin sessions (FR-001)  
- `0005` — session source for forwarded quotes (FR-002)  

Verify:

```bash
docker compose exec backend alembic current
```

---

## 5. Twilio WhatsApp setup (step by step)

### 5.1 Create Twilio account

1. Sign up at [https://www.twilio.com](https://www.twilio.com).
2. Console → **Account** → note **Account SID** and **Auth Token** → set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`.

### 5.2 WhatsApp Sandbox (fastest for testing)

1. Console → **Messaging** → **Try it out** → **Send a WhatsApp message**.
2. Join the sandbox from your phone (send the code shown, e.g. `join <word>` to the sandbox number).
3. Note the sandbox sender, e.g. `+1 415 523 8886` → set:
   ```bash
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```

### 5.3 Configure inbound webhook

1. In the WhatsApp sandbox (or your WhatsApp sender) settings, set **When a message comes in**:
   ```
   https://api.shopveluna.in/webhooks/twilio/whatsapp
   ```
   Method: **HTTP POST**.

2. Set `TWILIO_WEBHOOK_PUBLIC_URL` to that **exact** URL (Twilio signature validation uses it).

3. Restart backend after setting env vars:
   ```bash
   docker compose restart backend celery-worker
   ```

### 5.4 Test webhook reachability

Send any WhatsApp message to the Twilio sandbox number from your joined phone.

- Backend logs: `twilio.webhook.enqueued`
- Celery logs: routing + outbound `[MOCK WA twilio]` or real Twilio API call

```bash
docker compose logs -f backend celery-worker
```

If you get **403 invalid signature**: `TWILIO_WEBHOOK_PUBLIC_URL` does not match what Twilio calls (check HTTPS, path, no trailing slash mismatch).

### 5.5 Production WhatsApp sender (later)

Sandbox is for dev only. For production:

1. Twilio → **Messaging** → **WhatsApp senders** → register your business number (Meta approval).
2. Update `TWILIO_WHATSAPP_FROM=whatsapp:+91XXXXXXXXXX`.
3. Point the same webhook URL at the production sender.

### 5.6 Twilio vs contractor routing

Each inbound message is routed to a contractor using **`Contractor.wa_phone_number_id`**, which for Twilio must be the bot’s **E.164 number** (the `To` field), e.g. `+14155238886` — not the Twilio Account SID.

Set this when onboarding (web API or seed script below).

---

## 6. Register your first contractor

You need at least one contractor with **pricing** before quotes work.

### Option A — Web onboarding (recommended first time)

1. Open `https://<your-frontend>/onboarding`.
2. Complete:
   - Business profile (phone in E.164, e.g. `+919876543210`)
   - Rate card (upload PDF/CSV or paste text)
   - Go live — copy **buyer link** and **API key**
3. When creating the contractor, set **`wa_phone_number_id`** to your Twilio bot number:
   - Example: `+14155238886` (sandbox) or your production WA number.

If the UI does not expose `wa_phone_number_id`, update after signup:

```bash
docker compose exec backend python -c "
from app.db.base import SessionLocal
from app.db.models import Contractor
db = SessionLocal()
c = db.query(Contractor).order_by(Contractor.created_at.desc()).first()
c.wa_phone_number_id = '+14155238886'   # your Twilio To number
db.commit()
print(c.business_name, c.phone, c.whatsapp_link_slug, c.wa_phone_number_id)
db.close()
"
```

### Option B — WhatsApp `onboard` (FR-001 Phase 2)

From a **phone not yet registered** as a contractor, WhatsApp the bot:

```
onboard
```

Follow the bot’s prompts (business name, city, slug, work type, rate card). On completion you receive the buyer link and API key once.

### Option C — Seed script (dev / single-tenant)

```bash
WA_PHONE_NUMBER_ID=+14155238886 docker compose exec backend python scripts/seed_data.py
```

Creates contractor `+919999900001`, slug `dev`, with default painting + false ceiling rules.

---

## 7. End-to-end flow testing

Use a **buyer phone** (not the contractor phone) and the **contractor phone** (registered in DB).

### 7.1 Buyer direct quote → contractor approve

| Step | Who | Action |
|------|-----|--------|
| 1 | Buyer | Open `https://wa.me/<BOT_NUMBER>?text=quote-<slug>` or send `quote-<slug>` to the bot |
| 2 | Buyer | Answer AI questions (area, finish, etc.) |
| 3 | Contractor | Receives WhatsApp: “New quote ready for your approval…” |
| 4 | Contractor | Reply `approve` or `reject` |
| 5 | Buyer | Receives PDF on approve |

**`<slug>`** = contractor’s `whatsapp_link_slug` (e.g. `dev`).

### 7.2 FR-001 — `manage-rates` (registered contractor)

From the **contractor’s registered phone**:

```
manage-rates
```

Paste rates or send a PDF/TXT/CSV document → confirm with `yes` → new pricing version saved.

### 7.3 FR-002 — Forwarded buyer quote (auto PDF to contractor)

1. On your personal WhatsApp, receive a fake “buyer enquiry” (or use a second phone).
2. **Forward** that message to the QuoteWise Twilio bot number.
3. Bot asks **you** (contractor) for missing details.
4. Reply with answers (normal messages, not forwarded).
5. Bot auto-sends quote PDF to **contractor** — no `approve` step.

Twilio sets `Forwarded=true` on forwarded messages (parity with Meta `context.forwarded`).

### 7.4 Dashboard

1. Go to `https://<your-frontend>/quotes`.
2. Log in with the contractor **API key** from onboarding.
3. Confirm quotes appear with status and PDF links.

### 7.5 Demo UI (optional)

`https://<your-frontend>/demo` — synchronous chat without WhatsApp; useful to verify Vertex + pricing without Twilio.

---

## 8. PDF delivery checklist

WhatsApp document send uses a **public URL**:

```
https://api.shopveluna.in/pdfs/quote_<uuid>.pdf
```

Confirm:

1. `PDF_BASE_URL=https://api.shopveluna.in` on backend + celery.
2. PDFs are generated on a **shared volume** between backend and celery (same `PDF_STORAGE_DIR`).
3. FastAPI serves `/pdfs` (mounted in `app.main`).
4. URL is reachable from the internet (no auth wall on `/pdfs/*`).

```bash
curl -I https://api.shopveluna.in/pdfs/quote_<some-id>.pdf
# → 200 after a quote is generated
```

---

## 9. Reverse proxy / TLS (EC2)

Your API is already on HTTPS (`api.shopveluna.in`). Ensure nginx/Caddy/ALB:

- Proxies `https://api.shopveluna.in` → `localhost:8000` (backend)
- Proxies `https://shopveluna.in` → `localhost:3000` (frontend)
- Does **not** buffer/block Twilio webhook POSTs
- Forwards `X-Forwarded-Proto: https` (optional; `TWILIO_WEBHOOK_PUBLIC_URL` is the source of truth for signatures)

Webhook paths:

| Provider | URL |
|----------|-----|
| Twilio | `POST /webhooks/twilio/whatsapp` |
| Meta (if ever used) | `GET/POST /webhooks/whatsapp` |

---

## 10. Operational commands

```bash
# Logs
docker compose logs -f backend celery-worker

# Restart after env change
docker compose up -d --build backend celery-worker frontend

# DB shell
docker compose exec postgres psql -U quotewise -d quotewise

# List contractors
docker compose exec backend python -c "
from app.db.base import SessionLocal
from app.db.models import Contractor
db = SessionLocal()
for c in db.query(Contractor).all():
    print(c.business_name, c.phone, c.whatsapp_link_slug, c.wa_phone_number_id, c.api_key)
db.close()
"

# Run tests inside container (optional)
docker compose exec backend python -m pytest tests -q --ignore=tests/test_session_repo_db.py
```

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| Webhook 200 but no reply | Celery not running | `docker compose ps`; start `celery-worker` |
| Twilio 403 on webhook | Bad signature URL | Set `TWILIO_WEBHOOK_PUBLIC_URL` exactly as in Twilio Console |
| “No contractor with wa_phone_number_id” | Tenant not linked | Set contractor `wa_phone_number_id` to Twilio `To` E.164 |
| Contractor `approve` ignored | Active forward session or no pending direct quote | Complete forward flow or use buyer-direct quote |
| AI replies generic / wrong | `LLM_PROVIDER=mock` | Set `vertex` + GCP credentials |
| Vertex auth errors | Missing ADC in container | Mount `GOOGLE_APPLICATION_CREDENTIALS` JSON |
| PDF not sent | URL not public | Fix `PDF_BASE_URL`, proxy, shared volume |
| Frontend can’t reach API | Wrong build-time URL | Rebuild with `NEXT_PUBLIC_BACKEND_URL=https://api.shopveluna.in` |
| `manage-rates` rejected | Phone not registered | Use onboarded contractor phone or run `onboard` first |

---

## 12. Suggested rollout order

1. ✅ Containers up, `healthz` OK  
2. Run `alembic upgrade head`  
3. Configure Vertex (`LLM_PROVIDER=vertex` + service account)  
4. Set `PDF_BASE_URL=https://api.shopveluna.in`  
5. Twilio account + sandbox + webhook URL  
6. Set `WA_PROVIDER=twilio` and restart backend + celery  
7. Onboard first contractor (web or `onboard`) with correct `wa_phone_number_id`  
8. Test buyer quote → contractor `approve`  
9. Test `manage-rates` from contractor phone  
10. Test forwarded buyer quote (FR-002)  
11. Rebuild frontend with production API + WA bot number  
12. Move from Twilio sandbox to approved production sender when ready  

---

## 13. Reference docs in repo

| Doc | Contents |
|-----|----------|
| [FLOWS.md](FLOWS.md) | Buyer, admin (FR-001), forward (FR-002) flows |
| [DEMO.md](DEMO.md) | Local dev / demo UI |
| [feature_requests/FR-001-whatsapp-contractor-onboarding.md](feature_requests/FR-001-whatsapp-contractor-onboarding.md) | Admin WA spec |
| [feature_requests/FR-002-contractor-forwarded-buyer-quotes.md](feature_requests/FR-002-contractor-forwarded-buyer-quotes.md) | Forwarded quote spec |
| [.env.example](.env.example) | All environment variables |

---

## 14. Quick env template (copy-paste starter)

Save as `backend/.env` on the server (adjust secrets):

```bash
APP_ENV=prod
LOG_LEVEL=INFO

WA_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WEBHOOK_PUBLIC_URL=https://api.shopveluna.in/webhooks/twilio/whatsapp

DATABASE_URL=postgresql+psycopg://quotewise:CHANGE_ME@postgres:5432/quotewise
REDIS_URL=redis://redis:6379/0

LLM_PROVIDER=vertex
GCP_PROJECT_ID=your-gcp-project
GCP_LOCATION=asia-south1
GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-sa.json

PDF_STORAGE_DIR=data/pdfs
PDF_BASE_URL=https://api.shopveluna.in
QUOTE_VALIDITY_DAYS=30
SESSION_TTL_HOURS=72
```

After editing: `docker compose up -d --build backend celery-worker` and run migrations if needed.
