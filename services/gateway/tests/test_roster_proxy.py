"""Gateway roster routes: Administrator-only forwarding to the Academic service."""

from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from services.gateway.app import main

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}


@pytest.fixture
def forwarded(monkeypatch):
    calls = []

    async def proxy(service, path, request):
        calls.append((service, request.method, path, dict(request.query_params)))
        return JSONResponse({"data": {"ok": True}})

    monkeypatch.setattr(main, "service_proxy", proxy)
    return calls


@pytest.mark.parametrize(
    ("method", "suffix"),
    [("GET", ""), ("POST", ""), ("PUT", "/26-00101"), ("DELETE", "/26-00101")],
)
def test_administrator_roster_operations_are_forwarded(
    identity_adapters, forwarded, method, suffix
):
    identity_adapters(main, "administrator")
    period = uuid4()
    response = TestClient(main.app).request(
        method,
        f"/api/v1/academic/periods/{period}/roster{suffix}?limit=20",
        headers=HEADERS,
        json=None if method in {"GET", "DELETE"} else {"student_id": "26-00101"},
    )
    assert response.status_code == 200
    assert forwarded == [
        ("academic", method, f"/api/v1/academic/periods/{period}/roster{suffix}", {"limit": "20"})
    ]


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_non_administrators_never_reach_the_roster(identity_adapters, forwarded, role):
    identity_adapters(main, role)
    client = TestClient(main.app)
    period = uuid4()
    roster = f"/api/v1/academic/periods/{period}/roster"
    assert client.get(roster, headers=HEADERS).status_code == 403
    assert (
        client.delete(
            f"/api/v1/academic/periods/{period}/roster/26-00101", headers=HEADERS
        ).status_code
        == 403
    )
    assert forwarded == []


def test_anonymous_roster_access_is_denied(identity_adapters, forwarded):
    identity_adapters(main, "administrator")
    response = TestClient(main.app).get(f"/api/v1/academic/periods/{uuid4()}/roster")
    assert response.status_code == 401
    assert forwarded == []


@pytest.mark.parametrize("student_id", ["..%2Fsecrets", "2600101", "26-001011", "ab-00101"])
def test_malformed_roster_targets_are_rejected_before_forwarding(
    identity_adapters, forwarded, student_id
):
    identity_adapters(main, "administrator")
    response = TestClient(main.app).put(
        f"/api/v1/academic/periods/{uuid4()}/roster/{student_id}", headers=HEADERS, json={}
    )
    assert response.status_code in {404, 422}
    assert forwarded == []
