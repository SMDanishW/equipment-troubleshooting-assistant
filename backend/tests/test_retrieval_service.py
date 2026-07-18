from types import SimpleNamespace

from app.application.retrieval.service import RetrievalApplicationService
from app.domain.retrieval.entities import LexicalHit, VectorHit


class FakeVectorStore:
    def __init__(self) -> None:
        self.text_upsert = None
        self.image_upsert = None
        self.text_hits: list[VectorHit] = []
        self.image_hits: list[VectorHit] = []
        self.deleted = None

    def upsert_texts(self, ids, documents, metadatas) -> None:
        self.text_upsert = (ids, documents, metadatas)

    def upsert_images(self, ids, documents, metadatas) -> None:
        self.image_upsert = (ids, documents, metadatas)

    def search_texts(self, user_id, query, top_k, document_ids=None):
        return self.text_hits[:top_k]

    def search_images(self, user_id, query, top_k, document_ids=None):
        return self.image_hits[:top_k]

    def delete_document(self, user_id, document_id) -> None:
        self.deleted = (user_id, document_id)


class FakeEvidenceRepository:
    def __init__(self, *, chunks=None, images=None) -> None:
        self.chunks = chunks or {}
        self.images = images or {}

    def get_text_chunk(self, chunk_id):
        return self.chunks.get(chunk_id)

    def get_image(self, image_id):
        return self.images.get(image_id)


class FakeLexicalRetriever:
    def __init__(self, hits=None):
        self.hits = hits or []
        self.calls = []

    def search_texts(self, user_id, query, top_k, document_ids=None):
        self.calls.append((user_id, query, top_k, document_ids))
        return self.hits[:top_k]


def test_index_document_builds_tenant_scoped_vector_metadata():
    store = FakeVectorStore()
    service = RetrievalApplicationService(vector_store=store)
    document = SimpleNamespace(
        id="document-1",
        user_id="user-1",
        filename="manual.pdf",
        equipment_name="Welder",
        document_type="manual",
    )
    chunk = SimpleNamespace(id="chunk-1", content="Safety procedure", page_start=2, page_end=3, chunk_index=0)
    image = SimpleNamespace(
        id="image-1",
        caption="Wiring diagram",
        nearby_text="Connect the cable",
        page=4,
        filename="diagram.png",
        image_path="/data/diagram.png",
    )

    service.index_document(document, [chunk], [image])

    assert store.text_upsert[0] == ["txt_chunk-1"]
    assert store.text_upsert[2][0]["user_id"] == "user-1"
    assert store.text_upsert[2][0]["document_id"] == "document-1"
    assert store.image_upsert[0] == ["img_image-1"]
    assert store.image_upsert[2][0]["user_id"] == "user-1"


def test_search_revalidates_tenant_and_document_ownership():
    store = FakeVectorStore()
    own_document = SimpleNamespace(id="document-1", user_id="user-1", filename="manual.pdf")
    foreign_document = SimpleNamespace(id="document-2", user_id="user-2", filename="other.pdf")
    own_chunk = SimpleNamespace(
        id="chunk-1",
        document_id="document-1",
        document=own_document,
        page_start=2,
        page_end=2,
        content="Supported procedure",
    )
    foreign_chunk = SimpleNamespace(
        id="chunk-2",
        document_id="document-2",
        document=foreign_document,
        page_start=9,
        page_end=9,
        content="Foreign procedure",
    )
    store.text_hits = [
        VectorHit("txt_chunk-1", "Supported procedure", {"chunk_id": "chunk-1", "source_file": "manual.pdf"}, 0.25),
        VectorHit("txt_chunk-2", "Foreign procedure", {"chunk_id": "chunk-2", "source_file": "other.pdf"}, 0.1),
    ]
    repository = FakeEvidenceRepository(chunks={"chunk-1": own_chunk, "chunk-2": foreign_chunk})
    service = RetrievalApplicationService(vector_store=store, evidence_repository=repository)

    result = service.search(
        user_id="user-1",
        query="procedure",
        top_k_text=5,
        top_k_images=0,
        document_ids=["document-1"],
    )

    assert [item["id"] for item in result.text_evidence] == ["txt_chunk-1"]
    assert result.text_evidence[0]["score"] == 0.8


def test_hybrid_search_fuses_vector_and_lexical_ranks():
    store = FakeVectorStore()
    document = SimpleNamespace(id="document-1", user_id="user-1", filename="manual.pdf")
    chunks = {
        chunk_id: SimpleNamespace(
            id=chunk_id,
            document_id="document-1",
            document=document,
            page_start=index,
            page_end=index,
            content=f"Evidence {chunk_id}",
        )
        for index, chunk_id in enumerate(("vector-only", "shared", "lexical-only"), start=1)
    }
    store.text_hits = [
        VectorHit("txt_vector-only", "", {"chunk_id": "vector-only", "source_file": "manual.pdf"}, 0.1),
        VectorHit("txt_shared", "", {"chunk_id": "shared", "source_file": "manual.pdf"}, 0.2),
    ]
    lexical = FakeLexicalRetriever(
        [
            LexicalHit("txt_shared", "shared", 5.0),
            LexicalHit("txt_lexical-only", "lexical-only", 4.0),
        ]
    )
    service = RetrievalApplicationService(
        vector_store=store,
        evidence_repository=FakeEvidenceRepository(chunks=chunks),
        lexical_retriever=lexical,
        retrieval_mode="hybrid",
        candidate_multiplier=2,
        reciprocal_rank_fusion_k=60,
    )

    result = service.search(
        user_id="user-1",
        query="E102",
        top_k_text=3,
        top_k_images=0,
        document_ids=["document-1"],
    )

    assert [item["chunk_id"] for item in result.text_evidence] == [
        "shared",
        "vector-only",
        "lexical-only",
    ]
    assert result.text_evidence[0]["score"] > result.text_evidence[1]["score"]
    assert lexical.calls == [("user-1", "E102", 6, ["document-1"])]


def test_vector_mode_does_not_call_lexical_retriever():
    store = FakeVectorStore()
    document = SimpleNamespace(id="document-1", user_id="user-1", filename="manual.pdf")
    chunk = SimpleNamespace(
        id="chunk-1",
        document_id="document-1",
        document=document,
        page_start=1,
        page_end=1,
        content="Vector evidence",
    )
    store.text_hits = [
        VectorHit("txt_chunk-1", "", {"chunk_id": "chunk-1", "source_file": "manual.pdf"}, 0.25)
    ]
    lexical = FakeLexicalRetriever([LexicalHit("txt_other", "other", 10.0)])
    service = RetrievalApplicationService(
        vector_store=store,
        evidence_repository=FakeEvidenceRepository(chunks={"chunk-1": chunk}),
        lexical_retriever=lexical,
        retrieval_mode="vector",
    )

    result = service.search(
        user_id="user-1",
        query="vector",
        top_k_text=1,
        top_k_images=0,
    )

    assert result.text_evidence[0]["chunk_id"] == "chunk-1"
    assert lexical.calls == []


def test_delete_document_delegates_to_vector_store():
    store = FakeVectorStore()
    service = RetrievalApplicationService(vector_store=store)

    service.delete_document("user-1", "document-1")

    assert store.deleted == ("user-1", "document-1")
