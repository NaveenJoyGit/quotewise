"""Extract text from uploaded rate card files (SPEC §4.1 USE CASE 5)."""
from __future__ import annotations

import io


class UnsupportedFormatError(ValueError):
    """Raised when the uploaded file type is not supported."""


_SUPPORTED_EXTENSIONS = frozenset({".pdf", ".txt", ".csv"})


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from a rate card file.

    Supported: .pdf (text layer), .txt, .csv.
    Raises UnsupportedFormatError for other types.
    """
    lower = filename.lower()
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""

    if ext == ".pdf":
        return _extract_pdf(file_bytes)
    if ext in (".txt", ".csv"):
        return file_bytes.decode("utf-8", errors="replace")

    raise UnsupportedFormatError(
        f"Unsupported file type: '{filename}'. Supported: PDF, TXT, CSV."
    )


def _extract_pdf(file_bytes: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)
