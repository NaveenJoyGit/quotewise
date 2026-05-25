# FR-001 — WhatsApp Contractor Onboarding

**Status:** In progress  
**Depends on:** SPEC.md (M5 web onboarding, M4 approval routing)  
**Last updated:** May 2026

---

## 0. How to read this spec

- **Tight sections** — routing priority, data model, state machines, LLM boundaries, persistence via `OnboardingService`. Binding for implementation.
- **Loose sections** — exact WhatsApp copy, session TTL tuning, optional profile-extract heuristics.

---

## 1. Product overview (tight)

### 1.1 Goal

Let contractors manage QuoteWise account setup and pricing **over WhatsApp**, mirroring the web `/onboarding` flow:

| Phase | Prefix | Who | What |
|-------|--------|-----|--------|
| 1 | `manage-rates` | Registered contractor phone only | Upload/paste rate card → confirm → new `PricingConfig` version |
| 2 | `onboard` | Unregistered phone | Collect profile + pricing → `create_contractor` + `save_pricing_config` |

**Product details** = `PricingConfig.rules` only (inputs, rate_table, modifiers, line_item_template). No separate inventory/catalog table.

### 1.2 Out of scope

- Profile updates for existing contractors via WA (Phase 1 is pricing only)
- API key rotation / retrieval
- Image/OCR rate cards (PDF, TXT, CSV, plain text only)
- Hindi/Kannada admin copy
- Dashboard UI for admin sessions
- Replacing web onboarding (both channels coexist)

---

## 2. Architecture (tight)

### 2.1 Routing priority

On each inbound message (after `resolve_contractor` for tenant):

1. **Active `ContractorAdminSession`** for sender phone → `ContractorAdminEngine`
2. **Admin prefix** on text message → start or reject admin flow
3. **Sender phone matches registered contractor** → `ApprovalService`
4. **Else** → buyer `ConversationEngine`

### 2.2 Prefixes

- `manage-rates` — case-insensitive; optional tail (e.g. `manage-rates painting`)
- `onboard` — case-insensitive; Phase 2 signup

### 2.3 Reuse

- `OnboardingService.create_contractor`, `save_pricing_config`
- `RateCardParser` + `rate_card_ingest.jinja`
- `extract_text` for documents
- `PricingRules` validation
- `WhatsAppClient.download_media` for inbound documents

### 2.4 Phone normalization (tight)

Meta sends `919876543210`; DB may store `+919876543210`. All routing uses `app.services.whatsapp.phone` helpers — never raw string equality.

---

## 3. Data model (tight)

### 3.1 ContractorAdminSession

```
id (uuid, pk)
contractor_id (fk contractors, nullable — null during Phase 2 pre-signup)
admin_phone (string, indexed) — E.164 normalized
flow_type (enum: manage_rates, onboard)
state (enum — see §4)
work_type (enum work_type, nullable)
draft_rules (jsonb, nullable)
draft_profile (jsonb, nullable) — Phase 2: business_name, city, slug, gst_number
parse_notes (jsonb, default [])
validation_errors (jsonb, default [])
expires_at, created_at, updated_at
```

TTL: reuse `session_ttl_hours` from settings.

---

## 4. State machines (tight)

### 4.1 Phase 1 — manage_rates

```
(awaiting_work_type) → awaiting_content → reviewing → completed | cancelled
```

- **awaiting_work_type:** reply `painting` or `false_ceiling`
- **awaiting_content:** text rate card or document (PDF/TXT/CSV)
- **reviewing:** reply `yes`/`save` to persist, `cancel` to abort
- **completed / cancelled:** terminal; no further messages processed except new prefix

### 4.2 Phase 2 — onboard

```
awaiting_business_name → awaiting_city → awaiting_slug → awaiting_work_type
  → awaiting_content → reviewing → creating_account → completed | cancelled
```

Optional: paste block → `onboarding_profile_extract.jinja` → confirm profile fields.

On **completed:** send buyer link `https://wa.me/<BOT>?text=quote-<slug>` and API key once.

**Guardrails:**

- Registered phone + `onboard` → redirect to `manage-rates`
- Unknown phone + `manage-rates` → rejection (not buyer flow)
- Slug collision → stay in flow, ask alternate slug

---

## 5. LLM boundaries (tight)

| Use case | Template | Model |
|----------|----------|-------|
| Rate card → rules JSON | `rate_card_ingest` | Pro |
| Optional profile paste extract | `onboarding_profile_extract` | Flash |

Confirm/save/cancel and prefix detection: **deterministic**, no LLM.

Every LLM call: log template_name, tokens, latency (SPEC §8.3).

---

## 6. Worker integration (tight)

[`backend/app/workers/tasks.py`](../backend/app/workers/tasks.py):

- `_route_admin_message` → `ContractorAdminEngine.process`
- Commit after successful outbound; audit `pricing.updated` on save

---

## 7. Success criteria

- [ ] Registered contractor: `manage-rates` → document → confirm → active `PricingConfig` version incremented
- [ ] Contractor in admin session: `approve` does not trigger quote approval
- [ ] Unknown phone: `manage-rates` → clear error, not buyer session
- [ ] Phase 2: `onboard` → contractor + pricing created; API key sent once
- [ ] All tests pass

---

## 8. Incremental commits

See project plan: spec → phone normalize → media download → admin session model → phase 1 engine → phase 2 onboard.
