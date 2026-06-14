# Changelog

## FR-003 — Flexible Work Types (2026-06-13)

Goal: Overhaul QuoteWise to support dynamic, flexible work types (e.g. electrical, plumbing, carpentry) instead of hardcoded painting and false ceiling.

### What was done

- **DB Migration** — Replaced `WorkType` enum with generic `VARCHAR(64)` strings in `contractor_admin_sessions`, `pricing_configs`, `sessions`, and `quotes` tables. Removed `WorkType` enum class.
- **Pricing Evaluator & Schemas** — Refactored schemas to make it generic for any trade. `rate_per_sqft` has been renamed to `base_rate`, and `amount_per_sqft_per_extra_unit` to `amount_per_extra_unit`. `quantity_field` in `line_item_template` now correctly accepts generic units.
- **LLM Rate Card Ingest** — Rewrote `rate_card_ingest.jinja` prompt to be trade-agnostic and infer `quantity_field` and `base_formula` (e.g. `points * base_rate` vs `area_sqft * base_rate`) directly from the rate card. Removed painting-specific rules.
- **Contractor Handlers & Work Type Detection** — Replaced static `parse_work_type` with an automated slugifier (`text.strip().lower().replace(' ', '_')`). Added `electrical` and `plumbing` few-shot examples to `work_type_detection.jinja`.
- **Frontend** — Replaced hardcoded "painting" string initializers with empty strings and changed the `StepTwo` selection box to an `input` element to allow free-form trade names.
- **Tests** — Refactored all test suites to drop the `WorkType` enum reference and reflect the updated schema variables (`base_rate`, etc.).

---

## Twilio WhatsApp adapter (2026-05-25)

Goal: run the same QuoteWise flows (buyer, FR-001 admin, FR-002 forward) on **Twilio Programmable Messaging** instead of Meta Cloud API.

### What was done

- **`WA_PROVIDER`** — `meta` (default) or `twilio` selects inbound parser and outbound client.
- **Twilio webhook** — `POST /webhooks/twilio/whatsapp` (form POST, `X-Twilio-Signature`, empty TwiML ack).
- **Parsers** — `twilio_parser.py` maps `WaId`, `From`, `To`, `Forwarded`, `MediaUrl0` → `InboundMessage`.
- **Clients** — `TwilioWhatsAppClient` (Messages API); `WhatsAppClient` facade delegates by provider.
- **FR-002** — `Forwarded=true` on Twilio inbound (parity with Meta `context.forwarded`).
- **Simulator** — `scripts/simulate_conversation.py --provider twilio [--forwarded]`.
- **Tests** — `test_twilio_payload`, `test_twilio_auth`, `test_twilio_webhook`, `test_twilio_client`.

### Twilio setup (quick)

1. Set `WA_PROVIDER=twilio` and `TWILIO_*` in `backend/.env`.
2. Twilio Console → WhatsApp sender → **When a message comes in**: `https://<host>/webhooks/twilio/whatsapp`.
3. Seed contractor with `wa_phone_number_id` = your Twilio `To` number (E.164, e.g. `+14155238886`).
4. If using ngrok, set `TWILIO_WEBHOOK_PUBLIC_URL` to the exact public webhook URL.

---

## FR-002 — Contractor-forwarded buyer quotes (2026-05-25)

Goal: contractors forward buyer WhatsApp messages to the bot; QuoteWise runs a proxy quote conversation and auto-sends the PDF to the contractor (no approve step).

**Spec:** [`feature_requests/FR-002-contractor-forwarded-buyer-quotes.md`](feature_requests/FR-002-contractor-forwarded-buyer-quotes.md)

### What was done

- **Feature spec** — `feature_requests/FR-002-contractor-forwarded-buyer-quotes.md` (tight/loose, routing, synthetic `buyer_phone`, commit plan).

- **Forwarded payload detection** — `is_forwarded_message()`, `InboundMessage.is_forwarded`; `forwarded_text_message()` fixture and tests.

- **Migration 0005** — `SessionSource` enum (`buyer_direct`, `contractor_forward`); `Session.source`, optional `forward_metadata` JSONB.

- **`forwarded_quote` service** — `ForwardedQuoteEngine`, session repo (one active forward session per contractor), auto PDF delivery to contractor via `delivery.py`.

- **Proxy conversation mode** — `ConversationEngine` accepts pre-bound session; `HandlerDeps.proxy_mode`; `question_phrasing.jinja` contractor-facing branch; `ReadyToQuoteHandler` skips `awaiting_approval` for forward sessions.

- **Worker routing** — priority: admin → forward (active session or `context.forwarded`) → approve/reject (direct quotes only) → buyer direct → contractor help; `_handle_quote_ready` limited to `buyer_direct`.

- **FLOWS.md §3b** — documents contractor-forwarded buyer quote flow.

- **Tests** — `test_forward_payload`, `test_forwarded_quote_engine`, `test_forwarded_delivery`, `test_worker_task_forward`; updated M4 worker tests for new routing.

### Files added

```
feature_requests/FR-002-contractor-forwarded-buyer-quotes.md
backend/alembic/versions/0005_add_session_source.py
backend/app/services/forwarded_quote/
backend/tests/test_forward_payload.py
backend/tests/test_forwarded_quote_engine.py
backend/tests/test_forwarded_delivery.py
backend/tests/test_worker_task_forward.py
```

### Files edited

```
backend/app/db/enums.py
backend/app/db/models.py
backend/app/services/whatsapp/payload.py
backend/app/services/conversation/engine.py
backend/app/services/conversation/types.py
backend/app/services/conversation/session_repo.py
backend/app/services/conversation/handlers/
backend/app/services/conversation/question_phraser.py
backend/app/prompts/question_phrasing.jinja
backend/app/workers/tasks.py
backend/tests/sample_payloads.py
backend/tests/test_conversation_engine.py
backend/tests/test_handlers.py
backend/tests/test_worker_task_m4.py
FLOWS.md
CHANGELOG.md
```

### Deploy note

Run `alembic upgrade head` to apply migration `0005_add_session_source`.

---

## FR-001 — WhatsApp contractor onboarding (2026-05-25)

Goal: contractors can set up or update pricing via WhatsApp using prefixed messages and file uploads, reusing web onboarding persistence.

**Spec:** [`feature_requests/FR-001-whatsapp-contractor-onboarding.md`](feature_requests/FR-001-whatsapp-contractor-onboarding.md)

### What was done

- **Feature spec** — `feature_requests/FR-001-whatsapp-contractor-onboarding.md` (tight/loose sections, state machines, commit plan).

- **Phone normalization** (`app/services/whatsapp/phone.py`) — E.164 normalization and `find_contractor_by_phone()`; worker routing uses `phones_match()` instead of raw string equality.

- **WhatsApp media download** — `WhatsAppClient.download_media()`; `extract_document_info()` on inbound payloads; `document_message()` test fixture.

- **Migration 0004** — `contractor_admin_sessions` table with `admin_flow_type` and `admin_session_state` enums.

- **`ContractorAdminSession` ORM** — stores admin flow state, draft rules/profile, parse notes, validation errors.

- **`contractor_admin` service** — prefix parser (`manage-rates`, `onboard`), confirm keywords, session repo, rate summary formatter, state handlers, `ContractorAdminEngine`.

- **Phase 1 — `manage-rates`** — registered contractor updates pricing via chat; text or PDF/TXT/CSV upload; Gemini via `RateCardParser`; confirm with `yes`/`cancel`; persists via `OnboardingService.save_pricing_config()` with version bump; audit `pricing.updated`.

- **Phase 2 — `onboard`** — unregistered phone full signup (business name, city, slug, work type, rate card); `create_contractor` + pricing save; sends buyer link and API key once.

- **Worker routing** — priority: admin session/prefix → contractor approval → buyer conversation (`tasks.py`).

- **Prompt** — `onboarding_profile_extract.jinja` (optional profile paste extraction, Phase 2 ready).

- **FLOWS.md §2b** — documents WhatsApp contractor admin flow.

- **Tests** — `test_phone_normalize`, `test_wa_media_download`, `test_admin_prefix`, `test_contractor_admin_engine`, `test_worker_task_admin`; updated M3/M4 worker tests for new routing.

### Files added

```
feature_requests/FR-001-whatsapp-contractor-onboarding.md
backend/alembic/versions/0004_contractor_admin_sessions.py
backend/app/services/whatsapp/phone.py
backend/app/services/contractor_admin/
backend/app/prompts/onboarding_profile_extract.jinja
backend/tests/test_phone_normalize.py
backend/tests/test_wa_media_download.py
backend/tests/test_admin_prefix.py
backend/tests/test_contractor_admin_engine.py
backend/tests/test_worker_task_admin.py
```

### Files edited

```
backend/app/db/enums.py
backend/app/db/models.py
backend/app/services/whatsapp/client.py
backend/app/services/whatsapp/payload.py
backend/app/workers/tasks.py
backend/tests/sample_payloads.py
backend/tests/test_worker_task_m3.py
backend/tests/test_worker_task_m4.py
FLOWS.md
CHANGELOG.md
```

---

## Multitenancy — contractor API key auth (2026-05-15)

Goal: proper isolation between contractors so multiple contractors can coexist in the same deployment without data leakage.

**Problem:** through M5, `GET /api/v1/quotes` was hardcoded to the first contractor in the DB; `POST /api/v1/contractors/{id}/pricing/{work_type}` had no auth at all; and `resolve_contractor()` silently fell back to the first contractor when an unknown `wa_phone_number_id` arrived — a silent data-leak risk.

### What was done

- **SPEC.md §3.3 added** — tight section defining per-contractor API key auth: UUID v4, server-generated at signup, returned once in onboarding step 1, passed as `X-Contractor-Key` header on all dashboard API calls.

- **Migration 0003** (`alembic/versions/0003_add_contractor_api_key.py`) — adds `api_key UUID NOT NULL DEFAULT gen_random_uuid()` to `contractors` with a unique index. Existing rows get a value automatically via the server default.

- **`Contractor` ORM model** — `api_key: Mapped[uuid.UUID]` with `default=uuid.uuid4` (Python-side) and `server_default=gen_random_uuid()` (DB-side).

- **`app/api/deps.py`** (new) — shared FastAPI dependencies:
  - `get_db()` — yields a `SessionLocal` session; replaces the duplicated `get_db` that previously lived in both `quotes.py` and `onboarding.py`.
  - `get_current_contractor()` — reads `X-Contractor-Key` header, validates UUID format, looks up by `api_key`; 401 on missing, malformed, or unknown key.

- **`GET /api/v1/quotes`** — now uses `Depends(get_current_contractor)`; filters quotes by `contractor.id`. The old hardcoded `"first contractor in DB"` query (and its `# M4: single-tenant` comment) is gone.

- **`POST /api/v1/contractors/{id}/pricing/{work_type}`** — requires `X-Contractor-Key`; returns 403 if the URL `contractor_id` does not match the authenticated contractor.

- **`POST /api/v1/onboarding/contractors`** — now returns `api_key` in the response. This is the only time the key is revealed.

- **`resolve_contractor()` fix** (`session_repo.py`) — when `wa_phone_number_id` is provided but doesn't match any contractor, raises `ContractorNotFoundError` instead of silently routing to the first contractor. The fallback to first contractor is retained only when `wa_phone_number_id` is `None` (dev/mock mode).

- **Frontend — `/login` page** (`app/login/page.tsx`) — contractor enters their API key; client-side UUID validation; saved as `contractor_key` cookie (30-day expiry); redirects to `/quotes`.

- **Frontend — root redirect** (`app/page.tsx`) — reads `contractor_key` cookie; redirects to `/login` if absent, `/quotes` if present.

- **Frontend — `/quotes` page** — reads `contractor_key` cookie; redirects to `/login` if missing; passes key as `X-Contractor-Key` header in `fetchQuotes()`.

- **Frontend — onboarding step 3** (`StepThree.tsx`) — displays `api_key` in an amber "save this — shown once" box with a copy button; saves it to the `contractor_key` cookie on mount (auto-login after onboarding).

- **Frontend — onboarding step 2** (`StepTwo.tsx`) — accepts `apiKey` prop, forwards to `savePricingConfig()` as `X-Contractor-Key` header.

- **Tests** — 280 unit tests passing (was 272). Added `test_auth_deps.py` (8 tests covering missing/invalid/unknown key → 401, valid key → 200). Updated `test_quotes_api.py` (auth dep override; replaced `test_no_contractor_returns_empty` with `test_missing_auth_header_returns_401`). Updated `test_onboarding_api.py` (happy-path now properly checks `api_key` in response; `TestSavePricingConfig` adds 401/403 tests). Updated `test_session_repo_db.py` integration test to expect `ContractorNotFoundError` for unknown `wa_phone_number_id`.

### Files added

```
backend/alembic/versions/0003_add_contractor_api_key.py
backend/app/api/deps.py
backend/tests/test_auth_deps.py
frontend/app/login/page.tsx
```

### Files edited

```
SPEC.md                                              added §3.3, updated §9 and §10.5
backend/app/db/models.py                             Contractor.api_key field
backend/app/api/quotes.py                            uses get_current_contractor dep
backend/app/api/onboarding.py                        imports deps.get_db; api_key in response; 403 on mismatch
backend/app/services/conversation/session_repo.py    ContractorNotFoundError; no silent fallback
backend/tests/test_quotes_api.py                     auth dep override + 401 test
backend/tests/test_onboarding_api.py                 api_key in fake; 401/403 tests for save_pricing
backend/tests/test_session_repo_db.py                unknown wa_id now expects ContractorNotFoundError
frontend/lib/api.ts                                  fetchQuotes(apiKey) with X-Contractor-Key
frontend/lib/onboarding-api.ts                       ContractorResponse.api_key; savePricingConfig(apiKey)
frontend/app/page.tsx                                cookie-aware redirect
frontend/app/quotes/page.tsx                         cookie read + /login redirect + auth header
frontend/app/onboarding/page.tsx                     passes contractor.api_key to StepTwo
frontend/app/onboarding/components/StepTwo.tsx       apiKey prop
frontend/app/onboarding/components/StepThree.tsx     API key display + cookie set
```

### How to run locally

Unit tests (no external deps):
```
uv sync --extra dev
uv run pytest backend/tests -q -m "not integration" \
  --cov=app.services --cov=app.api --cov-report=term-missing
```

DB integration tests (requires Docker Desktop):
```
uv run pytest backend/tests/test_session_repo_db.py -v
```

Migrate existing DB:
```
uv run alembic -c backend/alembic.ini upgrade head
# Existing contractor rows get api_key auto-assigned via gen_random_uuid().
# Retrieve the dev contractor's key:
uv run python -c "
import sys; sys.path.insert(0, 'backend')
from app.db.base import SessionLocal
from app.db.models import Contractor
s = SessionLocal()
c = s.query(Contractor).first()
print('API key:', c.api_key)
"
```

Frontend:
```
cd frontend && npm run dev   # visit http://localhost:3000/login
```

---

## Milestone 5 — "Onboarding + rate card ingestion" (2026-04-27)

Goal (SPEC §10.5): contractor self-service onboarding, AI rate card ingestion, false ceiling work type, multi-contractor routing.

**Success criterion:** A new contractor can sign up, upload their rate card, and start receiving AI-handled enquiries without manual intervention.

### What was done

- **False ceiling work type** (`seed_rules.py`) — `FALSE_CEILING_RULES` added (3 ceiling types × 3 finishes = 9 rate rows, 18% GST). All M1–M4 code already supported any work type without changes. Seed script (`seed_data.py`) now upserts both painting and false ceiling configs for the dev contractor. 9 new parametrized evaluator tests cover every false ceiling rate row.

- **Work type detection (LLM)** — `IdentifyingScopeHandler` no longer hardcodes `WorkType.painting`. New `WorkTypeDetector` service + `work_type_detection.jinja` prompt classify buyer messages. Logic: single work type = no LLM call (zero regression risk); multiple = LLM; ambiguous = ask buyer, stay in `identifying_scope`. `HandlerDeps` extended with `available_work_types: list[WorkType]` (default `[]`, backward-compatible) and `pricing_rules_by_work_type: dict` so the handler can look up the detected type's rules without an extra DB round-trip. Engine loads all active configs per contractor in one query (`_load_available_work_types_and_rules`). `_load_pricing_rules` returns `{}` during `identifying_scope` (before work type is known) to avoid premature DB lookups.

- **Multi-contractor routing** (`wa_phone_number_id`) — Alembic migration 0002 adds `wa_phone_number_id VARCHAR(64)` + index to `contractors`. `Contractor` model updated. `parse_inbound()` now extracts `metadata.phone_number_id` from the Meta envelope and exposes it as `InboundMessage.phone_number_id`. `resolve_contractor(db, wa_phone_number_id=None)` looks up by this field first; falls back to first contractor (all unit tests still pass). Task layer passes `msg.phone_number_id` per-message (contractor resolved inside the loop).

- **LLM Pro client** — `VertexGeminiClient.__init__` gains explicit `model_name: str | None` parameter (default: Flash). Factory `get_llm_client(model="flash"|"pro")` selects Pro for rate card ingestion. Mock client is unchanged.

- **Rate card ingestion service** (`services/rate_card/`) — `extract_text()` supports PDF (via `pypdf`) and plain text/CSV. `RateCardParser(llm).parse()` calls Gemini Pro with `rate_card_ingest.jinja`, strips `_notes`, validates output with `PricingRules.model_validate()`, and always returns `ParsedRateCard` (never raises on validation failure — errors go into `validation_errors` list so the UI can show them for manual correction).

- **Prompt templates** — `rate_card_ingest.jinja` (full PricingRules schema embedded, one few-shot example, brand→tier mapping rules); `work_type_detection.jinja` (JSON-only, 6 few-shot examples, "unclear" fallback).

- **Onboarding service** (`services/onboarding/service.py`) — `create_contractor()` (409 on duplicate phone/slug); `save_pricing_config()` (deactivates existing, increments version).

- **Onboarding API** (`api/onboarding.py`) — `POST /api/v1/onboarding/contractors` (step 1); `POST /api/v1/onboarding/rate-card/parse` (step 2, multipart file upload → Gemini Pro → ParsedRulesResponse); `POST /api/v1/contractors/{id}/pricing/{work_type}` (step 3). Registered in `main.py`.

- **Frontend 3-step onboarding** (`frontend/app/onboarding/`) — Client-side Next.js 14 flow: StepOne (business profile form, auto-slug from name), StepTwo (file upload + AI parse + editable rate table), StepThree (summary + WhatsApp share link + copy button). `frontend/lib/onboarding-api.ts` API client. "+ Add Contractor" button added to `/quotes` page.

- **testcontainers DB integration tests** (`tests/test_session_repo_db.py`) — 8 tests covering `resolve_contractor` (by wa_phone_number_id, fallback, unknown id), `find_or_create_session` (new, existing, TTL-expired → new), `log_message`, `create_quote`, `apply_handler_result`. Marked `@pytest.mark.integration`, excluded from fast suite. Spins up `postgres:16-alpine` and runs `alembic upgrade head` before tests.

- **Dependencies added** — `pypdf>=4.0` (rate card PDF extraction), `python-multipart>=0.0.9` (FastAPI file upload), `testcontainers>=4.8` (dev, DB integration tests). `pytest.ini_options` gains `markers` declaration.

- **272 unit tests passing, 0 failures.** Pricing stays at 100% line coverage. All new services at 100% or close. Integration tests are separate (`-m integration`).

### Files added

```
backend/alembic/versions/0002_add_wa_phone_number_id.py
backend/app/prompts/rate_card_ingest.jinja
backend/app/prompts/work_type_detection.jinja
backend/app/services/rate_card/__init__.py
backend/app/services/rate_card/extractor.py
backend/app/services/rate_card/parser.py
backend/app/services/conversation/work_type_detector.py
backend/app/services/onboarding/__init__.py
backend/app/services/onboarding/service.py
backend/app/api/onboarding.py
backend/tests/test_rate_card_parser.py
backend/tests/test_work_type_detector.py
backend/tests/test_onboarding_api.py
backend/tests/test_session_repo_db.py         (integration, marked)
frontend/app/onboarding/page.tsx
frontend/app/onboarding/components/StepOne.tsx
frontend/app/onboarding/components/StepTwo.tsx
frontend/app/onboarding/components/StepThree.tsx
frontend/lib/onboarding-api.ts
```

### Files edited

```
backend/app/services/pricing/seed_rules.py
backend/app/services/conversation/types.py
backend/app/services/conversation/handlers/identifying_scope.py
backend/app/services/conversation/engine.py
backend/app/services/conversation/session_repo.py
backend/app/services/whatsapp/payload.py
backend/app/services/llm/vertex.py
backend/app/services/llm/factory.py
backend/app/db/models.py
backend/app/workers/tasks.py
backend/app/main.py
backend/app/quotes/page.tsx
backend/tests/test_handlers.py
backend/tests/test_pricing_evaluator.py
backend/tests/test_llm_factory.py
backend/tests/test_payload_parser.py
backend/tests/test_conversation_engine.py
scripts/seed_data.py
pyproject.toml
```

### How to run locally

Unit tests (no external deps — runs in < 1s):
```
uv sync --extra dev
uv run pytest backend/tests -q -m "not integration" \
  --cov=app.services --cov=app.api --cov-report=term-missing
```

DB integration tests (requires Docker Desktop):
```
uv run pytest backend/tests/test_session_repo_db.py -v
```

End-to-end with false ceiling (mock LLM):
```
docker compose up -d postgres redis
uv run alembic -c backend/alembic.ini upgrade head
uv run python scripts/seed_data.py
uv run uvicorn app.main:app --app-dir backend          # terminal 1
uv run celery -A app.workers.celery_app worker -l info --workdir backend  # terminal 2

# Painting (existing)
python scripts/simulate_conversation.py "hello"
python scripts/simulate_conversation.py "1000 sqft new wall, premium paint, 2 coats"

# False ceiling (new — work_type auto-detected if LLM_PROVIDER=vertex)
python scripts/simulate_conversation.py "hi, need false ceiling"
python scripts/simulate_conversation.py "gypsum board, 300 sqft, plain finish"
```

Onboarding flow:
```
# Onboarding API
curl -sX POST http://localhost:8000/api/v1/onboarding/contractors \
  -H "Content-Type: application/json" \
  -d '{"business_name":"Test Co","phone":"+919876543210","city":"Bangalore","whatsapp_link_slug":"testco"}' | python -m json.tool

# Frontend
cd frontend && npm install && npm run dev   # visit http://localhost:3000/onboarding
```

### What's next (M6 per SPEC §10.6)

- Rate staleness nudges
- Clarification loop handler (SPEC §5.2)
- Audit log dashboard
- Error handling for every edge case found with first real contractor
- Onboard 1 real interior contractor in Bangalore

---

## Milestone 4 — "Quote delivery" (2026-04-25)

Goal (SPEC §10.4): PDF generation, contractor approval via WhatsApp keyword match, approved PDF delivered to buyer, read-only Next.js contractor dashboard.

**Success criterion:** Complete flow — buyer messages → AI collects scope → contractor approves via WhatsApp → buyer receives PDF.

### What was done

- **State machine fixes** — `ReadyToQuoteHandler` now transitions to `AWAITING_APPROVAL` (was incorrectly staying in `READY_TO_QUOTE`). Two new handlers registered:
  - `AwaitingApprovalHandler` — buyer messages while contractor reviews get a holding reply; state unchanged.
  - `QuoteDeliveredHandler` — buyer messages after PDF is sent get a "check above" reply; state unchanged.

- **Engine transient attributes** (`engine.py`) — `ConversationEngine.process()` return type unchanged (`str | None`). Two new instance attrs set per call:
  - `pending_quote_snapshot: dict | None` — populated when a handler returns a quote snapshot.
  - `last_session: SessionModel | None` — populated after `find_or_create_session`. Task layer reads these to trigger quote persistence + contractor notification.

- **Quote persistence** (`session_repo.py`) — 4 new helpers: `load_active_pricing_config`, `create_quote`, `update_quote_pdf_url`, `find_pending_quote_for_contractor`. `create_quote` writes a `Quote` row at `status=pending_approval` immediately after the pricing evaluation, before notifying the contractor.

- **Approval keyword parser** (`services/approval/keywords.py`) — Pure `parse_approval_keyword()` with deterministic regex (SPEC §6.2 — never LLM). Approve patterns run before reject so "approve or cancel" → approve. Word boundaries prevent "cannot" matching "no".

- **ApprovalService** (`services/approval/service.py`) — Handles contractor's WhatsApp reply: keyword parse → find pending quote → approve (generate PDF + send_document to buyer + set `status=sent` + session → `QUOTE_DELIVERED`) or reject (send rejection to buyer + session → `CLOSED`). Logs `AuditLog` entries for both actions.

- **PDF service** (`services/pdf/service.py`) — `PdfService.generate(quote, contractor)` renders `quote_template.html` via Jinja2 then WeasyPrint (`HTML(string=…).write_pdf()`). Saves to `data/pdfs/quote_{id}.pdf`, returns public URL. Accepts injectable `_html_renderer` for tests (native WeasyPrint deps not required in unit tests). Buyer phone masked to last 4 digits in template (SPEC §9 PII).

- **WhatsApp `send_document`** (`services/whatsapp/client.py`) — Meta Graph API document message. Mock mode logs `[MOCK WA] send_document` and returns stub.

- **Task layer rewrite** (`workers/tasks.py`) — Contractor phone → `ApprovalService`; buyer phone → `ConversationEngine`. After engine returns, if `pending_quote_snapshot` is set, `_handle_quote_ready` persists the Quote, commits, then sends contractor notification via `send_text`. Per-message exceptions still caught and logged; DB always closed in `finally`.

- **Static file serving** (`main.py`) — `StaticFiles` mounted at `/pdfs`; directory auto-created on startup. Quotes API router registered at `/api/v1/quotes`.

- **Quotes API** (`api/quotes.py`) — `GET /api/v1/quotes` returns last 50 quotes for the active contractor, newest first. Optional `?status=` filter. `QuoteResponse` Pydantic model serialises all Quote fields.

- **Next.js contractor dashboard** (`frontend/`) — Next.js 14 App Router + Tailwind. Server component fetches quotes from `NEXT_PUBLIC_BACKEND_URL`. Quotes table with columns: Date, Buyer (masked), Work Type, Subtotal, GST, Total, Status (colour-coded badge), PDF link. Graceful error state when backend unreachable.

- **Config additions** — `PDF_STORAGE_DIR` (default `data/pdfs`), `PDF_BASE_URL` (default `http://localhost:8000`), `QUOTE_VALIDITY_DAYS` (default 30).

- **No new Alembic migration** — All schema fields (`pdf_url`, `approved_at`, `sent_at`, `awaiting_approval`/`quote_delivered` session states) already existed in the 0001 migration.

- **224 tests passing, 0 failures.** Pricing stays at 100% line coverage. New modules `approval/keywords.py`, `approval/service.py`, all handlers at 100%. Engine at 100%. `session_repo` intentionally low (DB-backed, no test-DB harness — consistent with M2/M3 approach).

### Files added

```
backend/app/services/approval/__init__.py
backend/app/services/approval/keywords.py
backend/app/services/approval/service.py

backend/app/services/pdf/__init__.py
backend/app/services/pdf/service.py
backend/app/services/pdf/quote_template.html

backend/app/services/conversation/handlers/awaiting_approval.py
backend/app/services/conversation/handlers/quote_delivered.py

backend/app/api/quotes.py

backend/tests/test_approval_keywords.py
backend/tests/test_approval_service.py
backend/tests/test_pdf_service.py
backend/tests/test_quotes_api.py
backend/tests/test_worker_task_m4.py

frontend/package.json
frontend/tsconfig.json
frontend/next.config.ts
frontend/tailwind.config.ts
frontend/postcss.config.js
frontend/app/globals.css
frontend/app/layout.tsx
frontend/app/page.tsx
frontend/app/quotes/page.tsx
frontend/lib/api.ts
```

### Files edited

- `backend/app/services/conversation/handlers/ready_to_quote.py` — `new_state` → `SessionState.awaiting_approval`
- `backend/app/services/conversation/handlers/__init__.py` — registered `AwaitingApprovalHandler`, `QuoteDeliveredHandler`
- `backend/app/services/conversation/engine.py` — added `pending_quote_snapshot`, `last_session` attrs
- `backend/app/services/conversation/session_repo.py` — added 4 new helpers
- `backend/app/services/whatsapp/client.py` — added `send_document()`
- `backend/app/core/config.py` — added PDF + quote validity settings
- `backend/app/workers/tasks.py` — **rewritten**: contractor routing + `_handle_quote_ready` + `_format_contractor_notification`
- `backend/app/main.py` — StaticFiles mount, quotes router
- `pyproject.toml` — added `weasyprint>=62`
- `.env.example` — added PDF config section
- `.gitignore` — added `data/pdfs/`
- `backend/tests/test_handlers.py` — updated `ReadyToQuoteHandler` assertion; added `AwaitingApprovalHandler` + `QuoteDeliveredHandler` tests
- `backend/tests/test_conversation_engine.py` — updated unknown-state test; added `pending_quote_snapshot` test
- `CHANGELOG.md` — this entry

### How to run locally

Unit tests (no external deps — runs in < 1s):
```
uv sync --extra dev
uv run pytest backend/tests -q --cov=app.services --cov=app.api --cov-report=term-missing
```

End-to-end with mock LLM (no Vertex or Meta creds needed):
```
docker compose up -d postgres redis
uv run alembic -c backend/alembic.ini upgrade head
uv run python scripts/seed_data.py
uv run uvicorn app.main:app --app-dir backend          # terminal 1
uv run celery -A app.workers.celery_app worker -l info --workdir backend  # terminal 2

# Buyer conversation
python scripts/simulate_conversation.py "hello"
python scripts/simulate_conversation.py "1000 sqft new wall, premium paint, 2 coats"
# Worker log shows event_type=quote.generated + contractor notification text

# Contractor approves (seed contractor phone = 919999900001)
python scripts/simulate_conversation.py --from 919999900001 "approve"
# Worker log shows quote.approved, pdf.generated, send_document to buyer

# Check quotes API
curl http://localhost:8000/api/v1/quotes | python -m json.tool
```

Dashboard (read-only quote history):
```
cd frontend && npm install && npm run dev   # visit http://localhost:3000/quotes
```

### What's next (M5 per SPEC §10.5)

- Web onboarding page (3-step contractor signup)
- File upload + Gemini Pro parsing of rate cards into PricingConfig
- Preview UI for contractor to correct parsed schema
- False ceiling work type (proves data-driven extensibility — all M4 code already supports it)
- `testcontainers`-backed DB tests for `session_repo`

---

## Milestone 3 — "First AI conversation" (2026-04-24)

Goal (SPEC §10.3): LLM slot extraction, next-question phrasing, state machine `GREETING → IDENTIFYING_SCOPE → COLLECTING_INPUTS → READY_TO_QUOTE`. Work type hardcoded to painting. On `READY_TO_QUOTE`: quote computed and logged as JSON. No PDF (M4).

### What was done

- **Prompt layer** (`backend/app/prompts/`) — Jinja2 loader (`StrictUndefined`, `trim_blocks`) + 3 prompt templates:
  - `slot_extraction.jinja` — SPEC §4.3 Pattern 1: JSON-only output, explicit schema for missing slots, 2–3 few-shot examples, untrusted-input delimiters (SPEC §9).
  - `question_phrasing.jinja` — one-question guardrail; passes `slot_def.question_template` as a phrasing baseline.
  - `greeting.jinja` — short greeting + scope opener; no price mentions.

- **LLM abstraction** (`backend/app/services/llm/`) — SPEC §4.4 "abstract all LLM calls behind a single `LLMClient` interface":
  - `base.py` — `LLMClient(ABC)` with `extract_json` / `generate_text`. Every call logs `event_type=llm.call`, template name, model, input/output tokens, latency (SPEC §8.3).
  - `mock.py` — `MockLLMClient`: canned dict/str/callable responses keyed by template name. Still renders the Jinja template (template errors surface in tests). Mirrors the `WhatsAppClient` mock-or-real pattern from M1.
  - `vertex.py` — `VertexGeminiClient`: lazy-imports `vertexai` (tests don't need the SDK). Uses `response_mime_type="application/json"` for structured extraction. Splits templates on `{# SYSTEM #}/{# USER #}` markers for Gemini's `system_instruction` (SPEC §9 role separation).
  - `factory.py` — returns `VertexGeminiClient` when `LLM_PROVIDER=vertex` + `GCP_PROJECT_ID` set; otherwise `MockLLMClient` (with a warning log if vertex was requested but creds absent).

- **State machine** (`backend/app/services/conversation/`) — SPEC §5.2 strategy pattern:
  - `handlers/__init__.py` — `StateHandler(ABC)`, `HANDLERS` registry, `get_handler()`. Deferred states raise `UnknownStateError` → engine sends stub reply.
  - `handlers/greeting.py` — LLM-generated greeting → `IDENTIFYING_SCOPE`.
  - `handlers/identifying_scope.py` — hardcodes `WorkType.painting`; derives `missing_slots` from `PricingRules.inputs` (required + no default); phrases first question via `QuestionPhraser`.
  - `handlers/collecting_inputs.py` — runs `SlotExtractor`; if all slots filled returns empty `outbound_text` to trigger chained dispatch; otherwise phrases next question.
  - `handlers/ready_to_quote.py` — calls `evaluate_quote`, logs `event_type=quote.generated` (SPEC §10.3 success criterion), returns buyer ack.

- **Support services**:
  - `slot_extractor.py` — `SlotExtractor`: LLM → validated dict. Coerces numeric strings; validates with `validate_slot_value` (reuses pricing code); drops invalid values with `slot.extraction.invalid` log.
  - `question_phraser.py` — `QuestionPhraser`: falls back to `slot_def.question_template` on empty/error LLM response (a turn never fails due to phrasing hiccup).
  - `session_repo.py` — DB helpers: `resolve_contractor` (first contractor — M5 debt), `find_or_create_session` (72h TTL), `load_active_pricing_rules`, `log_message`, `apply_handler_result`.

- **`ConversationEngine`** (`engine.py`) — orchestrator: non-text → polite refusal; resolve contractor + session; log inbound `Message`; dispatch to handler; apply result; chained re-dispatch (max 2 iterations) when `outbound_text == ""`; log outbound `Message`; `db.commit()`.

- **Worker rewrite** (`backend/app/workers/tasks.py`) — replaces M1 echo stub. Opens `SessionLocal`, creates `ConversationEngine + WhatsAppClient`, routes each inbound message through `engine.process()`. Catches per-message exceptions so one bad message doesn't abort the batch. DB always closed in `finally`.

- **`_validate` → `validate_slot_value`** in `pricing/evaluator.py` — made public so `SlotExtractor` can reuse it without duplicating validation logic (SPEC §8.1 DRY).

- **Config additions** (`app/core/config.py` + `.env.example`) — `LLM_PROVIDER`, `GCP_PROJECT_ID`, `GCP_LOCATION`, `VERTEX_MODEL_FLASH`, `VERTEX_MODEL_PRO`, `LLM_CALL_TIMEOUT_SECONDS`, `SESSION_TTL_HOURS`.

- **143 tests passing, 0 failures.** Pricing stays at 100% line coverage. `slot_extractor`, `engine`, all handlers, `llm/base`, `llm/mock` at 100%. `session_repo` intentionally low (DB-backed; no test-DB harness — consistent with M2 approach; deferred to M4 with `testcontainers`). `vertex.py` 0% per-commit (integration-only; `@pytest.mark.integration` suite runs against real Vertex nightly). Retired `test_worker_echo.py` (M1 echo contract superseded).

### Files added

```
backend/app/prompts/__init__.py
backend/app/prompts/loader.py
backend/app/prompts/greeting.jinja
backend/app/prompts/question_phrasing.jinja
backend/app/prompts/slot_extraction.jinja

backend/app/services/llm/__init__.py
backend/app/services/llm/base.py
backend/app/services/llm/mock.py
backend/app/services/llm/vertex.py
backend/app/services/llm/factory.py

backend/app/services/conversation/__init__.py
backend/app/services/conversation/types.py
backend/app/services/conversation/engine.py
backend/app/services/conversation/slot_extractor.py
backend/app/services/conversation/question_phraser.py
backend/app/services/conversation/session_repo.py
backend/app/services/conversation/handlers/__init__.py
backend/app/services/conversation/handlers/greeting.py
backend/app/services/conversation/handlers/identifying_scope.py
backend/app/services/conversation/handlers/collecting_inputs.py
backend/app/services/conversation/handlers/ready_to_quote.py

backend/tests/test_prompt_loader.py
backend/tests/test_llm_mock.py
backend/tests/test_llm_factory.py
backend/tests/test_slot_extractor.py
backend/tests/test_question_phraser.py
backend/tests/test_handlers.py
backend/tests/test_conversation_engine.py
backend/tests/test_worker_task_m3.py
```

### Files edited

- `pyproject.toml` — added `jinja2>=3.1`, `google-cloud-aiplatform>=1.70`
- `backend/app/core/config.py` — added 7 LLM + session config fields + `llm_vertex_enabled` property
- `.env.example` — added LLM and session TTL section
- `backend/tests/conftest.py` — added `LLM_PROVIDER=mock` default
- `backend/app/workers/tasks.py` — **rewritten**: M1 echo → M3 conversation engine
- `backend/app/services/pricing/evaluator.py` — `_validate` renamed to `validate_slot_value` (public)
- `backend/tests/test_pricing_evaluator.py` — added 4 `validate_slot_value` tests; pricing coverage stays 100%
- `CHANGELOG.md` — this entry

### Files deleted

- `backend/tests/test_worker_echo.py` — M1 echo contract retired (replaced by `test_worker_task_m3.py`)

### How to run locally

Unit tests (no external deps — runs in < 1s):
```
uv sync --extra dev
uv run pytest backend/tests -q --cov=app.services --cov-report=term-missing
```

End-to-end with mock LLM (no Vertex creds needed):
```
docker compose up -d postgres redis
uv run alembic -c backend/alembic.ini upgrade head
uv run python scripts/seed_data.py
uv run uvicorn app.main:app --app-dir backend          # terminal 1
uv run celery -A app.workers.celery_app worker -l info --workdir backend  # terminal 2

python scripts/simulate_conversation.py "hello"
python scripts/simulate_conversation.py "1000 sqft new wall, premium, 2 coats"
```
Worker log should contain `event_type=quote.generated` with `subtotal=22000.00, gst_amount=3960.00, total=25960.00`.

End-to-end with real Vertex AI:
```
export LLM_PROVIDER=vertex GCP_PROJECT_ID=<your-project>
gcloud auth application-default login
# restart worker — natural language now flows through Gemini Flash
```

### What's next (M4 per SPEC §10.4)

- PDF generation from quote data
- Contractor approval via WhatsApp ("approve"/"reject" keyword match, SPEC §6.2)
- Approved quote PDF delivered to buyer
- Basic Next.js contractor dashboard (read-only quote history)

---

## Milestone 2 — "Seed data & schema" (2026-04-23)

Goal (SPEC §10.2): persistence layer + deterministic pricing core. No LLM. Success criterion: a unit test that starts with `{area_sqft: 1000, surface_type: "new_wall", ...}` and outputs the correct quote total.

### What was done

- **Full database schema (SPEC §3.1)** — SQLAlchemy 2.0 models for all six entities:
  - `Contractor`, `PricingConfig` (with JSONB `rules` + partial unique index on active config per `(contractor_id, work_type)`), `Session`, `Message`, `Quote`, `AuditLog`
  - Enums: `WorkType`, `ApprovalMode`, `SessionState`, `MessageDirection`, `MessageType`, `QuoteStatus` — created as native Postgres enum types
  - All tables: `id UUID PK`, `created_at`/`updated_at` with `server_default=now()` + `onupdate`, money as `Numeric(12,2)`
- **Alembic setup** — `backend/alembic.ini` (uses `%(here)s` so it runs from any CWD) + hand-written initial migration `0001_initial_schema.py` covering all six tables + enums. Offline SQL (`alembic upgrade head --sql`) verified clean.
- **Deterministic pricing evaluator (SPEC §2.2, §4.2 — "never ask an LLM to multiply two numbers")**
  - `app.services.pricing.evaluator.evaluate_quote(rules, slots) -> EvaluatedQuote` — pure function, no I/O
  - `app.services.pricing.schemas` — pydantic validation of `PricingConfig.rules` (structured modifier grammar: `per_unit_surcharge` + `tax`, discriminated union)
  - `app.services.pricing.expr` — tiny safe AST evaluator (Name / BinOp `+ - * /` / unary minus / numeric literals only; everything else — calls, attrs, subscripts, `%`, `**` — raises). Honors SPEC §9 prompt-injection-style concerns for any future LLM-supplied expressions.
  - `app.services.pricing.errors` — typed `MissingSlotError`, `InvalidSlotValueError`, `RateNotFoundError`
  - All amounts use `Decimal` + `ROUND_HALF_UP` quantized to 2 dp.
- **Hand-written painting rules** (`seed_rules.PAINTING_RULES`) — 3 paint tiers × 3 surface types = 9 rate rows, extra-coat surcharge, 18% GST, 1 line-item template. Doubles as seed payload and test fixture.
- **Seed script** (`scripts/seed_data.py`) — idempotent: upserts one dev contractor (`+919999900001` / "QuoteWise Dev Contractor" / slug `dev`) and one active painting `PricingConfig`.
- **63 new pricing tests; 100% coverage** of `app/services/pricing/*.py` enforced via `pytest-cov --cov-fail-under=100`. All 16 Milestone 1 tests remain green.
  - SPEC §10.2 success-criterion test (1000 sqft basic new_wall → subtotal ₹14 000, GST ₹2 520, total ₹16 520)
  - Every rate-table row exercised via parametrized test
  - Extra-coat surcharge (1 extra, 2 extra, default applied when `coats` omitted)
  - Every `ModifierCondition` operator (`gt/gte/lt/lte/eq`) — both triggered and not-triggered paths
  - All error paths: missing required, enum out of options, number below/above min/max, wrong type (bool/str for number, bool/float for integer), wrong type for string, rate not found
  - `safe_eval` allowed ops (`+ - * / unary-minus`), rejected ops (`% ** call attr subscript`), unknown names, non-numeric names, bool constants
  - Schema validation: empty rate table, missing base_formula, enum input without options, unknown modifier type, unknown top-level key
- **Infra** — Postgres 16-alpine added to `docker-compose.yml` (named volume `quotewise_pg_data`, healthcheck). `DATABASE_URL` added to `Settings` and `.env.example`.

### Files added

```
backend/alembic.ini
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/0001_initial_schema.py

backend/app/db/__init__.py
backend/app/db/base.py                          # Base + engine + SessionLocal
backend/app/db/enums.py                         # 6 enums
backend/app/db/models.py                        # 6 ORM models

backend/app/services/pricing/__init__.py
backend/app/services/pricing/errors.py
backend/app/services/pricing/evaluator.py       # pure evaluate_quote()
backend/app/services/pricing/expr.py            # safe AST expression evaluator
backend/app/services/pricing/schemas.py         # pydantic rules schema
backend/app/services/pricing/seed_rules.py      # PAINTING_RULES dict

scripts/seed_data.py                            # idempotent dev seed

backend/tests/test_pricing_evaluator.py
backend/tests/test_pricing_expr.py
backend/tests/test_pricing_schemas.py
```

### Files edited

- `pyproject.toml` — added `sqlalchemy>=2.0`, `alembic>=1.13`, `psycopg[binary]>=3.2`, and dev dep `pytest-cov>=5.0`
- `docker-compose.yml` — added `postgres:16-alpine` service with named volume + healthcheck
- `backend/app/core/config.py` — added `database_url` setting
- `.env.example` — added `DATABASE_URL`

### How to run locally

Unit tests (no external deps):
```
uv sync --extra dev
uv run pytest -q --cov=app.services.pricing --cov-report=term-missing --cov-fail-under=100
```

Database round-trip (requires Docker Desktop running):
```
docker compose up -d postgres
uv run alembic -c backend/alembic.ini upgrade head
uv run python scripts/seed_data.py
uv run python -c "import sys; sys.path.insert(0, 'backend'); from app.db.base import SessionLocal; from app.db.models import Contractor, PricingConfig; s = SessionLocal(); print(s.query(Contractor).one().business_name); print(s.query(PricingConfig).one().rules['base_formula'])"
```
Expected: `QuoteWise Dev Contractor` and `area_sqft * rate_per_sqft`.

### Blocked / follow-ups

- **DB round-trip not executed at build time** — Docker Desktop was not running on the dev machine. Migration SQL was verified via `alembic upgrade head --sql`; user should run the round-trip above once Docker is up.
- **M2 does not wire pricing into the webhook path.** `app/workers/tasks.py` still does the M1 echo. That integration lands in M3.

### What's left (next milestones per SPEC §10)

- **M3 — First AI conversation:** Slot extraction (Gemini Flash), question phrasing, state machine `GREETING → IDENTIFYING_SCOPE → COLLECTING_INPUTS → READY_TO_QUOTE`. Prompt templates under `backend/app/prompts/` per CLAUDE.md. Log every LLM call with template name, token count, latency.
- **M4 — Quote delivery:** PDF generation, contractor approval via WhatsApp (deterministic keyword match, SPEC §6.2), basic Next.js dashboard.
- **M5 — Onboarding + rate card ingestion:** Web onboarding, Gemini Pro rate card parsing, `false_ceiling` work type (proves data-driven extensibility).
- **M6 — Polish + first real contractor.**

---

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

See the M2 entry above for the current next-milestone list.
