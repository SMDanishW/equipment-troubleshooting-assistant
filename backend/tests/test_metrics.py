from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.metrics import HTTP_REQUESTS, MetricsMiddleware


def test_metrics_use_route_templates_instead_of_resource_ids():
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)

    @app.get("/documents/{document_id}")
    def document(document_id: str):
        return {"id": document_id}

    client = TestClient(app)
    client.get("/documents/first-id")
    client.get("/documents/second-id")

    samples = [
        sample
        for metric in HTTP_REQUESTS.collect()
        for sample in metric.samples
        if sample.name == "equipment_agent_http_requests_total"
        and sample.labels.get("route") == "/documents/{document_id}"
    ]
    assert samples
    assert all("first-id" not in sample.labels.values() for sample in samples)
    assert all("second-id" not in sample.labels.values() for sample in samples)
