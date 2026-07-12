from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.observability.metrics import refresh_ingestion_job_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics", include_in_schema=False)
def metrics(db: Session = Depends(get_db)) -> Response:
    if not settings.metrics_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics are disabled.")
    refresh_ingestion_job_metrics(db)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
