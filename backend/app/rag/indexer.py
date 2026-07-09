from app.models.document import Document, DocumentImage, TextChunk
from app.rag.chroma_store import get_chroma_store


def index_document_evidence(document: Document, chunks: list[TextChunk], images: list[DocumentImage]) -> None:
    store = get_chroma_store()

    text_ids = [f"txt_{chunk.id}" for chunk in chunks]
    text_documents = [chunk.content for chunk in chunks]
    text_metadatas = [
        {
            "type": "text",
            "user_id": document.user_id,
            "document_id": document.id,
            "chunk_id": chunk.id,
            "source_file": document.filename,
            "equipment_name": document.equipment_name,
            "document_type": document.document_type,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "chunk_index": chunk.chunk_index,
        }
        for chunk in chunks
    ]
    store.upsert_texts(text_ids, text_documents, text_metadatas)

    image_ids = [f"img_{image.id}" for image in images]
    image_documents = [
        " ".join(
            part
            for part in [
                image.caption,
                image.nearby_text,
                document.equipment_name,
                document.filename,
                f"page {image.page}",
            ]
            if part
        )
        for image in images
    ]
    image_metadatas = [
        {
            "type": "image",
            "user_id": document.user_id,
            "document_id": document.id,
            "image_id": image.id,
            "source_file": document.filename,
            "equipment_name": document.equipment_name,
            "document_type": document.document_type,
            "page": image.page,
            "filename": image.filename,
            "image_path": image.image_path,
        }
        for image in images
    ]
    store.upsert_images(image_ids, image_documents, image_metadatas)

