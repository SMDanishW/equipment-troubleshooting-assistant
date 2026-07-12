from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.documents.entities import DocumentStatus


class TextChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_index: int
    page_start: int
    page_end: int
    content: str


class DocumentImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    page: int
    filename: str
    image_path: str
    caption: str | None = None
    nearby_text: str | None = None
    width: int | None = None
    height: int | None = None
    bytes_size: int | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    equipment_name: str
    document_type: str
    page_count: int
    text_chunks_count: int
    images_extracted_count: int
    status: DocumentStatus
    error_message: str | None = None
    created_at: datetime


class DocumentUploadResponse(DocumentRead):
    pass


class DocumentDetail(DocumentRead):
    text_chunks: list[TextChunkRead]
    images: list[DocumentImageRead]
