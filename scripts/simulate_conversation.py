"""Local end-to-end simulator for QuoteWise.

Posts a Meta-shaped webhook payload to the running FastAPI app, exercising
the full webhook → queue → worker → WhatsApp sender path without touching
Meta's servers. If the server runs with WA_APP_SECRET unset, signature
verification is skipped (dev convenience).

Usage:
    python scripts/simulate_conversation.py "hello bot"
    python scripts/simulate_conversation.py --from 919876543210 "I want to paint my 3BHK"

Milestone 1 expectation: the worker logs an outbound mock send of
"Got it: <your message>". When Meta credentials are set, the same call
sends a real WhatsApp reply.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time

import httpx


def build_payload(from_phone: str, text: str) -> dict:
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
                                {"profile": {"name": "Local Sim"}, "wa_id": from_phone}
                            ],
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": f"wamid.SIM{int(time.time())}",
                                    "timestamp": str(int(time.time())),
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate an inbound WhatsApp message.")
    parser.add_argument("text", help="Message body to send")
    parser.add_argument("--from", dest="from_phone", default="919876543210", help="Sender phone (E.164 digits)")
    parser.add_argument("--url", default="http://localhost:8000/webhooks/whatsapp", help="Webhook URL")
    args = parser.parse_args()

    payload = build_payload(args.from_phone, args.text)
    body = json.dumps(payload).encode()

    headers = {"Content-Type": "application/json"}
    secret = os.environ.get("WA_APP_SECRET", "")
    if secret:
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Hub-Signature-256"] = sig

    try:
        resp = httpx.post(args.url, content=body, headers=headers, timeout=5.0)
    except httpx.ConnectError:
        print(f"error: could not reach {args.url} — is the FastAPI server running?", file=sys.stderr)
        return 2

    print(f"{resp.status_code} {resp.text}")
    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
