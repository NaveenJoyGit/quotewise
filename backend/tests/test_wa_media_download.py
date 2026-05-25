"""Tests for WhatsApp media download (FR-001)."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx

from app.core.config import Settings
from app.services.whatsapp.client import WhatsAppClient
from app.services.whatsapp.payload import extract_document_info


def test_extract_document_info():
    raw = {
        "type": "document",
        "document": {"id": "abc123", "filename": "rates.pdf", "mime_type": "application/pdf"},
    }
    info = extract_document_info(raw)
    assert info is not None
    assert info.media_id == "abc123"
    assert info.filename == "rates.pdf"


def test_extract_document_info_missing():
    assert extract_document_info({"type": "text"}) is None


def test_download_media_mock_mode():
    settings = Settings(wa_access_token="", wa_phone_number_id="")
    client = WhatsAppClient(settings=settings)
    data, name = client.download_media("any-id")
    assert b"Painting rates" in data
    assert name == "mock_rates.txt"


def test_download_media_live_mode():
    settings = Settings(wa_access_token="token", wa_phone_number_id="123")
    mock_http = MagicMock(spec=httpx.Client)

    meta_resp = MagicMock()
    meta_resp.json.return_value = {"url": "https://cdn.example.com/file.pdf"}
    meta_resp.raise_for_status = MagicMock()

    file_resp = MagicMock()
    file_resp.content = b"%PDF-1.4 content"
    file_resp.raise_for_status = MagicMock()

    mock_http.get.side_effect = [meta_resp, file_resp]

    client = WhatsAppClient(settings=settings, http_client=mock_http)
    data, name = client.download_media("media-xyz")
    assert data == b"%PDF-1.4 content"
    assert name == "media-xyz"
    assert mock_http.get.call_count == 2
