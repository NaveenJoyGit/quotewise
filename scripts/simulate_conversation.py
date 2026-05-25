"""Local end-to-end simulator for QuoteWise.

Posts inbound webhook payloads to the running FastAPI app (Meta or Twilio),
exercising webhook → queue → worker → WhatsApp sender without external APIs.

Usage:
    # Meta (default)
    python scripts/simulate_conversation.py "hello bot"
    python scripts/simulate_conversation.py --from 919876543210 "quote-dev"

    # Twilio (set WA_PROVIDER=twilio in backend/.env)
    python scripts/simulate_conversation.py --provider twilio --from 919999900001 "manage-rates"
    python scripts/simulate_conversation.py --provider twilio --forwarded --from 919999900001 "Need painting 1000 sqft"
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


def build_meta_payload(from_phone: str, text: str, *, forwarded: bool = False) -> dict:
    msg: dict = {
        "from": from_phone,
        "id": f"wamid.SIM{int(time.time())}",
        "timestamp": str(int(time.time())),
        "text": {"body": text},
        "type": "text",
    }
    if forwarded:
        msg["context"] = {"forwarded": True}
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
                                "phone_number_id": os.environ.get(
                                    "WA_PHONE_NUMBER_ID", "PHONE_NUMBER_ID"
                                ),
                            },
                            "contacts": [
                                {"profile": {"name": "Local Sim"}, "wa_id": from_phone}
                            ],
                            "messages": [msg],
                        },
                    }
                ],
            }
        ],
    }


def build_twilio_form(from_phone: str, text: str, *, forwarded: bool = False) -> dict[str, str]:
    to = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    if not to.lower().startswith("whatsapp:"):
        to = f"whatsapp:{to}"
    from_addr = from_phone
    if not from_addr.lower().startswith("whatsapp:"):
        from_addr = f"whatsapp:+{from_phone.lstrip('+')}"

    sid = f"SM_SIM{int(time.time())}"
    params = {
        "MessageSid": sid,
        "SmsSid": sid,
        "AccountSid": os.environ.get("TWILIO_ACCOUNT_SID", "AC_SIM"),
        "From": from_addr,
        "To": to,
        "Body": text,
        "NumMedia": "0",
        "WaId": from_phone.replace("whatsapp:", "").replace("+", ""),
    }
    if forwarded:
        params["Forwarded"] = "true"
    return params


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate an inbound WhatsApp message.")
    parser.add_argument("text", help="Message body to send")
    parser.add_argument(
        "--provider",
        choices=("meta", "twilio"),
        default=os.environ.get("WA_PROVIDER", "meta"),
        help="Webhook format (default: WA_PROVIDER env or meta)",
    )
    parser.add_argument(
        "--from",
        dest="from_phone",
        default="919876543210",
        help="Sender phone (digits or whatsapp:+E164)",
    )
    parser.add_argument(
        "--forwarded",
        action="store_true",
        help="Mark message as forwarded (FR-002)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Webhook URL (default depends on --provider)",
    )
    args = parser.parse_args()

    if args.url:
        url = args.url
    elif args.provider == "twilio":
        url = "http://localhost:8000/webhooks/twilio/whatsapp"
    else:
        url = "http://localhost:8000/webhooks/whatsapp"

    try:
        if args.provider == "twilio":
            form = build_twilio_form(args.from_phone, args.text, forwarded=args.forwarded)
            resp = httpx.post(url, data=form, timeout=5.0)
        else:
            payload = build_meta_payload(args.from_phone, args.text, forwarded=args.forwarded)
            body = json.dumps(payload).encode()
            headers = {"Content-Type": "application/json"}
            secret = os.environ.get("WA_APP_SECRET", "")
            if secret:
                sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
                headers["X-Hub-Signature-256"] = sig
            resp = httpx.post(url, content=body, headers=headers, timeout=5.0)
    except httpx.ConnectError:
        print(f"error: could not reach {url} — is the FastAPI server running?", file=sys.stderr)
        return 2

    print(f"{resp.status_code} {resp.text[:200]}")
    return 0 if resp.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
