import json
from collections.abc import Iterable, Iterator
from typing import Any


def sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def chunk_text(text: str, chunk_size: int = 80) -> Iterable[str]:
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]


def stream_with_error_boundary(events: Iterable[str]) -> Iterator[str]:
    try:
        yield from events
    except Exception:
        yield sse_event("error", {"message": "The response stream ended unexpectedly."})
