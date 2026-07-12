from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb

from app.config import settings
from app.rag.embeddings import get_embedding_provider

TEXT_COLLECTION = "equipment_text_chunks"
IMAGE_COLLECTION = "equipment_image_refs"


class ChromaStore:
    def __init__(self, persist_dir: str | None = None) -> None:
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.embedding_provider = get_embedding_provider()
        self.text_collection = self.client.get_or_create_collection(TEXT_COLLECTION)
        self.image_collection = self.client.get_or_create_collection(IMAGE_COLLECTION)

    def reset(self) -> None:
        for name in (TEXT_COLLECTION, IMAGE_COLLECTION):
            try:
                self.client.delete_collection(name)
            except Exception:
                pass
        self.text_collection = self.client.get_or_create_collection(TEXT_COLLECTION)
        self.image_collection = self.client.get_or_create_collection(IMAGE_COLLECTION)

    def upsert_texts(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        if not ids:
            return
        self.text_collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=self.embedding_provider.embed_documents(documents),
        )

    def upsert_images(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        if not ids:
            return
        self.image_collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=self.embedding_provider.embed_documents(documents),
        )

    def search_texts(
        self,
        user_id: str,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._search(self.text_collection, user_id, query, top_k, document_ids)

    def search_images(
        self,
        user_id: str,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        return self._search(self.image_collection, user_id, query, top_k, document_ids)

    def delete_document(self, user_id: str, document_id: str) -> None:
        where = {"$and": [{"user_id": user_id}, {"document_id": document_id}]}
        for collection in (self.text_collection, self.image_collection):
            try:
                collection.delete(where=where)
            except Exception:
                try:
                    collection.delete(where={"document_id": document_id})
                except Exception as fallback_error:
                    raise RuntimeError(f"Unable to remove vector evidence for document {document_id}.") from fallback_error

    def _search(
        self,
        collection: Any,
        user_id: str,
        query: str,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if top_k <= 0:
            return []
        result = collection.query(
            query_embeddings=self.embedding_provider.embed_query(query),
            n_results=top_k,
            where=self._where(user_id, document_ids),
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        rows: list[dict[str, Any]] = []
        for index, item_id in enumerate(ids):
            rows.append(
                {
                    "id": item_id,
                    "document": documents[index],
                    "metadata": metadatas[index],
                    "distance": distances[index],
                }
            )
        return rows

    def _where(self, user_id: str, document_ids: list[str] | None = None) -> dict[str, Any]:
        filtered_document_ids = [document_id for document_id in document_ids or [] if document_id]
        if not filtered_document_ids:
            return {"user_id": user_id}
        return {"$and": [{"user_id": user_id}, {"document_id": {"$in": filtered_document_ids}}]}


@lru_cache
def get_chroma_store() -> ChromaStore:
    return ChromaStore()
