"""
Reads the CIM PDF page by page (fully offline, using pdfplumber) and groups
pages into chunks small enough for a local model.
"""
import pdfplumber

import config


class ScannedPDFError(RuntimeError):
    pass


def read_pdf(path) -> list[dict]:
    """Return [{'page': 1, 'text': '...'}, ...]. Tables are appended as rows
    separated by ' | ' so financial tables keep their structure."""
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for table in page.extract_tables() or []:
                rows = [" | ".join(c.strip() if c else "" for c in row) for row in table]
                text += "\n[TABLE]\n" + "\n".join(rows)
            pages.append({"page": i, "text": text.strip()})

    usable = [p for p in pages if len(p["text"]) >= config.MIN_PAGE_CHARS]
    if len(usable) < max(1, len(pages) // 4):
        raise ScannedPDFError(
            "Most pages have no text layer, so this looks like a scanned PDF. "
            "Run it through a local OCR tool first (e.g. `ocrmypdf in.pdf out.pdf`)."
        )
    return pages


def chunk_pages(pages: list[dict], max_chars: int = config.CHUNK_CHARS) -> list[str]:
    """Group consecutive pages into chunks of about max_chars. Every page is
    labelled '=== PAGE n ===' so the model can cite page numbers."""
    chunks, current = [], ""
    for p in pages:
        if len(p["text"]) < config.MIN_PAGE_CHARS:
            continue
        block = f"=== PAGE {p['page']} ===\n{p['text'][:max_chars]}\n"
        if current and len(current) + len(block) > max_chars:
            chunks.append(current)
            current = ""
        current += block
    if current:
        chunks.append(current)
    return chunks
