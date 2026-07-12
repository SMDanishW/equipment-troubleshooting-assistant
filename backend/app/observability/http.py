import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.logging import LOGGER_NAME, request_id_context

REQUEST_ID_HEADER = b"x-request-id"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _request_id_from_scope(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == REQUEST_ID_HEADER:
            candidate = value.decode("latin-1").strip()
            if REQUEST_ID_PATTERN.fullmatch(candidate):
                return candidate
            break
    return str(uuid4())


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = logging.getLogger(LOGGER_NAME)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id_from_scope(scope)
        token = request_id_context.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started_at = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            self.logger.exception(
                "request_failed",
                extra=self._log_context(scope, request_id, status_code, started_at),
            )
            raise
        else:
            self.logger.info(
                "request_completed",
                extra=self._log_context(scope, request_id, status_code, started_at),
            )
        finally:
            request_id_context.reset(token)

    @staticmethod
    def _log_context(scope: Scope, request_id: str, status_code: int, started_at: float) -> dict[str, object]:
        client = scope.get("client")
        return {
            "request_id": request_id,
            "http_method": scope.get("method", ""),
            "http_path": scope.get("path", ""),
            "http_status": status_code,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "client_ip": client[0] if client else None,
        }
