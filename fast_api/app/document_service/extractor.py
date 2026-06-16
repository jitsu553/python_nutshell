from pathlib import Path


def extract_text(file_path: Path, content_type: str) -> str:
    """
    Dispatch to the correct extractor based on content type.
    Returns plain text string. Returns empty string on failure.
    """
    try:
        if content_type == "application/pdf":
            return _extract_pdf(file_path)
        if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return _extract_docx(file_path)
        if content_type == "text/plain":
            return _extract_txt(file_path)
    except Exception:
        return ""
    return ""


def _extract_pdf(file_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    return "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )


def _extract_docx(file_path: Path) -> str:
    from docx import Document

    doc = Document(str(file_path))
    return "\n".join(
        paragraph.text
        for paragraph in doc.paragraphs
        if paragraph.text.strip()
    )


def _extract_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="replace")