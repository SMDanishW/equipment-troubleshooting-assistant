from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.documents.entities import IngestionJobStatus
from app.models.ingestion_job import IngestionJob


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SqlAlchemyIngestionJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue(self, document_id: str, max_attempts: int) -> IngestionJob:
        job = IngestionJob(document_id=document_id, max_attempts=max_attempts)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def claim_next(self) -> IngestionJob | None:
        statement = (
            select(IngestionJob)
            .where(
                IngestionJob.status == IngestionJobStatus.QUEUED,
                IngestionJob.attempts < IngestionJob.max_attempts,
            )
            .order_by(IngestionJob.queued_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = self.db.execute(statement).scalar_one_or_none()
        if job is None:
            return None
        job.status = IngestionJobStatus.RUNNING
        job.attempts += 1
        job.started_at = utc_now()
        job.completed_at = None
        self.db.commit()
        self.db.refresh(job)
        return job

    def succeed(self, job: IngestionJob) -> None:
        job.status = IngestionJobStatus.SUCCEEDED
        job.error_message = None
        job.completed_at = utc_now()
        self.db.commit()

    def fail_or_requeue(self, job: IngestionJob, error: Exception) -> bool:
        exhausted = job.attempts >= job.max_attempts
        job.status = IngestionJobStatus.FAILED if exhausted else IngestionJobStatus.QUEUED
        job.error_message = str(error)[:4000]
        job.completed_at = utc_now() if exhausted else None
        job.started_at = None if not exhausted else job.started_at
        self.db.commit()
        return exhausted

    def recover_stale(self, timeout_minutes: int) -> int:
        cutoff = utc_now() - timedelta(minutes=timeout_minutes)
        jobs = list(
            self.db.execute(
                select(IngestionJob).where(
                    IngestionJob.status == IngestionJobStatus.RUNNING,
                    IngestionJob.started_at < cutoff,
                )
            ).scalars()
        )
        for job in jobs:
            job.status = IngestionJobStatus.QUEUED
            job.started_at = None
            job.error_message = "Recovered after worker timeout."
        self.db.commit()
        return len(jobs)
