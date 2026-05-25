"""Twilio WhatsApp inbound webhook — acknowledge and enqueue (SPEC §2.2)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.core.config import Settings, get_settings
from app.services.whatsapp.twilio_auth import verify_twilio_signature
from app.workers.tasks import process_inbound_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio/whatsapp", tags=["whatsapp-twilio"])

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


@router.post("", status_code=status.HTTP_200_OK)
async def receive(
    request: Request,
    x_twilio_signature: str | None = Header(default=None),
) -> Response:
    """Parse form POST, verify signature, enqueue Celery task, return empty TwiML."""
    settings = get_settings()
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}

    webhook_url = _webhook_url(request, settings)
    if not verify_twilio_signature(
        settings.twilio_auth_token,
        webhook_url,
        params,
        x_twilio_signature,
    ):
        logger.warning(
            "twilio.webhook.signature_invalid",
            extra={"event_type": "twilio.webhook.signature_invalid"},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid signature")

    process_inbound_message.delay({"provider": "twilio", "data": params})
    logger.info(
        "twilio.webhook.enqueued",
        extra={"event_type": "twilio.webhook.enqueued"},
    )
    return Response(content=_EMPTY_TWIML, media_type="application/xml")


def _webhook_url(request: Request, settings: Settings) -> str:
    if settings.twilio_webhook_public_url:
        return settings.twilio_webhook_public_url.rstrip("/")
    return str(request.url).split("?")[0]
