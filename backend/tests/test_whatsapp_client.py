from unittest.mock import MagicMock

from app.core.config import Settings
from app.services.whatsapp.client import WhatsAppClient


def _settings(**overrides) -> Settings:
    base = dict(
        wa_verify_token="vt",
        wa_app_secret="as",
        wa_access_token="",
        wa_phone_number_id="",
    )
    base.update(overrides)
    return Settings(**base)


def test_client_runs_in_mock_mode_without_credentials():
    client = WhatsAppClient(settings=_settings())
    result = client.send_text(to="9198", body="hi")
    assert result["mock"] is True
    assert result["to"] == "9198"
    assert result["body"] == "hi"


def test_client_posts_to_graph_api_when_configured():
    http = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {"messages": [{"id": "wamid.OUT"}]}
    http.post.return_value = resp

    settings = _settings(wa_access_token="TOKEN", wa_phone_number_id="PNID")
    client = WhatsAppClient(settings=settings, http_client=http)

    out = client.send_text(to="9198", body="hello")

    http.post.assert_called_once()
    url = http.post.call_args.args[0]
    kwargs = http.post.call_args.kwargs
    assert "PNID/messages" in url
    assert kwargs["headers"]["Authorization"] == "Bearer TOKEN"
    assert kwargs["json"] == {
        "messaging_product": "whatsapp",
        "to": "9198",
        "type": "text",
        "text": {"body": "hello"},
    }
    assert out == {"messages": [{"id": "wamid.OUT"}]}
