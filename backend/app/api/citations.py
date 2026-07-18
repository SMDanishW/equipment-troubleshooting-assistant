from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import pdfplumber
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject

from app.api.deps import get_current_user
from app.database import get_db
from app.infrastructure.storage.factory import build_artifact_store
from app.models.document import Document, DocumentImage, TextChunk
from app.models.user import User
from app.schemas.citations import CitationRead

router = APIRouter(tags=["citations"])


@router.get("/citations/{citation_id}", response_model=CitationRead)
def get_citation(
    citation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CitationRead:
    citation_type, entity_id = _split_citation_id(citation_id)
    if citation_type == "text":
        chunk = db.get(TextChunk, entity_id)
        if not chunk or chunk.document.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Citation not found.")
        return CitationRead(
            id=citation_id,
            type="text",
            source_file=chunk.document.filename,
            document_id=chunk.document_id,
            page=chunk.page_start,
            page_end=chunk.page_end,
            excerpt=chunk.content,
            pdf_url=f"/files/pdfs/{chunk.document_id}?page={chunk.page_start}",
            highlighted_pdf_url=f"/citations/{citation_id}/highlighted-pdf",
        )

    image = db.get(DocumentImage, entity_id)
    if not image or image.document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Citation not found.")
    return CitationRead(
        id=citation_id,
        type="image",
        source_file=image.document.filename,
        document_id=image.document_id,
        page=image.page,
        page_end=image.page,
        image_url=f"/files/images/{image.id}",
        pdf_url=f"/files/pdfs/{image.document_id}?page={image.page}",
        caption=image.caption,
        related_text=image.nearby_text,
        width=image.width,
        height=image.height,
    )


@router.get("/files/images/{image_id}")
def get_image_file(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    normalized_id = image_id.removeprefix("img_")
    image = db.get(DocumentImage, normalized_id)
    if not image or image.document.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")

    image_path = build_artifact_store().resolve(image.image_path)
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found.")
    return FileResponse(image_path)


@router.get("/files/pdfs/{document_id}")
def get_pdf_file(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    document = db.get(Document, document_id)
    if not document or document.user_id != current_user.id or not document.storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not found.")
    pdf_path = build_artifact_store().resolve(document.storage_path)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found.")
    return FileResponse(pdf_path, media_type="application/pdf", filename=document.filename)


@router.get("/citations/{citation_id}/highlighted-pdf")
def get_highlighted_citation_pdf(
    citation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    citation_type, entity_id = _split_citation_id(citation_id)
    if citation_type != "text":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only text citations can be highlighted.")

    chunk = db.get(TextChunk, entity_id)
    if not chunk or chunk.document.user_id != current_user.id or not chunk.document.storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Citation not found.")
    pdf_path = build_artifact_store().resolve(chunk.document.storage_path)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found.")

    output_path = _build_highlighted_single_page_pdf(pdf_path, chunk.page_start, chunk.content)
    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"{chunk.document.filename}-page-{chunk.page_start}-highlight.pdf",
    )


def _split_citation_id(citation_id: str) -> tuple[str, str]:
    if citation_id.startswith("txt_"):
        return "text", citation_id.removeprefix("txt_")
    if citation_id.startswith("img_"):
        return "image", citation_id.removeprefix("img_")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown citation ID format.")


def _build_highlighted_single_page_pdf(pdf_path: Path, page_number: int, excerpt: str) -> str:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    source_page = reader.pages[page_number - 1]
    writer.add_page(source_page)

    rect = _find_highlight_rect(pdf_path, page_number, excerpt)
    if rect:
        annotation = Highlight(
            rect=rect,
            quad_points=ArrayObject(
                [
                    FloatObject(rect[0]),
                    FloatObject(rect[3]),
                    FloatObject(rect[2]),
                    FloatObject(rect[3]),
                    FloatObject(rect[0]),
                    FloatObject(rect[1]),
                    FloatObject(rect[2]),
                    FloatObject(rect[1]),
                ]
            ),
            highlight_color="ffe066",
            printing=True,
        )
        writer.add_annotation(page_number=0, annotation=annotation)

    output = NamedTemporaryFile(delete=False, suffix=".pdf")
    with output:
        writer.write(output)
    return output.name


def _find_highlight_rect(pdf_path: Path, page_number: int, excerpt: str) -> tuple[float, float, float, float] | None:
    phrases = _highlight_phrases(excerpt)
    if not phrases:
        return None
    with pdfplumber.open(str(pdf_path)) as pdf:
        page = pdf.pages[page_number - 1]
        page_height = float(page.height)
        for phrase in phrases:
            matches = page.search(phrase, regex=False, case=False, x_tolerance=2, y_tolerance=3)
            if matches:
                match = matches[0]
                return (
                    float(match["x0"]),
                    page_height - float(match["bottom"]),
                    float(match["x1"]),
                    page_height - float(match["top"]),
                )
    return None


def _highlight_phrases(excerpt: str) -> list[str]:
    normalized = " ".join(excerpt.split())
    sentences = re_split_sentences(normalized)
    phrases = []
    for sentence in sentences:
        if len(sentence) < 20:
            continue
        words = sentence.split()
        for size in (10, 8, 6, 4):
            if len(words) >= size:
                phrases.append(" ".join(words[:size]))
                break
    return phrases[:6]


def re_split_sentences(text: str) -> list[str]:
    import re

    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|(?<=[.!?])(?=[A-Z])", text) if part.strip()]
