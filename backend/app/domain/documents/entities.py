from enum import StrEnum


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class IngestionJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
