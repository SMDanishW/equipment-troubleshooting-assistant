from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HTTP_REQUESTS = Counter(
    "equipment_agent_http_requests_total",
    "HTTP requests completed by the API.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "equipment_agent_http_request_duration_seconds",
    "HTTP response duration including streaming bodies.",
    ("method", "route"),
)
INGESTION_JOBS = Gauge(
    "equipment_agent_ingestion_jobs",
    "Durable ingestion jobs by current state.",
    ("status",),
)


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        status_code = 500
        started_at = perf_counter()

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            route = scope.get("route")
            route_name = getattr(route, "path", None) or "unmatched"
            method = scope.get("method", "UNKNOWN")
            HTTP_REQUESTS.labels(method=method, route=route_name, status=str(status_code)).inc()
            HTTP_DURATION.labels(method=method, route=route_name).observe(perf_counter() - started_at)


def refresh_ingestion_job_metrics(db) -> None:
    from sqlalchemy import func, select

    from app.models.ingestion_job import IngestionJob

    counts = dict(db.execute(select(IngestionJob.status, func.count()).group_by(IngestionJob.status)).all())
    for status in ("queued", "running", "succeeded", "failed"):
        INGESTION_JOBS.labels(status=status).set(counts.get(status, 0))
