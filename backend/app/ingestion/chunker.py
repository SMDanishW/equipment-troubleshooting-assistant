from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TextChunk:
    text: str
    page_start: int
    page_end: int
    chunk_index: int


def normalize_pdf_text(text: str) -> str:
    cleaned = text.replace("\x00", " ")
    cleaned = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", cleaned)
    lines = [line.strip() for line in cleaned.splitlines()]
    return re.sub(r"\s+", " ", " ".join(line for line in lines if line)).strip()


def chunk_pages(pages: list[tuple[int, str]], chunk_size: int = 1200, overlap: int = 180) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    current = ""
    page_start = 0
    page_end = 0

    for page_number, raw_text in pages:
        text = normalize_pdf_text(raw_text)
        if not text:
            continue
        if not current:
            page_start = page_number
        page_end = page_number
        current = f"{current} {text}".strip()

        while len(current) >= chunk_size:
            split_at = _find_split_boundary(current, chunk_size)
            chunk_text = current[:split_at].strip()
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    page_start=page_start,
                    page_end=page_end,
                    chunk_index=len(chunks),
                )
            )
            current = current[_find_overlap_boundary(current, split_at, overlap) :].strip()
            page_start = page_number

    if current:
        chunks.append(TextChunk(text=current, page_start=page_start, page_end=page_end, chunk_index=len(chunks)))

    return chunks


def _find_split_boundary(text: str, target: int) -> int:
    if len(text) <= target:
        return len(text)
    boundary = text.rfind(" ", 0, target)
    if boundary >= int(target * 0.65):
        return boundary
    return target


def _find_overlap_boundary(text: str, split_at: int, overlap: int) -> int:
    start = max(0, split_at - overlap)
    if start == 0:
        return 0
    boundary = text.find(" ", start, split_at)
    if boundary != -1:
        return boundary + 1
    return start
