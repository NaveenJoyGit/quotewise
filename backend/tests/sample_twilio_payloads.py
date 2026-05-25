"""Twilio WhatsApp webhook form bodies (application/x-www-form-urlencoded)."""
from __future__ import annotations

from typing import Any


def twilio_text_message(
    *,
    from_phone: str = "whatsapp:+919999900001",
    to: str = "whatsapp:+14155238886",
    body: str = "hello",
    message_sid: str = "SM_TEST001",
    wa_id: str = "919999900001",
    forwarded: bool = False,
) -> dict[str, str]:
    params: dict[str, str] = {
        "MessageSid": message_sid,
        "SmsSid": message_sid,
        "AccountSid": "AC_TEST",
        "From": from_phone,
        "To": to,
        "Body": body,
        "NumMedia": "0",
        "NumSegments": "1",
        "SmsStatus": "received",
        "ApiVersion": "2010-04-01",
        "MessageType": "text",
        "WaId": wa_id,
    }
    if forwarded:
        params["Forwarded"] = "true"
    return params


def twilio_document_message(
    *,
    from_phone: str = "whatsapp:+919999900001",
    media_url: str = "https://api.twilio.com/2010-04-01/Accounts/AC/Messages/SM/Media/ME",
    filename_hint: str = "rates.pdf",
) -> dict[str, str]:
    return {
        "MessageSid": "SM_DOC001",
        "From": from_phone,
        "To": "whatsapp:+14155238886",
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": media_url,
        "MediaContentType0": "application/pdf",
        "WaId": "919999900001",
    }
