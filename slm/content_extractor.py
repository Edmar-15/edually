# slm/content_extractor.py
"""
Enhanced content‑extraction utilities for PDF, DOCX and PPTX files.

Features
--------
* PDF → HTML using pdfminer (better layout) + optional OCR fallback via pytesseract.
* DOCX → HTML that keeps headings, tables, lists and embeds images as base‑64 data‑URIs.
* PPTX → HTML preserving slide titles, bullet lists (nested) and slide images.
* Safety – every output string is sanitised with ``bleach`` before it is stored.
* Central configuration (``EXTRACTOR_SETTINGS``) makes thresholds & options easy to tweak.
* No API/model changes – the public function ``extract_content(file_obj)`` keeps the same
  signature and still raises ``ValueError`` on failure.
"""

import io
import os
import pathlib
import logging
import base64
import html                     # standard‑lib escaping for <pre> blocks
from typing import List

from django.core.files.base import ContentFile

# -------------------------------------------------------------------------
# Third‑party libraries (install with pip if you don’t have them yet)
# -------------------------------------------------------------------------
import mammoth                     # docx → html
import fitz                        # PyMuPDF (pdf)
import pdfminer.high_level as pdfminer  # pdfminer.six
from pptx import Presentation      # python‑pptx
from PIL import Image               # Pillow (image handling)

# Optional OCR – disabled automatically if the binary is missing
try:
    import pytesseract            # pytesseract (needs the tesseract exe)
    _OCR_AVAILABLE = True
except Exception:                 # pragma: no cover – missing Tesseract
    _OCR_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "pytesseract not available – scanned PDFs will not be OCR‑ed."
    )

# HTML sanitiser
import bleach

# Optional BeautifulSoup – only needed when we have to rewrite stray image src’s
try:
    from bs4 import BeautifulSoup   # beautifulsoup4
    _BS4_AVAILABLE = True
except Exception:                 # pragma: no cover
    _BS4_AVAILABLE = False

# -------------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Allowed file extensions (kept identical to the original project)
# -------------------------------------------------------------------------
ALLOWED_EXT = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}

# -------------------------------------------------------------------------
# Central configuration – tune here without touching the extraction code
# -------------------------------------------------------------------------
EXTRACTOR_SETTINGS = {
    # -----------------------------------------------------------------
    # PDF‑related options
    # -----------------------------------------------------------------
    "pdf": {
        "ocr_language": "eng",          # Tesseract language pack
        "min_text_ratio": 0.15,        # <15 % selectable text → run OCR
        "dpi_for_ocr": 200,             # DPI when rendering a page for OCR
        "max_pages_for_ocr": 30,        # safety guard – don’t OCR massive PDFs
    },

    # -----------------------------------------------------------------
    # DOCX‑related options
    # -----------------------------------------------------------------
    "docx": {
        "embed_images": True,           # embed any non‑inline images as base64 data‑uri
    },

    # -----------------------------------------------------------------
    # PPTX‑related options
    # -----------------------------------------------------------------
    "pptx": {
        "embed_images": True,
        "max_image_dim": 1024,          # down‑scale slide images larger than this (px)
    },

    # -----------------------------------------------------------------
    # Bleach sanitiser options – we start from the library defaults and
    # extend the allowed tags/attributes.  **Note:** recent Bleach versions
    # no longer accept a ``styles=`` arg, so we omit it.
    # -----------------------------------------------------------------
    "bleach": {
        "tags": list(bleach.sanitizer.ALLOWED_TAGS) + [
            "h1", "h2", "h3", "h4", "h5", "h6",
            "p", "ul", "ol", "li", "strong", "em", "br",
            "table", "thead", "tbody", "tr", "th", "td",
            "img", "blockquote", "pre", "code", "div",
            "span", "hr"
        ],
        "attributes": {
            "*": ["class", "style", "id"],
            "a": ["href", "title", "target", "rel"],
            "img": ["src", "alt", "title", "width", "height"],
        },
        "strip": True,
    },
}

# -------------------------------------------------------------------------
# Helper – HTML sanitiser (single point of truth)
# -------------------------------------------------------------------------
def _sanitize_html(raw_html: str) -> str:
    cfg = EXTRACTOR_SETTINGS["bleach"]
    return bleach.clean(
        raw_html,
        tags=cfg["tags"],
        attributes=cfg["attributes"],
        strip=cfg["strip"],
    )

# -------------------------------------------------------------------------
# Helper – read raw bytes from any Django FileField‑like object
# -------------------------------------------------------------------------
def _read_file_bytes(file_obj) -> bytes:
    """Guarantees we have the raw bytes of the uploaded file."""
    if hasattr(file_obj, "read"):
        return file_obj.read()
    # TemporaryUploadedFile has a .path attribute
    with open(file_obj.path, "rb") as f:
        return f.read()

# -------------------------------------------------------------------------
# PDF extraction -----------------------------------------------------------
# -------------------------------------------------------------------------
def _extract_pdf(raw: bytes) -> str:
    """
    1️⃣ Try to get selectable text via pdfminer (keeps columns/tables).
    2️⃣ If the PDF looks mostly scanned, render each page with PyMuPDF,
       run OCR via pytesseract, and wrap the result in <pre>.
    Returns **sanitised** HTML.
    """
    settings = EXTRACTOR_SETTINGS["pdf"]

    # -------------------------------------------------
    # 1️⃣ pdfminer → plain text (fast, layout‑aware)
    # -------------------------------------------------
    try:
        txt = pdfminer.extract_text(io.BytesIO(raw))
    except Exception as exc:  # pdfminer can be noisy on bad PDFs
        logger.warning("pdfminer failed (%s) – falling back to OCR", exc)
        txt = ""

    # Heuristic: ratio of non‑whitespace chars to total length
    text_ratio = (len(txt.strip()) / len(txt)) if txt else 0.0
    need_ocr = (text_ratio < settings["min_text_ratio"]) or not txt

    if not need_ocr:
        # Plain selectable text – keep line breaks with <pre>
        html_out = f"<pre>{html.escape(txt)}</pre>"
        return _sanitize_html(html_out)

    # -------------------------------------------------
    # 2️⃣ OCR fallback (only if pytesseract is available)
    # -------------------------------------------------
    if not _OCR_AVAILABLE:
        logger.info("OCR not available – returning empty preview for PDF.")
        return _sanitize_html("<pre></pre>")

    doc = fitz.open(stream=raw, filetype="pdf")
    html_pages: List[str] = []

    for page_number, page in enumerate(doc, start=1):
        # Render the page at a higher DPI for OCR readability
        pix = page.get_pixmap(dpi=settings["dpi_for_ocr"])
        img_bytes = pix.tobytes("png")  # keep everything in‑memory

        try:
            ocr_text = pytesseract.image_to_string(
                Image.open(io.BytesIO(img_bytes)),
                lang=settings["ocr_language"]
            )
        except Exception as exc:
            logger.error("OCR failed on PDF page %s: %s", page_number, exc)
            ocr_text = ""

        html_pages.append(
            f'<div class="pdf-page" data-page="{page_number}"><pre>{html.escape(ocr_text)}</pre></div>'
        )

        if page_number >= settings["max_pages_for_ocr"]:
            logger.info(
                "Reached max_pages_for_ocr (%s) – stopping OCR early.",
                settings["max_pages_for_ocr"]
            )
            break

    final_html = "\n".join(html_pages)
    return _sanitize_html(final_html)

# -------------------------------------------------------------------------
# DOCX extraction ---------------------------------------------------------
# -------------------------------------------------------------------------
def _extract_docx(raw: bytes) -> str:
    """
    Convert DOCX (or .doc) to HTML with Mammoth.
    * Keeps headings, tables, lists, etc.
    * If ``embed_images`` is True, any images that are *not* already inline
      are extracted from the zip container and embedded as base64 data‑uri.
    Returns sanitised HTML.
    """
    # NOTE: We **do not** pass a custom ``convert_image`` function.
    # Mammoth’s default behavior works across all supported versions.
    # The post‑processing step below will embed any image that is still
    # referenced via a file path.
    result = mammoth.convert_to_html(io.BytesIO(raw))
    raw_html = result.value

    if EXTRACTOR_SETTINGS["docx"]["embed_images"] and _BS4_AVAILABLE:
        soup = BeautifulSoup(raw_html, "html.parser")
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src.startswith("data:"):
                continue  # already a data‑uri, nothing to do

            # Try to read the image from the DOCX zip container
            try:
                import zipfile
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    # Word stores binaries under word/media/
                    media_path = src.replace("file:///", "").lstrip("/")
                    if not media_path.startswith("word/media/"):
                        media_path = f"word/media/{media_path}"
                    img_bytes = z.read(media_path)
                    mime = f"image/{pathlib.Path(media_path).suffix.lstrip('.')}"
                    b64 = base64.b64encode(img_bytes).decode()
                    img["src"] = f"data:{mime};base64,{b64}"
            except Exception as exc:
                logger.warning("Failed to embed DOCX image %s: %s", src, exc)
                img["src"] = ""  # break the broken link – the browser will show alt text

        raw_html = str(soup)

    return _sanitize_html(raw_html)

# -------------------------------------------------------------------------
# PPTX extraction ---------------------------------------------------------
# -------------------------------------------------------------------------
def _extract_pptx(raw: bytes) -> str:
    """
    Convert PPTX → HTML.
    * Each slide becomes <section class="ppt-slide" data-slide="N">.
    * First title placeholder → <h2>.
    * Bullet / numbered paragraphs become nested <ul>/<ol>.
    * Images are embedded as base64 data‑uri (optional down‑scale).
    Returns sanitised HTML.
    """
    cfg = EXTRACTOR_SETTINGS["pptx"]
    prs = Presentation(io.BytesIO(raw))

    sections: List[str] = []

    for slide_idx, slide in enumerate(prs.slides, start=1):
        parts: List[str] = [f'<section class="ppt-slide" data-slide="{slide_idx}">']

        # --------------------- title placeholder ---------------------
        title_text = None
        for shape in slide.shapes:
            if getattr(shape, "is_placeholder", False) and shape.placeholder_fmt.idx == 0:
                title_text = shape.text.strip()
                break
        if title_text:
            parts.append(f"<h2>{html.escape(title_text)}</h2>")

        # --------------------- bullet / numbered lists -------------
        bullet_items = []  # (level, tag, escaped_text)
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            # Skip the title shape we already handled
            if title_text and shape.text.strip() == title_text:
                continue
            for para in shape.text_frame.paragraphs:
                txt = para.text.strip()
                if not txt:
                    continue
                lvl = para.level
                tag = "ol" if para.font.bold else "ul"
                bullet_items.append((lvl, tag, html.escape(txt)))

        if bullet_items:
            cur_lvl = -1
            cur_tag = None
            for lvl, tag, txt in bullet_items:
                # Open deeper levels
                while lvl > cur_lvl:
                    parts.append(f"<{tag}>")
                    cur_lvl += 1
                    cur_tag = tag
                # Close while moving up
                while lvl < cur_lvl:
                    parts.append(f"</{cur_tag}>")
                    cur_lvl -= 1
                parts.append(f"<li>{txt}</li>")
            # Close any still‑open list
            while cur_lvl >= 0:
                parts.append(f"</{cur_tag}>")
                cur_lvl -= 1

        # --------------------- images (pictures) ------------------
        if cfg["embed_images"]:
            for shape in slide.shapes:
                if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
                    image = shape.image
                    img_bytes = image.blob

                    # Down‑scale huge images to keep DB size modest
                    if max(image.width, image.height) > cfg["max_image_dim"]:
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        pil_img.thumbnail(
                            (cfg["max_image_dim"], cfg["max_image_dim"])
                        )
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        img_bytes = buf.getvalue()
                        mime = "image/png"
                    else:
                        mime = f"image/{image.ext}"

                    b64 = base64.b64encode(img_bytes).decode()
                    parts.append(
                        f'<img src="data:{mime};base64,{b64}" alt="Slide {slide_idx} image">'
                    )

        parts.append("</section>")
        sections.append("\n".join(parts))

    return _sanitize_html("\n".join(sections))

# -------------------------------------------------------------------------
# Public façade – unchanged signature (returns safe HTML or raises ValueError)
# -------------------------------------------------------------------------
def extract_content(file_obj) -> str:
    """
    Public API used throughout the project.
    Accepts a Django ``FileField``‑like object and returns **sanitised HTML**.
    Raises ``ValueError`` for unsupported extensions or any extraction problem.
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
    except Exception as exc:  # pragma: no cover – exercised via runtime
        logger.exception("Failed to extract %s", file_obj.name)
        raise ValueError(f"Extraction error: {exc}")

    # This line should never be reached because the extension guard is earlier
    raise ValueError(f"Unsupported extension: {ext}")
