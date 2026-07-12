from fastapi import Response, status
from sqlalchemy.exc import OperationalError

from app.api.health import liveness, readiness


class HealthySession:
    def execute(self, _statement):
        return None


class UnavailableSession:
    def execute(self, _statement):
        raise OperationalError("SELECT 1", {}, RuntimeError("database unavailable"))


def test_liveness_does_not_depend_on_external_services():
    assert liveness() == {"status": "alive"}


def test_readiness_reports_database_health():
    response = Response()

    result = readiness(response=response, db=HealthySession())

    assert response.status_code == status.HTTP_200_OK
    assert result == {"status": "ready", "checks": {"database": "ok"}}


def test_readiness_returns_503_when_database_is_unavailable():
    response = Response()

    result = readiness(response=response, db=UnavailableSession())

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert result == {"status": "not_ready", "checks": {"database": "unavailable"}}
