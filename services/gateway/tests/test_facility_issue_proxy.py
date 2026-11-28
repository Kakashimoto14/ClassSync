"""Gateway facility issue routes: Teachers report, only Administrators change status."""

from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from services.gateway.app import main

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}
BASE = "/api/v1/timetables/issues"


@pytest.fixture
def forwarded(monkeypatch):
    calls = []

    async def proxy(service, path, request):
        calls.append((service, request.method, path))
        return JSONResponse({"data": {"ok": True}})

    monkeypatch.setattr(main, "service_proxy", proxy)
    return calls


def _send(method, path):
    return TestClient(main.app).request(
        method, path, headers=HEADERS, json=None if method == "GET" else {}
    )


@pytest.mark.parametrize(
    ("role", "method"), [("teacher", "POST"), ("teacher", "GET"), ("administrator", "GET")]
)
def test_report_and_list_are_forwarded(identity_adapters, forwarded, role, method):
    identity_adapters(main, role)
    assert _send(method, BASE).status_code == 200
    assert forwarded == [("scheduling", method, BASE)]


@pytest.mark.parametrize("role", ["student", "administrator"])
def test_only_teachers_submit_reports(identity_adapters, forwarded, role):
    identity_adapters(main, role)
    assert _send("POST", BASE).status_code == 403
    assert forwarded == []


def test_administrator_transition_is_forwarded(identity_adapters, forwarded):
    identity_adapters(main, "administrator")
    path = f"{BASE}/{uuid4()}/transition"
    assert _send("POST", path).status_code == 200
    assert forwarded == [("scheduling", "POST", path)]


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_non_administrators_never_transition(identity_adapters, forwarded, role):
    identity_adapters(main, role)
    assert _send("POST", f"{BASE}/{uuid4()}/transition").status_code == 403
    assert forwarded == []
