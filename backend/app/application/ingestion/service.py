from typing import Any

from app.domain.ingestion.ports import IngestionPipeline


class DocumentIngestionService:
    def __init__(self, pipeline: IngestionPipeline) -> None:
        self.pipeline = pipeline

    def stage(self, *, user: Any, upload: Any, equipment_name: str, document_type: str) -> Any:
        return self.pipeline.stage(
            user=user,
            upload=upload,
            equipment_name=equipment_name,
            document_type=document_type,
        )

    def ingest_inline(self, *, user: Any, upload: Any, equipment_name: str, document_type: str) -> Any:
        document = self.stage(
            user=user,
            upload=upload,
            equipment_name=equipment_name,
            document_type=document_type,
        )
        return self.pipeline.process(document.id, final_failure_cleanup=True)

    def process_queued(self, document_id: str, *, final_attempt: bool) -> Any:
        return self.pipeline.process(document_id, final_failure_cleanup=final_attempt)
