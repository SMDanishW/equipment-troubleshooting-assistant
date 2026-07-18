from typing import Any, Protocol

from app.domain.retrieval.entities import LexicalHit, VectorHit


class VectorStore(Protocol):
    def upsert_texts(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None: ...

    def upsert_images(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None: ...

    def search_texts(
        self,
        user_id: str,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[VectorHit]: ...

    def search_images(
        self,
        user_id: str,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[VectorHit]: ...

    def delete_document(self, user_id: str, document_id: str) -> None: ...


class EvidenceRepository(Protocol):
    def get_text_chunk(self, chunk_id: str) -> Any | None: ...

    def get_image(self, image_id: str) -> Any | None: ...


class LexicalRetriever(Protocol):
    def search_texts(
        self,
        user_id: str,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[LexicalHit]: ...
