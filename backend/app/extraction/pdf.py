import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_BYTES = 10 * 1024 * 1024
MIN_TEXT_CHARS = 200
MAX_TEXT_CHARS = 120_000


class PdfError(Exception):
    pass


def pdf_to_text(data: bytes) -> str:
    """Text from a text-based PDF. Scanned PDFs are rejected because they have no text layer."""
    if len(data) > MAX_PDF_BYTES:
        raise PdfError("PDF is larger than 10 MB")
    if not data.startswith(b"%PDF"):
        raise PdfError("file is not a PDF")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PdfError("PDF is password protected")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfReadError as exc:
        raise PdfError(f"could not read PDF: {exc}") from exc
    text = text.strip()
    if len(text) < MIN_TEXT_CHARS:
        raise PdfError("PDF has almost no text; it may be a scanned image, which is not supported yet")
    return text[:MAX_TEXT_CHARS]
