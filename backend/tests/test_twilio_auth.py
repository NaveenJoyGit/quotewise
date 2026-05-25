from app.services.whatsapp.twilio_auth import compute_twilio_signature, verify_twilio_signature


def test_compute_and_verify_signature():
    auth_token = "secret"
    url = "https://example.com/webhooks/twilio/whatsapp"
    params = {"Body": "hi", "From": "whatsapp:+91999"}
    sig = compute_twilio_signature(auth_token, url, params)
    assert verify_twilio_signature(auth_token, url, params, sig)


def test_empty_token_skips_verification():
    assert verify_twilio_signature("", "https://x", {}, None)
