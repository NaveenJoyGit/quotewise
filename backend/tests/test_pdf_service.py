"""Tests for PdfService — uses injectable renderer to avoid native WeasyPrint deps."""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_renderer(pdf_bytes: bytes = b"%PDF-1.4 fake"):
    """Returns a callable that mimics weasyprint.HTML."""
    mock = MagicMock()
    mock.return_value.write_pdf.return_value = pdf_bytes
    return mock


def _make_quote(**overrides):
    defaults = dict(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        buyer_phone="919876543210",
        work_type="painting",
        line_items=[
            {
                "description": "Painting 1000 sqft new_wall (premium)",
                "quantity": "1000.00",
                "unit": "sqft",
                "rate": "22.00",
                "amount": "22000.00",
            }
        ],
        subtotal=Decimal("22000.00"),
        gst_amount=Decimal("3960.00"),
        total=Decimal("25960.00"),
        validity_date=datetime.date(2026, 5, 25),
        pdf_url=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_contractor(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        business_name="QuoteWise Dev Contractor",
        gst_number="29ABCDE1234F1Z5",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_service(tmp_path: Path, base_url: str = "http://localhost:8000", renderer=None):
    from app.services.pdf.service import PdfService
    return PdfService(
        storage_dir=tmp_path,
        base_url=base_url,
        _html_renderer=renderer or _fake_renderer(),
    )


def test_generate_returns_public_url(tmp_path):
    svc = _make_service(tmp_path)
    quote = _make_quote()
    contractor = _make_contractor()

    url = svc.generate(quote, contractor)

    assert url == f"http://localhost:8000/pdfs/quote_{quote.id}.pdf"


def test_generate_creates_file_at_expected_path(tmp_path):
    renderer = _fake_renderer(b"%PDF-1.4 fake content")
    svc = _make_service(tmp_path, renderer=renderer)
    quote = _make_quote()
    contractor = _make_contractor()

    svc.generate(quote, contractor)

    expected = tmp_path / f"quote_{quote.id}.pdf"
    assert expected.exists()
    assert expected.read_bytes() == b"%PDF-1.4 fake content"


def test_generate_creates_storage_dir_if_missing(tmp_path):
    storage = tmp_path / "deep" / "nested" / "pdfs"
    assert not storage.exists()

    from app.services.pdf.service import PdfService
    svc = PdfService(
        storage_dir=storage,
        base_url="http://localhost:8000",
        _html_renderer=_fake_renderer(),
    )
    svc.generate(_make_quote(), _make_contractor())

    assert storage.exists()


def test_generate_passes_html_string_to_renderer(tmp_path):
    renderer = _fake_renderer()
    svc = _make_service(tmp_path, renderer=renderer)
    quote = _make_quote()
    contractor = _make_contractor()

    svc.generate(quote, contractor)

    call_kwargs = renderer.call_args.kwargs
    rendered_html = call_kwargs["string"]
    assert "QuoteWise Dev Contractor" in rendered_html
    assert "25960.00" in rendered_html


def test_generate_html_contains_gst_number(tmp_path):
    renderer = _fake_renderer()
    svc = _make_service(tmp_path, renderer=renderer)
    svc.generate(_make_quote(), _make_contractor())
    rendered_html = renderer.call_args.kwargs["string"]
    assert "29ABCDE1234F1Z5" in rendered_html


def test_generate_is_idempotent(tmp_path):
    r1 = _fake_renderer(b"first")
    svc1 = _make_service(tmp_path, renderer=r1)
    url1 = svc1.generate(_make_quote(), _make_contractor())

    r2 = _fake_renderer(b"second")
    svc2 = _make_service(tmp_path, renderer=r2)
    url2 = svc2.generate(_make_quote(), _make_contractor())

    assert url1 == url2
    quote = _make_quote()
    assert (tmp_path / f"quote_{quote.id}.pdf").read_bytes() == b"second"


def test_mask_phone():
    from app.services.pdf.service import _mask_phone
    assert _mask_phone("919876543210") == "+XX XXXXXX3210"
    assert _mask_phone("+919876543210") == "+XX XXXXXX3210"
    assert _mask_phone("12") == "XXXXXX"


def test_generate_with_no_gst_number(tmp_path):
    svc = _make_service(tmp_path)
    quote = _make_quote()
    contractor = _make_contractor(gst_number=None)
    url = svc.generate(quote, contractor)
    assert url.endswith(".pdf")


def test_masked_phone_appears_in_rendered_html(tmp_path):
    renderer = _fake_renderer()
    svc = _make_service(tmp_path, renderer=renderer)
    svc.generate(_make_quote(buyer_phone="919876543210"), _make_contractor())
    rendered_html = renderer.call_args.kwargs["string"]
    assert "3210" in rendered_html  # Last 4 digits visible, full number not
    assert "9876" not in rendered_html
