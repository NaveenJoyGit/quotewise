# QuoteWise — Flows & Architecture

A reference document covering every flow in the system: how data moves, who does what, and which code handles each step.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Contractor Onboarding Flow](#2-contractor-onboarding-flow)
3. [Buyer Conversation Flow](#3-buyer-conversation-flow)
4. [Contractor Approval Flow](#4-contractor-approval-flow)
5. [Quote Dashboard Flow](#5-quote-dashboard-flow)
6. [Demo / Web UI Flow](#6-demo--web-ui-flow)
7. [Architecture](#7-architecture)
8. [Database Schema Summary](#8-database-schema-summary)
9. [State Machine Reference](#9-state-machine-reference)

---

## 1. System Overview

QuoteWise lets interior contractors in India receive and respond to quote requests over WhatsApp — entirely handled by AI, without the contractor needing to be online.

**Three actors:**

| Actor | What they do |
|---|---|
| **Contractor** | Signs up once, uploads their rate card, approves/rejects quotes via WhatsApp reply |
| **Buyer** | Taps a WhatsApp link, chats with the AI, receives a PDF quote |
| **Operator (you)** | Manages the platform, monitors via the dashboard |

**High-level flow:**

```
Buyer taps WA link → AI collects details → AI prices the job
    → Contractor approves → Buyer receives PDF quote
```

---

## 2. Contractor Onboarding Flow

Done once per contractor via the web UI at `/onboarding`.

### Step 1 — Business Profile

The contractor fills in their name, phone number (E.164 format, e.g. `+919876543210`), city, and a unique URL slug.

**What happens:**
- `POST /api/v1/onboarding/contractors`
- `OnboardingService.create_contractor()` writes a `Contractor` row to the DB
- A UUID v4 `api_key` is generated server-side and returned **once** — the contractor must save it
- The frontend sets a `contractor_key` cookie in the browser automatically (30-day expiry) so the dashboard works immediately

**Key code:** `backend/app/api/onboarding.py` → `create_contractor()`

---

### Step 2 — Rate Card Upload

The contractor uploads their pricing as a PDF, TXT, or CSV file.

**What happens:**
- `POST /api/v1/onboarding/rate-card/parse`
- The file is read into text (PDF via `pdfminer`, plain text otherwise)
- **Gemini Pro** is called with the `rate_card_ingest.jinja` prompt to extract a structured rate table
- The result is shown in an editable table in the browser — the contractor can correct any parsing mistakes
- `POST /api/v1/contractors/{id}/pricing/{work_type}` saves the final rules as a `PricingConfig` row
- Requires `X-Contractor-Key` header (auth enforced)

**Key code:** `backend/app/services/rate_card/parser.py`, `backend/app/api/onboarding.py` → `save_pricing_config()`

---

### Step 3 — Go Live

The contractor is shown:
- Their **buyer WhatsApp link** — `https://wa.me/<BOT_NUMBER>?text=quote-<slug>`  
  Buyers tap this link and the AI conversation starts automatically
- Their **API key** (shown once, copy it somewhere safe)

At this point the contractor is live. Any buyer who taps the link will be routed to their AI assistant.

---

### 2b — WhatsApp contractor admin (FR-001)

Contractors can also set up or update pricing over WhatsApp using prefixed messages.

| Prefix | Who | Purpose |
|--------|-----|---------|
| `manage-rates` | Registered contractor phone | Update pricing for a work type |
| `onboard` | Unregistered phone | Full signup (profile + pricing) |

**Phase 1 — manage-rates (existing contractors):**

1. Contractor sends `manage-rates` from their registered WhatsApp number
2. Bot asks for work type (`painting` or `false_ceiling`)
3. Contractor sends rate card as text or uploads PDF/TXT/CSV
4. **Gemini Pro** parses via `rate_card_ingest.jinja`; bot shows rate table summary
5. Contractor replies `yes` to save or `cancel` to abort
6. `OnboardingService.save_pricing_config()` creates a new versioned `PricingConfig`

**Phase 2 — onboard (new contractors):**

1. Unregistered phone sends `onboard`
2. Bot collects business name, city, slug, work type, rate card (conversational)
3. On confirm: `create_contractor()` + `save_pricing_config()`
4. Bot sends buyer link and API key (shown once)

**Routing priority:** active admin session → admin prefix → contractor approval → buyer quote flow.

**Key code:** `backend/app/services/contractor_admin/`, `backend/app/workers/tasks.py`

---

## 3. Buyer Conversation Flow

This is the core AI-driven flow. It runs entirely over WhatsApp.

### Entry point

The buyer taps `https://wa.me/<BOT_NUMBER>?text=quote-<slug>`. WhatsApp opens and pre-fills the message with `quote-<slug>`. The buyer sends it.

### Message path (production)

```
Buyer sends WA message
  → Meta WebhookPOST /webhook/whatsapp
  → HMAC signature verified
  → Celery task queued: process_inbound_message
  → ConversationEngine.process(inbound)
  → AI reply sent back via WhatsApp Cloud API
```

**Key code:** `backend/app/api/whatsapp_webhook.py`, `backend/app/workers/tasks.py`, `backend/app/services/conversation/engine.py`

---

### 3b — Contractor-forwarded buyer quotes (FR-002)

Contractors forward buyer messages from their personal WhatsApp to the QuoteWise bot.

| Step | What happens |
|------|----------------|
| 1 | Contractor forwards a buyer text message to the bot (`context.forwarded` in webhook) |
| 2 | `ForwardedQuoteEngine` creates a `contractor_forward` session (`buyer_phone` = `fwd:<session_id>`) |
| 3 | `ConversationEngine` runs in **proxy mode** — follow-up questions go to the **contractor** |
| 4 | When slots are complete, pricing runs and PDF is **auto-sent to the contractor** (no approve step) |

**Routing:** admin (FR-001) → active forward session / new forward → approve (direct quotes only) → buyer direct.

**Key code:** `backend/app/services/forwarded_quote/`, [`feature_requests/FR-002-contractor-forwarded-buyer-quotes.md`](feature_requests/FR-002-contractor-forwarded-buyer-quotes.md)

---

### State machine

Each buyer has a **Session** that moves through states. The engine runs one handler per message and advances the state.

```
GREETING → IDENTIFYING_SCOPE → COLLECTING_INPUTS → READY_TO_QUOTE → AWAITING_APPROVAL → QUOTE_DELIVERED
```

| State | Handler | What happens |
|---|---|---|
| `greeting` | `GreetingHandler` | AI sends a welcome message using the `greeting.jinja` prompt. Session advances to `identifying_scope`. |
| `identifying_scope` | `IdentifyingScopeHandler` | AI detects the type of work (painting, false ceiling, etc.) using `work_type_detection.jinja`. Sets `work_type` on the session. |
| `collecting_inputs` | `CollectingInputsHandler` | AI uses `slot_extraction.jinja` to extract required values (area, finish, number of coats, etc.) from buyer messages. Asks follow-up questions via `question_phrasing.jinja` until all slots are filled. |
| `ready_to_quote` | `ReadyToQuoteHandler` | Deterministic pricing evaluator runs against collected slots and pricing rules. Produces a quote snapshot (line items, subtotal, GST, total). Buyer is told "your contractor will confirm shortly." |
| `awaiting_approval` | `AwaitingApprovalHandler` | Session is locked waiting for the contractor's decision. Buyer messages in this state get a "quote is being reviewed" reply. |
| `quote_delivered` | `QuoteDeliveredHandler` | Terminal state. Quote has been sent to the buyer. |
| `closed` | — | Terminal state. Quote was rejected or session expired. |

---

### LLM calls in the conversation

| Prompt template | Used by | Purpose |
|---|---|---|
| `greeting.jinja` | `GreetingHandler` | Friendly opening message personalised with business name |
| `work_type_detection.jinja` | `IdentifyingScopeHandler` | Classify the buyer's work type from free text |
| `slot_extraction.jinja` | `CollectingInputsHandler` | Extract structured values (area, finish, rooms) from a message |
| `question_phrasing.jinja` | `CollectingInputsHandler` | Phrase the next clarifying question naturally |
| `rate_card_ingest.jinja` | `RateCardParser` (onboarding only) | Parse an uploaded rate card file into a structured rate table |

All LLM calls use **Gemini Flash** except rate card parsing which uses **Gemini Pro** (runs once at setup, accuracy matters more than speed).

---

### Pricing evaluation

Once all slots are collected, pricing is **deterministic** — no AI involved. The evaluator (`backend/app/services/pricing/evaluator.py`) applies the contractor's rate table rules to the collected slots and returns:

- Line items (each pricing rule that matched)
- Subtotal
- GST amount (18%)
- Total
- Confidence score

---

### Quote persistence

After `ReadyToQuoteHandler` returns a quote snapshot, the Celery task layer (`_handle_quote_ready` in `tasks.py`) persists a `Quote` row to the database with status `pending_approval` and notifies the contractor via WhatsApp.

---

## 4. Contractor Approval Flow

After a quote is generated, the contractor receives a WhatsApp message:

```
New quote ready for your approval.

Buyer: +XX XXXXXX1234
Work: painting
Total: Rs. 18,400

Reply "approve" to send to buyer or "reject" to decline.
```

### Approve

The contractor replies `approve` (or `approved`, `yes`, `ok`).

**What happens:**
- `ApprovalService.process()` matches the keyword deterministically (no LLM)
- PDF is generated via WeasyPrint from `quote_template.html`
- PDF is saved to `data/pdfs/quote_<id>.pdf`
- PDF is served at `http://localhost:8000/pdfs/quote_<id>.pdf`
- PDF URL is sent to the buyer via WhatsApp document message
- `Quote.status` → `approved` → `sent`
- Session state → `quote_delivered`

**Key code:** `backend/app/services/approval/service.py`, `backend/app/services/pdf/service.py`

### Reject

The contractor replies `reject` (or `rejected`, `no`, `decline`).

**What happens:**
- Buyer receives: "The contractor is unable to provide a quote at this time."
- `Quote.status` → `rejected`
- Session state → `closed`

---

## 5. Quote Dashboard Flow

The contractor can view all their quotes at `/quotes`.

### Authentication

The dashboard requires a contractor API key. On first visit the browser redirects to `/login`. The contractor pastes their UUID key and clicks Sign in — this sets a `contractor_key` cookie (30 days, SameSite=Strict).

After onboarding the cookie is set automatically, so the contractor goes straight to the dashboard.

### What's shown

`GET /api/v1/quotes` (authenticated via `X-Contractor-Key` header) returns:

- Date and time
- Buyer phone (masked — only last 4 digits shown, e.g. `+XX XXXXXX1234`)
- Work type
- Subtotal, GST, Total
- Status badge (pending approval / approved / sent / rejected / expired)
- PDF link (if generated)

**Key code:** `backend/app/api/quotes.py`, `frontend/app/quotes/page.tsx`

---

## 6. Demo / Web UI Flow

For demos without a WhatsApp Business Account. Available at `/demo`.

The demo bypasses WhatsApp and Celery entirely — all calls are synchronous and go directly to the DB and LLM.

### Two-pane layout

- **Left pane** — simulates the buyer's WhatsApp chat (green bubbles, `#e5ddd5` background)
- **Right pane** — simulates the contractor's view, showing the quote when it's ready

### Flow

1. Page loads → `crypto.randomUUID()` generates a fresh session ID
2. Buyer types a message → `POST /api/v1/demo/chat` → `ConversationEngine.process()` runs synchronously → AI reply returned in the HTTP response (no Celery, no WA)
3. When all slots are filled, the quote appears on the right pane
4. Contractor clicks **Approve** → `POST /api/v1/demo/decide` → PDF generated → "Open PDF" link shown
5. Or clicks **Reject** → quote marked rejected
6. **Reset conversation** reloads the page with a new session ID

The demo always routes to the **first contractor in the database** (the seeded dev contractor). No auth required.

**Key code:** `backend/app/api/demo.py`, `frontend/app/demo/page.tsx`

---

## 7. Architecture

### Services

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                          │
│   /onboarding   /quotes   /login   /demo                        │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP (REST)
┌────────────────────────▼────────────────────────────────────────┐
│                     FastAPI Backend (:8000)                      │
│                                                                  │
│  /webhooks/whatsapp (Meta) or /webhooks/twilio/whatsapp → queue   │
│  /api/v1/demo/chat   →  ConversationEngine (synchronous)        │
│  /api/v1/quotes      →  Quote DB query (auth required)          │
│  /api/v1/onboarding  →  OnboardingService                       │
│  /pdfs/*             →  StaticFiles (generated PDFs)            │
└───────┬────────────────────────┬───────────────────────────────┘
        │                        │
┌───────▼──────┐        ┌────────▼────────┐
│   Postgres   │        │  Celery Worker  │
│   (SQLAlch.) │        │  + Redis broker │
└──────────────┘        └────────┬────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │   ConversationEngine      │
                    │   + LLM (Vertex Gemini)   │
                    │   + WhatsApp (Meta/Twilio) │
                    └──────────────────────────┘
```

### Key design decisions

| Decision | Rationale |
|---|---|
| **Celery for WA messages** | Meta webhooks must respond in < 5 s. The LLM call can take 3–8 s. Celery decouples receipt from processing. |
| **Synchronous demo endpoint** | Demo UI needs inline replies. No Celery, no WA — just HTTP request/response. |
| **Deterministic pricing** | Pricing logic uses no LLM. Rules are applied from the contractor's rate table. Reproducible, auditable, fast. |
| **Strategy pattern for handlers** | One class per session state. Easy to add/modify states without touching the engine. |
| **API key auth (UUID v4)** | Simple stateless auth. No sessions, no OAuth. Key is generated server-side, shown once, stored as a hash-indexed UUID column. |
| **Multitenancy via contractor_id** | Every table (sessions, quotes, messages, pricing configs) is scoped by `contractor_id`. A single deployment serves multiple contractors. |
| **LLM prompts in Jinja templates** | All prompts live in `backend/app/prompts/*.jinja`. Never inlined in code. Easy to iterate without code changes. |

### Component responsibilities

| Component | Responsibility |
|---|---|
| `ConversationEngine` | Orchestrates DB reads/writes and handler dispatch. Owns all I/O. |
| `StateHandler` subclasses | Pure business logic per state. No DB or WA access — only return `HandlerResult`. |
| `SlotExtractor` | Calls LLM to extract structured values from buyer free text. |
| `QuestionPhraser` | Calls LLM to phrase the next clarifying question naturally. |
| `PricingEvaluator` | Deterministic. Applies rate table rules to collected slots. |
| `ApprovalService` | Keyword-matches contractor replies. Generates PDF. Sends to buyer. |
| `PdfService` | Renders Jinja HTML template → WeasyPrint → PDF file. |
| `OnboardingService` | Creates contractor rows, deduplicates slugs/phones. |
| `RateCardParser` | Calls Gemini Pro to parse uploaded rate card files. |
| `WhatsAppClient` | Wraps Meta Graph API. Sends text and document messages. |

---

## 8. Database Schema Summary

```
contractors
  id, phone, business_name, city, whatsapp_link_slug
  api_key (UUID, unique — used for dashboard auth)
  wa_phone_number_id (used to route inbound WA messages to the right contractor)
  approval_mode, confidence_threshold

pricing_configs
  id, contractor_id → contractors
  work_type (painting | false_ceiling)
  rules (JSONB — rate table + input definitions)
  is_active, version

sessions
  id, contractor_id → contractors
  buyer_phone, state (enum), work_type (enum)
  collected_slots (JSONB), missing_slots (JSONB)
  last_message_at, expires_at

messages
  id, session_id → sessions
  direction (inbound | outbound), message_type
  raw_content, normalized_content, whatsapp_message_id

quotes
  id, session_id → sessions, contractor_id → contractors
  buyer_phone, work_type
  line_items (JSONB), subtotal, gst_amount, total
  status (pending_approval | approved | sent | rejected | expired)
  pdf_url, validity_date, approved_at, sent_at

audit_logs
  id, contractor_id, session_id
  event_type, payload (JSONB)
```

---

## 9. State Machine Reference

```
                    ┌─────────┐
   buyer sends      │ GREETING│  AI sends welcome message
   first message ──►│         │─────────────────────────────►
                    └─────────┘                              │
                                                             ▼
                    ┌──────────────────┐
                    │ IDENTIFYING_SCOPE│  AI detects work type
                    │                  │  (painting / false ceiling)
                    └──────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
              ┌────►│COLLECTING_INPUTS│  AI asks for area, finish,
              │     │                 │  number of coats, etc.
              └─────┤  (loops until   │  one slot at a time
           missing  │  all slots full)│
           slots    └─────────────────┘
                             │ all slots collected
                             ▼
                    ┌────────────────┐
                    │ READY_TO_QUOTE │  Deterministic pricing runs.
                    │                │  Quote persisted to DB.
                    │                │  Buyer told "contractor will confirm."
                    └────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │AWAITING_APPROVAL │  Contractor notified via WA.
                    │                  │  Waiting for approve/reject reply.
                    └──────────────────┘
                          │       │
               approve    │       │  reject
                          ▼       ▼
              ┌────────────────┐  ┌────────┐
              │ QUOTE_DELIVERED│  │ CLOSED │
              │                │  │        │
              │ PDF generated  │  │ Buyer  │
              │ sent to buyer  │  │notified│
              └────────────────┘  └────────┘
```

**Approval keywords** (deterministic, no LLM):
- Approve: `approve`, `approved`, `yes`, `ok`, `okay`, `send it`
- Reject: `reject`, `rejected`, `no`, `decline`, `cancel`
