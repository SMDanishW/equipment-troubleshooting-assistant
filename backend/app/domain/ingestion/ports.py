from typing import Any, Protocol


class IngestionPipeline(Protocol):
    def stage(
        self,
        *,
        user: Any,
        upload: Any,
        equipment_name: str,
        document_type: str,
    ) -> Any: ...

    def process(self, document_id: str, *, final_failure_cleanup: bool) -> Any: ...
