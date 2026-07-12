import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

LOGGER_NAME = "equipment_agent"
request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_context.get()
        return True


class JsonFormatter(logging.Formatter):
    _extra_fields = (
        "request_id",
        "http_method",
        "http_path",
        "http_status",
        "duration_ms",
        "client_ip",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in self._extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_logging(level: str, log_format: str) -> logging.Logger:
    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger
