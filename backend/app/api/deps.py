"""Shared FastAPI dependencies (SPEC §3.3)."""
from __future__ import annotations

import uuid
from typing import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.db.base import SessionLocal
from app.db.models import Contractor


def get_db() -> Generator[DBSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_contractor(
    x_contractor_key: str | None = Header(default=None, alias="X-Contractor-Key"),
    db: DBSession = Depends(get_db),
) -> Contractor:
    """Authenticate a contractor by API key. Raises 401 on missing or invalid key."""
    if not x_contractor_key:
        raise HTTPException(
            status_code=401,
            detail="X-Contractor-Key header is required.",
        )
    try:
        key_uuid = uuid.UUID(x_contractor_key)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid API key format.")

    contractor = (
        db.query(Contractor).filter(Contractor.api_key == key_uuid).first()
    )
    if contractor is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return contractor
