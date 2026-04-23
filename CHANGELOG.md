# Changelog

## Milestone 1 — "Hello from WhatsApp" (2026-04-23)

Goal (SPEC §10.1): messages flow end-to-end through webhook → queue → worker → WhatsApp sender, no LLM, no pricing. Just plumbing.

### What was done

- **FastAPI webhook** at `/webhooks/whatsapp`
  - `GET` — Meta verification handshake (returns `hub.challenge` on correct token)
  - `POST` — HMAC-SHA256 verifies `X-Hub-Signature-256` against `WA_APP_SECRET`, enqueues Celery task, returns 200 immediately (SPEC §2.2: "synchronous webhook is forbidden")
- **Celery worker** with `process_inbound_message` task that echoes `"Got it: <text>"` for text messages and `"Got it: [<type>]"` for voice/image/document
- **WhatsApp client** (`app/services/whatsapp/client.py`) with two modes:
  - Mock mode when `WA_ACCESS_TOKEN` is empty — logs would-be outbound, no network
  - Live mode — POSTs to `graph.facebook.com/v21.0/{phone_number_id}/messages`
- **Meta payload parser** (`app/services/whatsapp/payload.py`) — normalizes `entry[].changes[].value.messages[]` into `InboundMessage` objects; returns empty list for status-only callbacks
- **Core infra**
  - `app/core/config.py` — pydantic-settings loading all WA + Redis vars from `.env`
  - `app/core/logging.py` — JSON structured logs with `contractor_id`/`session_id`/`event_type` fields per SPEC §8.3
- **Local simulator** (`scripts/simulate_conversation.py`) — posts Meta-shaped payloads to the running webhook for E2E testing without Meta creds (SPEC §12.9)
- **Tooling** — `uv` project (`package = false`), Python 3.11+ required, `docker-compose.yml` for local Redis
- **16 tests passing in 0.03s**, no warnings. Coverage includes:
  - Verification handshake (valid token / bad token / wrong mode)
  - HMAC signature (valid / invalid / missing)
  - Webhook does not call WhatsApp API in request thread (SPEC §2.2)
  - Payload parser (text, status-only, empty, non-text type mapping)
  - Worker echo (text, status-only skipped, non-text type-tagged)
  - WhatsApp client (mock vs Graph API POST shape)

### Files added

```
.env.example                                      env var reference
.gitignore
CHANGELOG.md                                      this file
CLAUDE.md                                         (existing) project instructions
PROMPTS.md                                        (existing) prompt template reference
SPEC.md                                           (existing) binding tech spec
docker-compose.yml                                local Redis
pyproject.toml                                    uv project, py>=3.11
uv.lock                                           locked deps

backend/app/__init__.py
backend/app/main.py                               FastAPI entry + /healthz
backend/app/api/__init__.py
backend/app/api/whatsapp_webhook.py               GET verify, POST enqueue
backend/app/core/__init__.py
backend/app/core/config.py                        pydantic-settings
backend/app/core/logging.py                       JSON structured logs
backend/app/services/__init__.py
backend/app/services/whatsapp/__init__.py
backend/app/services/whatsapp/client.py           mock-or-Graph-API sender
backend/app/services/whatsapp/payload.py          Meta envelope parser
backend/app/workers/__init__.py
backend/app/workers/celery_app.py                 Celery bootstrap
backend/app/workers/tasks.py                      process_inbound_message

backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/sample_payloads.py
backend/tests/test_payload_parser.py
backend/tests/test_webhook_signature.py
backend/tests/test_webhook_verification.py
backend/tests/test_whatsapp_client.py
backend/tests/test_worker_echo.py

scripts/simulate_conversation.py                  local E2E simulator
```

### How to run locally

```
docker compose up -d redis
uv run uvicorn app.main:app --reload --app-dir backend
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=info --workdir backend
uv run python scripts/simulate_conversation.py "hello bot"
```
Worker log shows: `[MOCK WA] to=919876543210 body=Got it: hello bot`

### Blocked / follow-ups

- **Meta WhatsApp Cloud API verification** — SPEC §11 flags this as multi-week. Code runs in mock mode until `WA_ACCESS_TOKEN` and `WA_PHONE_NUMBER_ID` are set.
- **Public tunnel for Meta** — when creds arrive, need ngrok or deploy so Meta can hit the webhook. Not in M1 scope.

### What's left (next milestones per SPEC §10)

- **M2 — Seed data & schema:** Postgres schema for all entities in SPEC §3.1, seed one contractor, hand-write a painting `PricingConfig`, implement formula evaluator with 100% test coverage (§8.2). No LLM yet.
- **M3 — First AI conversation:** Slot extraction (Gemini Flash), question phrasing, state machine `GREETING → IDENTIFYING_SCOPE → COLLECTING_INPUTS → READY_TO_QUOTE`. Prompt templates under `backend/app/prompts/` per CLAUDE.md. Log every LLM call with template name, token count, latency.
- **M4 — Quote delivery:** PDF generation, contractor approval via WhatsApp (deterministic keyword match, SPEC §6.2), basic Next.js dashboard.
- **M5 — Onboarding + rate card ingestion:** Web onboarding, Gemini Pro rate card parsing, false ceiling work type.
- **M6 — Polish + first real contractor.**
