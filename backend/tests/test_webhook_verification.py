def test_verification_handshake_returns_challenge(client):
    resp = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "42-challenge",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "42-challenge"


def test_verification_rejects_bad_token(client):
    resp = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "42-challenge",
        },
    )
    assert resp.status_code == 403


def test_verification_rejects_non_subscribe_mode(client):
    resp = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "42-challenge",
        },
    )
    assert resp.status_code == 403
