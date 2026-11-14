"""Read, normalize and trace source pages."""
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).strip()


def load_pdf(
    path: Path,
    document_id: str,
    source: str,
    included_pages: set[int],
    section_ranges: list[dict[str, object]],
) -> list[DocumentPage]:
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    for physical_page, pdf_page in enumerate(reader.pages, start=1):
        if physical_page not in included_pages:
            continue
        text = pdf_page.extract_text() or ""
        if physical_page == 1 and "Contents" in text:
            text = text.split("Contents", maxsplit=1)[0]
        text = normalize_text(text)
        if not text:
            raise ValueError(
                f"Physical page {physical_page} has no extractable text; OCR or a readable source is required"
            )
        section = next(
            (
                str(item["section"])
                for item in section_ranges
                if int(item["start_page"]) <= physical_page <= int(item["end_page"])
            ),
            None,
        )
        if section is None:
            raise ValueError(f"No section metadata for physical page {physical_page}")
        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=physical_page,
                text=text,
                metadata={"section": section},
            )
        )
    return pages
