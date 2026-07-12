import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.streaming.response import sse_response
from app.streaming.sse import sse_event


def parse_events(raw_stream: str) -> list[dict]:
    events = []
    for block in raw_stream.strip().split("\n\n"):
        fields = {}
        for line in block.splitlines():
            name, _, value = line.partition(": ")
            fields[name] = value
        if "event" in fields and "data" in fields:
            events.append({"event": fields["event"], "data": json.loads(fields["data"])})
    return events


def make_client(generator):
    app = FastAPI()

    @app.get("/stream")
    def stream():
        return sse_response(generator())

    return TestClient(app)


def test_sse_response_preserves_order_and_proxy_headers():
    def events():
        yield sse_event("token", {"content": "hello"})
        yield sse_event("done", {"conversation_id": "conversation-1"})

    response = make_client(events).get("/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert [event["event"] for event in parse_events(response.text)] == ["token", "done"]


def test_sse_response_emits_terminal_error_event_without_leaking_exception():
    def events():
        yield sse_event("agent_update", {"status": "running"})
        raise RuntimeError("secret internal failure")

    response = make_client(events).get("/stream")
    parsed = parse_events(response.text)

    assert [event["event"] for event in parsed] == ["agent_update", "error"]
    assert parsed[-1]["data"] == {"message": "The response stream ended unexpectedly."}
    assert "secret internal failure" not in response.text
