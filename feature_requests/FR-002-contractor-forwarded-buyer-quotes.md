# FR-002 — Contractor-Forwarded Buyer Quotes

**Status:** Implemented  
**Depends on:** SPEC.md, FR-001, M4 approval flow  
**Last updated:** May 2026

---

## 0. How to read this spec

- **Tight** — routing, session source, proxy conversation, auto-delivery to contractor, synthetic buyer phone.
- **Loose** — exact WhatsApp copy, forward_metadata fields.

---

## 1. Product overview (tight)

Contractors forward buyer enquiries from their personal WhatsApp to the QuoteWise bot. The system:

1. Detects `context.forwarded` on inbound messages
2. Runs the quote state machine in **proxy mode** (replies to contractor, not buyer)
3. Asks the **contractor** follow-up questions when slots are missing
4. **Auto-sends PDF** to the contractor when ready (no approve/reject)

Direct buyer flow (`quote-<slug>`) and FR-001 admin flows are unchanged.

### 1.2 Out of scope

- PDF to buyer without buyer phone (Meta does not expose it on forwards)
- OCR / voice / image forwards
- Multiple parallel forward sessions per contractor
- Dashboard UI for forward sessions

---

## 2. Architecture (tight)

**Routing priority** ([`backend/app/workers/tasks.py`](../backend/app/workers/tasks.py)):

1. FR-001 admin session / prefix
2. Registered contractor + active `contractor_forward` session → `ForwardedQuoteEngine`
3. Registered contractor + forwarded message → `ForwardedQuoteEngine`
4. Registered contractor + approve/reject + pending **buyer_direct** quote → `ApprovalService`
5. Other senders → buyer `ConversationEngine`
6. Registered contractor idle → help text

---

## 3. Data model (tight)

`Session.source`: `buyer_direct` | `contractor_forward` (default `buyer_direct`)

Forward sessions:

- `buyer_phone` = `fwd:{session.id}`
- Start state `identifying_scope` (skip greeting)
- One open forward session per contractor (TTL from settings)

---

## 4. Success criteria

- [ ] Forward buyer text → contractor gets follow-ups → PDF auto-delivered
- [ ] Contractor non-forward replies continue same forward session
- [ ] Direct buyer approve flow unchanged
- [ ] FR-001 admin priority preserved

---

## 5. Incremental commits

See CHANGELOG FR-002 section.
