from typing import Any

from app.domain.retrieval.entities import LexicalHit, RetrievalResult, VectorHit
from app.domain.retrieval.ports import EvidenceRepository, LexicalRetriever, VectorStore


class RetrievalApplicationService:
    def __init__(
        self,
        *,
        vector_store: VectorStore,
        evidence_repository: EvidenceRepository | None = None,
        lexical_retriever: LexicalRetriever | None = None,
        retrieval_mode: str = "vector",
        candidate_multiplier: int = 4,
        reciprocal_rank_fusion_k: int = 60,
    ) -> None:
        self.vector_store = vector_store
        self.evidence_repository = evidence_repository
        self.lexical_retriever = lexical_retriever
        self.retrieval_mode = retrieval_mode
        self.candidate_multiplier = candidate_multiplier
        self.reciprocal_rank_fusion_k = reciprocal_rank_fusion_k

    def index_document(self, document: Any, chunks: list[Any], images: list[Any]) -> None:
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
        self.vector_store.upsert_texts(text_ids, text_documents, text_metadatas)

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
        self.vector_store.upsert_images(image_ids, image_documents, image_metadatas)

    def search(
        self,
        *,
        user_id: str,
        query: str,
        top_k_text: int,
        top_k_images: int,
        document_ids: list[str] | None = None,
    ) -> RetrievalResult:
        if self.evidence_repository is None:
            raise RuntimeError("An evidence repository is required for retrieval.")
        selected_document_ids = set(document_ids or [])
        vector_limit = (
            top_k_text * self.candidate_multiplier
            if self.retrieval_mode == "hybrid" and self.lexical_retriever is not None
            else top_k_text
        )
        vector_text_hits = self.vector_store.search_texts(user_id, query, vector_limit, document_ids)
        lexical_hits = (
            self.lexical_retriever.search_texts(user_id, query, vector_limit, document_ids)
            if self.retrieval_mode == "hybrid" and self.lexical_retriever is not None
            else []
        )
        text_hits = _rank_text_hits(
            vector_hits=vector_text_hits,
            lexical_hits=lexical_hits,
            top_k=top_k_text,
            fusion_k=self.reciprocal_rank_fusion_k,
            hybrid=self.retrieval_mode == "hybrid" and self.lexical_retriever is not None,
        )
        image_hits = self.vector_store.search_images(user_id, query, top_k_images, document_ids)

        text_evidence = []
        for hit_id, chunk_id, score in text_hits:
            chunk = self.evidence_repository.get_text_chunk(chunk_id)
            if not chunk or chunk.document.user_id != user_id:
                continue
            if selected_document_ids and chunk.document_id not in selected_document_ids:
                continue
            text_evidence.append(
                {
                    "id": hit_id,
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "source_file": chunk.document.filename,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "text": chunk.content,
                    "score": score,
                }
            )

        image_evidence = []
        for hit in image_hits:
            image = self.evidence_repository.get_image(hit.metadata["image_id"])
            if not image or image.document.user_id != user_id:
                continue
            if selected_document_ids and image.document_id not in selected_document_ids:
                continue
            image_evidence.append(
                {
                    "id": hit.id,
                    "image_id": image.id,
                    "document_id": image.document_id,
                    "source_file": hit.metadata["source_file"],
                    "page": image.page,
                    "image_path": image.image_path,
                    "content_hash": image.content_hash,
                    "width": image.width,
                    "height": image.height,
                    "caption": image.caption,
                    "nearby_text": image.nearby_text,
                    "score": _distance_to_score(hit.distance),
                }
            )
        return RetrievalResult(query=query, text_evidence=text_evidence, image_evidence=image_evidence)

    def delete_document(self, user_id: str, document_id: str) -> None:
        self.vector_store.delete_document(user_id, document_id)


def _distance_to_score(distance: float | int | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, 1.0 / (1.0 + float(distance)))


def _rank_text_hits(
    *,
    vector_hits: list[VectorHit],
    lexical_hits: list[LexicalHit],
    top_k: int,
    fusion_k: int,
    hybrid: bool,
) -> list[tuple[str, str, float]]:
    if not hybrid:
        return [
            (hit.id, hit.metadata["chunk_id"], _distance_to_score(hit.distance))
            for hit in vector_hits[:top_k]
        ]

    chunk_ids: dict[str, str] = {
        hit.id: str(hit.metadata["chunk_id"])
        for hit in vector_hits
    }
    chunk_ids.update({hit.id: hit.chunk_id for hit in lexical_hits})
    fused_scores: dict[str, float] = {}
    for rank, hit in enumerate(vector_hits, start=1):
        fused_scores[hit.id] = fused_scores.get(hit.id, 0.0) + 1.0 / (fusion_k + rank)
    for rank, hit in enumerate(lexical_hits, start=1):
        fused_scores[hit.id] = fused_scores.get(hit.id, 0.0) + 1.0 / (fusion_k + rank)

    maximum_score = 2.0 / (fusion_k + 1)
    ranked_ids = sorted(fused_scores, key=lambda hit_id: (-fused_scores[hit_id], hit_id))
    return [
        (hit_id, chunk_ids[hit_id], min(1.0, fused_scores[hit_id] / maximum_score))
        for hit_id in ranked_ids[:top_k]
    ]
