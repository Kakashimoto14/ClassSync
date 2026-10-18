import httpx
from fastapi.testclient import TestClient

from services.gateway.app import main


def test_stream_outage_returns_recoverable_service_status(monkeypatch):
    monkeypatch.setattr(main.settings, "classsync_env", "development")
    monkeypatch.setattr(main.settings, "enable_scheduling_sandbox", True)

    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError("Scheduling service offline")

    monkeypatch.setattr(httpx.AsyncClient, "send", unavailable)
    response = TestClient(main.app).get(
        "/api/v1/timetables/sandbox/events/period?start=2026-10-01&end=2026-10-31"
    )
    assert response.status_code == 503
    assert "reconnect later" in response.text
