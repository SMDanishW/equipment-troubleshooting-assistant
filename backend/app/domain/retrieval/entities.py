from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VectorHit:
    id: str
    document: str
    metadata: dict[str, Any]
    distance: float | int | None


@dataclass(frozen=True)
class LexicalHit:
    id: str
    chunk_id: str
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    text_evidence: list[dict[str, Any]]
    image_evidence: list[dict[str, Any]]
