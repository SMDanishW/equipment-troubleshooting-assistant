from sqlalchemy.orm import Session

from app.application.retrieval.service import RetrievalApplicationService
from app.config import settings
from app.infrastructure.bm25 import SqlAlchemyBm25Retriever
from app.infrastructure.repositories.evidence import SqlAlchemyEvidenceRepository
from app.rag.chroma_store import get_chroma_store


def build_retrieval_service(db: Session | None = None) -> RetrievalApplicationService:
    return RetrievalApplicationService(
        vector_store=get_chroma_store(),
        evidence_repository=SqlAlchemyEvidenceRepository(db) if db is not None else None,
        lexical_retriever=(
            SqlAlchemyBm25Retriever(db, candidate_limit=settings.lexical_candidate_limit)
            if db is not None and settings.retrieval_mode == "hybrid"
            else None
        ),
        retrieval_mode=settings.retrieval_mode,
        candidate_multiplier=settings.retrieval_candidate_multiplier,
        reciprocal_rank_fusion_k=settings.reciprocal_rank_fusion_k,
    )
