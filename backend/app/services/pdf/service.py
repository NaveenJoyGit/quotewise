"""PDF generation service — renders an HTML quote template to a PDF file.

WeasyPrint converts the rendered HTML to PDF. The file is written to a local
directory and served via FastAPI's StaticFiles mount.
"""
from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.core.config import Settings, get_settings
from app.db.models import Contractor, Quote

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent
_TEMPLATE_NAME = "quote_template.html"


class PdfService:
    def __init__(
        self,
        storage_dir: str | Path | None = None,
        base_url: str | None = None,
        settings: Settings | None = None,
        _html_renderer=None,  # Injected in tests to avoid native WeasyPrint dependencies
    ) -> None:
        s = settings or get_settings()
        self._storage_dir = Path(storage_dir or s.pdf_storage_dir)
        self._base_url = (base_url or s.pdf_base_url).rstrip("/")
        self._html_renderer = _html_renderer  # None → real weasyprint.HTML at generate() time
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            undefined=StrictUndefined,
            autoescape=True,
        )

    def generate(self, quote: Quote, contractor: Contractor) -> str:
        """Render quote → PDF; return the public URL string.

        Idempotent: if the file already exists it is overwritten.
        """
        if self._html_renderer is None:
            import weasyprint
            html_cls = weasyprint.HTML
        else:
            html_cls = self._html_renderer

        self._storage_dir.mkdir(parents=True, exist_ok=True)

        html_str = self._render_html(quote, contractor)
        pdf_bytes = html_cls(string=html_str).write_pdf()

        filename = f"quote_{quote.id}.pdf"
        dest = self._storage_dir / filename
        dest.write_bytes(pdf_bytes)

        url = f"{self._base_url}/pdfs/{filename}"
        logger.info(
            "pdf.generated",
            extra={
                "event_type": "pdf.generated",
                "quote_id": str(quote.id),
                "path": str(dest),
                "url": url,
            },
        )
        return url

    def _render_html(self, quote: Quote, contractor: Contractor) -> str:
        template = self._jinja_env.get_template(_TEMPLATE_NAME)
        masked_phone = _mask_phone(str(quote.buyer_phone))
        return template.render(
            contractor=contractor,
            quote=quote,
            masked_buyer_phone=masked_phone,
            line_items=quote.line_items,
        )


def _mask_phone(phone: str) -> str:
    """Show only the last 4 digits of the buyer's phone number (SPEC §9 PII)."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 4:
        return "XXXXXX"
    return f"+XX XXXXXX{digits[-4:]}"
