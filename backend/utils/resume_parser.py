"""
utils/resume_parser.py
──────────────────────
Extracts plain text from uploaded resume files (PDF or DOCX).
The extracted text is stored in the session and injected into the LLM prompt.
"""

import io
from pathlib import Path
from utils.logger import get_logger

logger = get_logger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text from a PDF file using PyMuPDF (fitz).
    Handles multi-page PDFs and preserves paragraph structure.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
        doc.close()
        full_text = "\n\n".join(pages)
        logger.info(f"PDF parsed: {len(full_text)} chars across {len(pages)} pages")
        return full_text
    except ImportError:
        logger.error("PyMuPDF not installed. Run: pip install pymupdf")
        return ""
    except Exception as e:
        logger.error(f"PDF parse error: {e}")
        return ""


def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extract text from a DOCX file using python-docx.
    Reads all paragraphs and table cells.
    """
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        parts = []

        # Paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                parts.append(text)

        # Tables (skills, education grids etc.)
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells if cell.text.strip()
                )
                if row_text:
                    parts.append(row_text)

        full_text = "\n".join(parts)
        logger.info(f"DOCX parsed: {len(full_text)} chars")
        return full_text
    except ImportError:
        logger.error("python-docx not installed. Run: pip install python-docx")
        return ""
    except Exception as e:
        logger.error(f"DOCX parse error: {e}")
        return ""


def parse_resume(file_bytes: bytes, filename: str) -> str:
    """
    Auto-detect file type and extract resume text.

    Args:
        file_bytes: Raw file content
        filename:   Original filename (used to detect extension)

    Returns:
        Extracted plain text, or empty string on failure
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        text = extract_text_from_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        text = extract_text_from_docx(file_bytes)
    elif ext == ".txt":
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
    else:
        logger.warning(f"Unsupported resume format: {ext}")
        return ""

    return _clean_text(text)


def _clean_text(text: str) -> str:
    """
    Basic cleanup:
    • Collapse excessive newlines
    • Strip leading/trailing whitespace per line
    • Remove non-printable characters
    """
    lines = text.splitlines()
    cleaned = []
    blank_count = 0

    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
            blank_count = 0
        else:
            blank_count += 1
            if blank_count <= 1:  # allow max 1 blank line between sections
                cleaned.append("")

    return "\n".join(cleaned).strip()
