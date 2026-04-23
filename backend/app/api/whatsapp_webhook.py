import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response, status

from app.core.config import Settings, get_settings
from app.workers.tasks import process_inbound_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


@router.get("")
def verify(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    settings: Settings = None,  # type: ignore[assignment]
) -> Response:
    settings = settings or get_settings()
    if hub_mode != "subscribe" or hub_verify_token != settings.wa_verify_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verification failed")
    return Response(content=hub_challenge, media_type="text/plain")


@router.post("", status_code=status.HTTP_200_OK)
async def receive(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    """Acknowledge-and-enqueue only. SPEC §2.2: no synchronous processing."""
    settings = get_settings()
    raw_body = await request.body()

    if not _signature_ok(raw_body, x_hub_signature_256, settings.wa_app_secret):
        logger.warning(
            "whatsapp.webhook.signature_invalid",
            extra={"event_type": "whatsapp.webhook.signature_invalid"},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid signature")

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid json")

    process_inbound_message.delay(payload)
    logger.info(
        "whatsapp.webhook.enqueued",
        extra={"event_type": "whatsapp.webhook.enqueued"},
    )
    return {"status": "enqueued"}


def _signature_ok(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    # Dev convenience: with no app secret configured, skip verification so the
    # local simulator can post without signing. Never ship to prod with empty secret.
    if not app_secret:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)
