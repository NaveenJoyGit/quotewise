"""Fixtures mirroring Meta's actual WhatsApp Cloud API webhook payload shape.
Reference: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
"""
from typing import Any


def text_message(
    from_phone: str = "919876543210",
    text: str = "hello",
    message_id: str = "wamid.TEST001",
) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "PHONE_NUMBER_ID",
                            },
                            "contacts": [
                                {"profile": {"name": "Test Buyer"}, "wa_id": from_phone}
                            ],
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": message_id,
                                    "timestamp": "1714000000",
                                    "text": {"body": text},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def document_message(
    from_phone: str = "919876543210",
    media_id: str = "MEDIA_ID_123",
    filename: str = "rates.pdf",
    message_id: str = "wamid.DOC001",
) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "PHONE_NUMBER_ID",
                            },
                            "contacts": [
                                {"profile": {"name": "Contractor"}, "wa_id": from_phone}
                            ],
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": message_id,
                                    "timestamp": "1714000000",
                                    "type": "document",
                                    "document": {
                                        "id": media_id,
                                        "filename": filename,
                                        "mime_type": "application/pdf",
                                    },
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def forwarded_text_message(
    from_phone: str = "919999900001",
    text: str = "Need painting for 1000 sqft apartment",
    message_id: str = "wamid.FWD001",
) -> dict[str, Any]:
    """Contractor forwards a buyer message to the bot (FR-002)."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "PHONE_NUMBER_ID",
                            },
                            "contacts": [
                                {"profile": {"name": "Contractor"}, "wa_id": from_phone}
                            ],
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": message_id,
                                    "timestamp": "1714000000",
                                    "type": "text",
                                    "context": {"forwarded": True},
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def status_only() -> dict[str, Any]:
    """Payload with no 'messages' key — just a delivery/read status callback."""
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "PHONE_NUMBER_ID",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.STATUS1",
                                    "status": "delivered",
                                    "timestamp": "1714000001",
                                    "recipient_id": "919876543210",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
