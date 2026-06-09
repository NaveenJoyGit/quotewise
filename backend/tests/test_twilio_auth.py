import base64
import hmac
import hashlib
from urllib.parse import urlencode

from app.services.whatsapp.twilio_auth import compute_twilio_signature, verify_twilio_signature


def test_compute_and_verify_signature():
    auth_token = "secret"
    url = "https://example.com/webhooks/twilio/whatsapp"
    params = {"Body": "hi", "From": "whatsapp:+91999"}
    sig = compute_twilio_signature(auth_token, url, params)
    assert verify_twilio_signature(auth_token, url, params, sig)


def test_empty_token_skips_verification():
    assert verify_twilio_signature("", "https://x", {}, None)


def test_matches_twilio_documented_algorithm():
    """Regression: must not use urlencode (=&) between params."""
    auth_token = "12345"
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    params = {
        "CallSid": "CA1234567890ABCDE",
        "Caller": "+12349013030",
        "Digits": "1234",
        "From": "+12349013030",
        "To": "+18005551212",
    }
    # Twilio spec: sorted key+value concatenation, no delimiters.
    expected_data = url + "".join(k + params[k] for k in sorted(params))
    expected_sig = base64.b64encode(
        hmac.new(auth_token.encode(), expected_data.encode(), hashlib.sha1).digest()
    ).decode()

    assert compute_twilio_signature(auth_token, url, params) == expected_sig
    assert verify_twilio_signature(auth_token, url, params, expected_sig)

    # Old buggy urlencode approach must not match Twilio's signature.
    wrong_data = url + urlencode(sorted(params.items()))
    wrong_sig = base64.b64encode(
        hmac.new(auth_token.encode(), wrong_data.encode(), hashlib.sha1).digest()
    ).decode()
    assert wrong_sig != expected_sig
