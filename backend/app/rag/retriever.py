from sqlalchemy.orm import Session

from app.infrastructure.retrieval import build_retrieval_service
from app.schemas.retrieval import ImageEvidence, RetrievalResponse, TextEvidence


def retrieve_evidence(
    db: Session,
    user_id: str,
    query: str,
    top_k_text: int,
    top_k_images: int,
    document_ids: list[str] | None = None,
) -> RetrievalResponse:
    result = build_retrieval_service(db).search(
        user_id=user_id,
        query=query,
        top_k_text=top_k_text,
        top_k_images=top_k_images,
        document_ids=document_ids,
    )
    return RetrievalResponse(
        query=result.query,
        text_evidence=[TextEvidence(**item) for item in result.text_evidence],
        image_evidence=[ImageEvidence(**item) for item in result.image_evidence],
    )
