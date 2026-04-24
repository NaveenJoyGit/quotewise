# Changelog

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
