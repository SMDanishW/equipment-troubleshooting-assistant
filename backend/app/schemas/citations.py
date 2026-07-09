from pydantic import BaseModel


class CitationRead(BaseModel):
    id: str
    type: str
    source_file: str
    document_id: str
    page: int
    page_end: int | None = None
    excerpt: str | None = None
    image_url: str | None = None
    pdf_url: str | None = None
    highlighted_pdf_url: str | None = None
    caption: str | None = None
    related_text: str | None = None
    width: int | None = None
    height: int | None = None
