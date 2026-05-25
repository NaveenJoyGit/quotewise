"""Demo API — synchronous conversation endpoints that bypass Celery and WhatsApp.

These endpoints let anyone run a full quote conversation in a browser without a
WhatsApp Business Account.  No auth required; always routes to the first seeded
contractor (dev / demo mode only).

POST /api/v1/demo/chat    — send one buyer message; get reply + optional quote
POST /api/v1/demo/decide  — approve or reject a pending quote; get PDF URL
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.api.deps import get_db
from app.db.enums import QuoteStatus
from app.db.models import Contractor, Quote
from app.services.conversation import session_repo
from app.services.conversation.engine import ConversationEngine
from app.services.llm.factory import get_llm_client
from app.services.whatsapp.payload import InboundMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# buyer_phone = "demo-" + first 24 chars of session_id → max 29 chars (fits VARCHAR(32))
_PHONE_PREFIX = "demo-"
_SESSION_ID_CHARS = 24


class ChatRequest(BaseModel):
    text: str
    session_id: str


class DecideRequest(BaseModel):
    quote_id: uuid.UUID
    action: str  # "approve" | "reject"


@router.post("/chat")
def demo_chat(req: ChatRequest, db: DBSession = Depends(get_db)) -> dict[str, Any]:
    contractor = session_repo.resolve_contractor(db)

    buyer_phone = f"{_PHONE_PREFIX}{req.session_id[:_SESSION_ID_CHARS]}"

    inbound = InboundMessage(
        whatsapp_message_id=f"demo-{uuid.uuid4().hex[:12]}",
        from_phone=buyer_phone,
        message_type="text",
        text=req.text,
        raw={},
        phone_number_id="",
    )

    llm = get_llm_client()
    engine = ConversationEngine(db=db, llm=llm)
    reply = engine.process(inbound)

    quote_data: dict[str, Any] | None = None
    if engine.pending_quote_snapshot is not None and engine.last_session is not None:
        quote_data = _persist_quote(db, engine, contractor)

    session_state = (
        engine.last_session.state.value if engine.last_session else "unknown"
    )
    return {"reply": reply, "session_state": session_state, "quote": quote_data}


@router.post("/decide")
def demo_decide(req: DecideRequest, db: DBSession = Depends(get_db)) -> dict[str, Any]:
    if req.action not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="action must be 'approve' or 'reject'")

    quote: Quote | None = db.get(Quote, req.quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found.")

    now = datetime.now(timezone.utc)

    if req.action == "reject":
        quote.status = QuoteStatus.rejected
        db.commit()
        return {"status": "rejected", "pdf_url": None}

    # approve — generate PDF (graceful fallback if WeasyPrint unavailable)
    contractor: Contractor | None = (
        db.query(Contractor).filter(Contractor.id == quote.contractor_id).first()
    )
    if contractor is None:
        raise HTTPException(status_code=500, detail="Contractor record missing.")

    pdf_url: str | None = None
    try:
        from app.services.pdf.service import PdfService
        pdf_url = PdfService().generate(quote, contractor)
        quote.pdf_url = pdf_url
    except Exception:
        logger.warning("demo.pdf_generation_failed", exc_info=True)

    quote.status = QuoteStatus.approved
    quote.approved_at = now
    db.commit()

    return {"status": "approved", "pdf_url": pdf_url}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _persist_quote(
    db: DBSession,
    engine: ConversationEngine,
    contractor: Contractor,
) -> dict[str, Any] | None:
    session = engine.last_session
    snapshot = engine.pending_quote_snapshot
    try:
        pc = session_repo.load_active_pricing_config(
            db, contractor.id, session.work_type or "painting"
        )
        quote = session_repo.create_quote(
            db=db,
            session=session,
            contractor=contractor,
            snapshot=snapshot,
            pricing_config_version=pc.version,
        )
        db.commit()
        return {
            "id": str(quote.id),
            "subtotal": str(quote.subtotal),
            "gst_amount": str(quote.gst_amount),
            "total": str(quote.total),
            "work_type": quote.work_type.value if hasattr(quote.work_type, "value") else str(quote.work_type),
            "line_items": quote.line_items,
            "status": quote.status.value,
        }
    except Exception:
        logger.error("demo.quote_persist_failed", exc_info=True)
        return None
