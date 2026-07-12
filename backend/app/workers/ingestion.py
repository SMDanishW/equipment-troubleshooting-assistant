import logging
from time import sleep

from app.config import settings
from app.database import SessionLocal
from app.infrastructure.repositories.ingestion_jobs import SqlAlchemyIngestionJobRepository
from app.ingestion.pipeline import process_staged_document
from app.observability.logging import configure_logging

logger = logging.getLogger("equipment_agent.ingestion_worker")


def process_next_job() -> bool:
    with SessionLocal() as db:
        repository = SqlAlchemyIngestionJobRepository(db)
        job = repository.claim_next()
        if job is None:
            return False
        try:
            process_staged_document(db, job.document_id, final_failure_cleanup=job.attempts >= job.max_attempts)
        except Exception as exc:
            exhausted = repository.fail_or_requeue(job, exc)
            logger.exception(
                "ingestion_job_failed",
                extra={"document_id": job.document_id, "job_id": job.id, "attempts": job.attempts},
            )
            return not exhausted
        repository.succeed(job)
        logger.info("ingestion_job_succeeded", extra={"document_id": job.document_id, "job_id": job.id})
        return True


def run() -> None:
    configure_logging(settings.log_level, settings.log_format)
    with SessionLocal() as db:
        recovered = SqlAlchemyIngestionJobRepository(db).recover_stale(settings.ingestion_job_timeout_minutes)
        if recovered:
            logger.warning("stale_ingestion_jobs_recovered", extra={"count": recovered})
    while True:
        if not process_next_job():
            sleep(settings.ingestion_poll_seconds)


if __name__ == "__main__":
    run()
