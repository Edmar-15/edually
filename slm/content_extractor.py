import io
import os
import pathlib
import logging

from django.core.files.base import ContentFile

# pip install mammoth python-pptx PyMuPDF
import mammoth               # DOCX → HTML
import fitz                  # PyMuPDF (PDF) → HTML
from pptx import Presentation   # PPTX → simple HTML

logger = logging.getLogger(__name__)

ALLOWED_EXT = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}


def _read_file_bytes(file_obj) -> bytes:
    """Guarantees we have the raw bytes of the uploaded file."""
    if hasattr(file_obj, "read"):
        return file_obj.read()
    # Fallback for TemporaryUploadedFile
    with open(file_obj.path, "rb") as f:
        return f.read()


def _extract_docx(raw: bytes) -> str:
    """Convert DOCX → HTML using Mammoth."""
    result = mammoth.convert_to_html(io.BytesIO(raw))
    return result.value


def _extract_pdf(raw: bytes) -> str:
    """Render each PDF page to HTML using PyMuPDF."""
    doc = fitz.open(stream=raw, filetype="pdf")
    html_pages = []
    for page in doc:
        html_pages.append(page.get_text("html"))
    return "\n".join(html_pages)


def _extract_pptx(raw: bytes) -> str:
    """Very simple conversion of PPTX → HTML (titles + bullet text)."""
    prs = Presentation(io.BytesIO(raw))
    parts = []
    for i, slide in enumerate(prs.slides, start=1):
        parts.append(f"<h2>Slide {i}</h2>")
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            txt = shape.text.strip()
            if not txt:
                continue
            if shape == slide.shapes[0]:
                parts.append(f"<h3>{txt}</h3>")
            else:
                parts.append(f"<p>{txt}</p>")
    return "\n".join(parts)


def extract_content(file_obj) -> str:
    """
    Public API – receives Django ``FileField`` instance and returns an HTML string.
    Raises ``ValueError`` for unsupported types or extraction errors.
    """
    ext = pathlib.Path(file_obj.name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Unsupported extension: {ext}")

    raw = _read_file_bytes(file_obj)

    try:
        if ext in {".docx", ".doc"}:
            return _extract_docx(raw)
        if ext == ".pdf":
            return _extract_pdf(raw)
        if ext in {".pptx", ".ppt"}:
            return _extract_pptx(raw)
    except Exception as exc:
        logger.exception("Failed to extract %s", file_obj.name)
        raise ValueError(f"Extraction error: {exc}")

    raise ValueError(f"Unsupported extension: {ext}")
