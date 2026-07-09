from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.rag.retriever import retrieve_evidence
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalResponse)
def search(
    payload: RetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RetrievalResponse:
    return retrieve_evidence(
        db=db,
        user_id=current_user.id,
        query=payload.query,
        top_k_text=payload.top_k_text,
        top_k_images=payload.top_k_images,
        document_ids=payload.document_ids,
    )
