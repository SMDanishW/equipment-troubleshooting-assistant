from collections.abc import Iterable

from fastapi.responses import StreamingResponse

from app.streaming.sse import stream_with_error_boundary

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_response(events: Iterable[str]) -> StreamingResponse:
    return StreamingResponse(
        stream_with_error_boundary(events),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
