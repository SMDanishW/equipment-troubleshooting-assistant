import re

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.documents.entities import DocumentStatus
from app.domain.retrieval.entities import LexicalHit
from app.models.document import Document, TextChunk

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*", re.IGNORECASE)


class SqlAlchemyBm25Retriever:
    def __init__(self, db: Session, *, candidate_limit: int) -> None:
        self.db = db
        self.candidate_limit = candidate_limit

    def search_texts(
        self,
        user_id: str,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[LexicalHit]:
        query_tokens = tokenize(query)
        if not query_tokens or top_k <= 0:
            return []

        statement = (
            select(TextChunk)
            .join(TextChunk.document)
            .where(
                Document.user_id == user_id,
                Document.status == DocumentStatus.INDEXED,
            )
            .order_by(TextChunk.created_at.desc())
            .limit(self.candidate_limit)
        )
        filtered_ids = [document_id for document_id in document_ids or [] if document_id]
        if filtered_ids:
            statement = statement.where(TextChunk.document_id.in_(filtered_ids))

        candidates = [
            (chunk, tokenize(chunk.content))
            for chunk in self.db.execute(statement).scalars().all()
        ]
        query_token_set = set(query_tokens)
        candidates = [
            (chunk, tokens)
            for chunk, tokens in candidates
            if query_token_set.intersection(tokens)
        ]
        if not candidates:
            return []

        chunks = [chunk for chunk, _ in candidates]
        corpus = [tokens for _, tokens in candidates]
        scores = BM25Okapi(corpus).get_scores(query_tokens)
        ranked = sorted(
            (
                LexicalHit(id=f"txt_{chunk.id}", chunk_id=chunk.id, score=float(score))
                for chunk, score in zip(chunks, scores, strict=True)
            ),
            key=lambda hit: (-hit.score, hit.id),
        )
        return ranked[:top_k]


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
