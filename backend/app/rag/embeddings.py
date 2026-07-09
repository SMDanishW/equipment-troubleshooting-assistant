from collections import Counter
from hashlib import sha256
from math import sqrt
from typing import Protocol

from app.config import settings


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[list[float]]:
        ...


class HashingEmbeddingProvider:
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[list[float]]:
        return [self._embed(text)]

    def _embed(self, text: str) -> list[float]:
        tokens = [token.lower() for token in text.replace("_", " ").split() if token.strip()]
        counts = Counter(tokens)
        vector = [0.0] * self.dimensions
        for token, count in counts.items():
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * float(count)
        norm = sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class SentenceTransformerEmbeddingProvider:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[list[float]]:
        return self.embed_documents([text])


def get_embedding_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "sentence_transformers":
        try:
            return SentenceTransformerEmbeddingProvider(settings.embedding_model)
        except Exception:
            return HashingEmbeddingProvider(settings.hashing_embedding_dimensions)
    return HashingEmbeddingProvider(settings.hashing_embedding_dimensions)

