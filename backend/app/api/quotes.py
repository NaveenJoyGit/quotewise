"""Read-only quotes API for the contractor dashboard (SPEC §10.4)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.api.deps import get_current_contractor, get_db
from app.db.enums import QuoteStatus
from app.db.models import Contractor, Quote

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


class LineItemResponse(BaseModel):
    description: str
    quantity: str
    unit: str
    rate: str
    amount: str


class QuoteResponse(BaseModel):
    id: str
    buyer_phone: str
    work_type: str
    subtotal: str
    gst_amount: str
    total: str
    status: str
    pdf_url: str | None
    validity_date: str | None
    created_at: str
    approved_at: str | None
    sent_at: str | None
    line_items: list[dict]

    model_config = {"from_attributes": True}


@router.get("", response_model=list[QuoteResponse])
def list_quotes(
    status: QuoteStatus | None = Query(default=None, description="Filter by quote status"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    contractor: Contractor = Depends(get_current_contractor),
    db: DBSession = Depends(get_db),
) -> list[QuoteResponse]:
    """Return quotes for the authenticated contractor, newest first."""
    q = db.query(Quote).filter(Quote.contractor_id == contractor.id)
    if status is not None:
        q = q.filter(Quote.status == status)

    quotes = q.order_by(Quote.created_at.desc()).offset(offset).limit(limit).all()
    return [_to_response(quote) for quote in quotes]


def _to_response(q: Quote) -> QuoteResponse:
    return QuoteResponse(
        id=str(q.id),
        buyer_phone=q.buyer_phone,
        work_type=q.work_type.value if hasattr(q.work_type, "value") else str(q.work_type),
        subtotal=str(q.subtotal),
        gst_amount=str(q.gst_amount),
        total=str(q.total),
        status=q.status.value if hasattr(q.status, "value") else str(q.status),
        pdf_url=q.pdf_url,
        validity_date=str(q.validity_date) if q.validity_date else None,
        created_at=q.created_at.isoformat(),
        approved_at=q.approved_at.isoformat() if q.approved_at else None,
        sent_at=q.sent_at.isoformat() if q.sent_at else None,
        line_items=q.line_items or [],
    )
