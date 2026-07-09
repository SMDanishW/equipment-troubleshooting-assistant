from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k_text: int = Field(default=5, ge=0, le=20)
    top_k_images: int = Field(default=3, ge=0, le=20)
    document_ids: list[str] | None = Field(default=None, max_length=50)


class TextEvidence(BaseModel):
    id: str
    chunk_id: str
    document_id: str
    source_file: str
    page_start: int
    page_end: int
    text: str
    score: float


class ImageEvidence(BaseModel):
    id: str
    image_id: str
    document_id: str
    source_file: str
    page: int
    image_path: str
    content_hash: str | None = None
    width: int | None = None
    height: int | None = None
    caption: str | None = None
    nearby_text: str | None = None
    score: float


class RetrievalResponse(BaseModel):
    query: str
    text_evidence: list[TextEvidence]
    image_evidence: list[ImageEvidence]
