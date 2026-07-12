import json
import logging

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.observability.http import RequestContextMiddleware
from app.observability.logging import LOGGER_NAME, JsonFormatter, configure_logging


def make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/probe")
    def probe(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    return TestClient(app)


def test_request_id_is_propagated_to_response_and_request_state():
    response = make_client().get("/probe", headers={"X-Request-ID": "client-request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-request-123"
    assert response.json() == {"request_id": "client-request-123"}


def test_invalid_request_id_is_replaced():
    response = make_client().get("/probe", headers={"X-Request-ID": "unsafe request id"})

    generated = response.headers["X-Request-ID"]
    assert generated != "unsafe request id"
    assert response.json() == {"request_id": generated}


def test_json_formatter_emits_machine_readable_request_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name=LOGGER_NAME,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-1"
    record.http_status = 200
    record.duration_ms = 12.5

    payload = json.loads(formatter.format(record))

    assert payload["event"] == "request_completed"
    assert payload["request_id"] == "request-1"
    assert payload["http_status"] == 200
    assert payload["duration_ms"] == 12.5


def test_configure_logging_does_not_duplicate_handlers():
    logger = configure_logging("INFO", "json")
    configure_logging("INFO", "json")

    assert len(logger.handlers) == 1
