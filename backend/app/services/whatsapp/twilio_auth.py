"""Twilio webhook request signature validation (HMAC-SHA1)."""
from __future__ import annotations

import base64
import hmac
import hashlib
from urllib.parse import urlparse, urlunparse


def compute_twilio_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """Compute X-Twilio-Signature for the given URL and POST parameters.

    Twilio sorts POST fields by name and appends each key+value to the URL
    with no delimiters (not application/x-www-form-urlencoded encoding).
    See https://www.twilio.com/docs/usage/security#validating-requests
    """
    data = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _signature_url_variants(url: str) -> list[str]:
    """URLs Twilio may have signed (with and without explicit :443/:80).

    Mirrors twilio-python RequestValidator.validate() — Twilio's backend is
    inconsistent about including the port in the signed URL string.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or parsed.netloc.split(":")[0]

    without_port = urlunparse(
        (parsed.scheme, hostname, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )

    if parsed.port:
        with_port = url
    else:
        default_port = 443 if parsed.scheme == "https" else 80
        with_port = urlunparse(
            (
                parsed.scheme,
                f"{hostname}:{default_port}",
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )

    variants: list[str] = []
    for candidate in (without_port, with_port):
        normalized = candidate.rstrip("/")
        if normalized not in variants:
            variants.append(normalized)
    return variants


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
    for candidate_url in _signature_url_variants(url):
        expected = compute_twilio_signature(auth_token, candidate_url, params)
        if hmac.compare_digest(expected, signature):
            return True
    return False
