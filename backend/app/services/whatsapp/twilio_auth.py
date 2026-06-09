"""Twilio webhook request signature validation (HMAC-SHA1)."""
from __future__ import annotations

import base64
import hmac
import hashlib


def compute_twilio_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """Compute X-Twilio-Signature for the given URL and POST parameters.

    Twilio sorts POST fields by name and appends each key+value to the URL
    with no delimiters (not application/x-www-form-urlencoded encoding).
    See https://www.twilio.com/docs/usage/security#validating-requests
    """
    data = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def verify_twilio_signature(
    auth_token: str,
    url: str,
    params: dict[str, str],
    signature: str | None,
) -> bool:
    """Return True if signature matches. Empty auth_token skips check (dev only)."""
    if not auth_token:
        return True
    if not signature:
        return False
    expected = compute_twilio_signature(auth_token, url, params)
    return hmac.compare_digest(expected, signature)
