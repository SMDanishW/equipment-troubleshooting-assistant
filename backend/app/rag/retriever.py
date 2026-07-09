from sqlalchemy.orm import Session

from app.models.document import DocumentImage, TextChunk
from app.rag.chroma_store import get_chroma_store
from app.schemas.retrieval import ImageEvidence, RetrievalResponse, TextEvidence


def retrieve_evidence(
    db: Session,
    user_id: str,
    query: str,
    top_k_text: int,
    top_k_images: int,
    document_ids: list[str] | None = None,
) -> RetrievalResponse:
    store = get_chroma_store()
    selected_document_ids = set(document_ids or [])
    text_hits = store.search_texts(user_id=user_id, query=query, top_k=top_k_text, document_ids=document_ids)
    image_hits = store.search_images(user_id=user_id, query=query, top_k=top_k_images, document_ids=document_ids)

    text_evidence: list[TextEvidence] = []
    for hit in text_hits:
        metadata = hit["metadata"]
        chunk = db.get(TextChunk, metadata["chunk_id"])
        if not chunk or chunk.document.user_id != user_id:
            continue
        if selected_document_ids and chunk.document_id not in selected_document_ids:
            continue
        text_evidence.append(
            TextEvidence(
                id=hit["id"],
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                source_file=metadata["source_file"],
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                text=chunk.content,
                score=_distance_to_score(hit["distance"]),
            )
        )

    image_evidence: list[ImageEvidence] = []
    for hit in image_hits:
        metadata = hit["metadata"]
        image = db.get(DocumentImage, metadata["image_id"])
        if not image or image.document.user_id != user_id:
            continue
        if selected_document_ids and image.document_id not in selected_document_ids:
            continue
        image_evidence.append(
            ImageEvidence(
                id=hit["id"],
                image_id=image.id,
                document_id=image.document_id,
                source_file=metadata["source_file"],
                page=image.page,
                image_path=image.image_path,
                content_hash=image.content_hash,
                width=image.width,
                height=image.height,
                caption=image.caption,
                nearby_text=image.nearby_text,
                score=_distance_to_score(hit["distance"]),
            )
        )

    return RetrievalResponse(query=query, text_evidence=text_evidence, image_evidence=image_evidence)


def _distance_to_score(distance: float | int | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, 1.0 / (1.0 + float(distance)))
