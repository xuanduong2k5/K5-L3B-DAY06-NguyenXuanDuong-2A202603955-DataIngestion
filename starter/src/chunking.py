"""Fixed-window and paragraph-aware chunking."""
import hashlib
import re

from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, index: int, text: str) -> Chunk:
    stable_id = hashlib.sha256(
        f"{page.document_id}\0{page.page}\0{index}\0{text}".encode("utf-8")
    ).hexdigest()
    return Chunk(
        chunk_id=stable_id,
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata=dict(page.metadata),
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("size must be positive and overlap must be in [0, size)")
    chunks = []
    start = 0
    while start < len(page.text):
        end = min(start + size, len(page.text))
        text = page.text[start:end].strip()
        if text:
            chunks.append(_chunk(page, len(chunks), text))
        if end == len(page.text):
            break
        start = end - overlap
    return chunks


def _split_oversized(text: str, max_size: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if len(sentences) == 1:
        words = text.split()
        pieces = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) > max_size and current:
                pieces.append(current)
                current = word
            else:
                current = candidate
        if current:
            pieces.append(current)
        return pieces

    pieces = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_size:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_oversized(sentence, max_size))
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) > max_size and current:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", page.text) if part.strip()]
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    current = ""
    for paragraph in paragraphs:
        pieces = _split_oversized(paragraph, max_size) if len(paragraph) > max_size else [paragraph]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}".strip()
            if len(candidate) > max_size and current:
                chunks.append(_chunk(page, len(chunks), current))
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(_chunk(page, len(chunks), current))
    return chunks
