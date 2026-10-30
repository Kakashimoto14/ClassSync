"""PostgreSQL publication HTTP composition guards; storage remains qualified separately."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.scheduling.app import main
from services.scheduling.app import publication_api as api


def pg_settings():
    return main.Settings(
        _env_file=None,
        classsync_env="test",
        firebase_project_id="demo-publication",
        institutional_tenant_id="tenant-a",
        scheduling_database_transport="loopback-sspi-test",
        scheduling_database_url=SecretStr(
            "postgresql+psycopg://runtime@127.0.0.1:19999/postgres"
        ),
    )


def request(engine=None):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(scheduling_engine=engine))
    )


def test_postgres_publication_provider_binds_server_tenant_and_verified_uid(monkeypatch):
    from services.scheduling.app.postgres_publication_repository import (
        PostgresPublicationRepository,
    )

    settings = pg_settings()
    engine = object()
    monkeypatch.setattr(api, "settings_only", lambda: settings)
    _, repository = api.scoped_repo(
        request(engine), {"uid": "verified-admin", "tenant_id": "tenant-a"}
    )
    assert isinstance(repository, PostgresPublicationRepository)
    assert repository.engine is engine
    assert repository.keys == {"tenant": "tenant-a", "owner": "verified-admin"}


@pytest.mark.parametrize(
    ("claims", "engine", "status"),
    [
        ({"uid": "verified-admin", "tenant_id": "other-tenant"}, object(), 403),
        ({"uid": "verified-admin", "tenant_id": "tenant-a"}, None, 503),
    ],
)
def test_postgres_publication_provider_fails_closed_on_tenant_or_pool(
    monkeypatch, claims, engine, status
):
    monkeypatch.setattr(api, "settings_only", pg_settings)
    with pytest.raises(HTTPException) as error:
        api.scoped_repo(request(engine), claims)
    assert error.value.status_code == status


def test_postgres_publication_history_route_uses_only_postgres_repository(monkeypatch):
    from services.scheduling.app.postgres_publication_repository import (
        PostgresPublicationRepository,
    )

    settings = pg_settings()
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(api, "require_administrator", lambda *_: {
        "uid": "verified-admin", "tenant_id": "tenant-a", "role": "administrator",
    })
    monkeypatch.setattr(
        PostgresPublicationRepository,
        "history",
        lambda self, dataset, period: [{"dataset": dataset, "period_id": period}],
    )
    monkeypatch.setattr(
        api, "settings_and_repo", lambda: pytest.fail("SQLite publication fallback was used")
    )
    result = api.history(
        "term-a", request(object()), dataset="institutional"
    )
    assert result == {"versions": [{"dataset": "institutional", "period_id": "term-a"}]}


@pytest.mark.parametrize("role", ["student", "teacher", "administrator"])
def test_timetable_http_routes_use_verified_role_for_postgres_projection(monkeypatch, role):
    class Repository:
        def periods(self, requested_role, **scope):
            assert requested_role == role
            return {"periods": []}

        def calendar(self, tenant, dataset, period, start, end, viewer):
            assert viewer["role"] == role
            return {"sequence": 0, "occurrences": [], "sections": [], "teachers": []}

    claims = {"uid": "verified-user", "tenant_id": "tenant-a", "role": role}
    if role == "student":
        claims["student_id"] = "student-1"
    if role == "teacher":
        claims["faculty_id"] = "faculty-1"
    monkeypatch.setattr(api, "identity", lambda request: claims)
    monkeypatch.setattr(api, "settings_only", pg_settings)
    monkeypatch.setattr(api, "scoped_repo", lambda request, current: (pg_settings(), Repository()))
    async def record_stream(period, request, sandbox, start, end, requested_role,
                            section, teacher, after):
        assert requested_role == role
        return {"role": requested_role}

    monkeypatch.setattr(api, "stream", record_stream)
    client = TestClient(main.app)
    headers = {"Authorization": "Bearer verified", "X-ClassSync-Role": role}
    assert client.get("/api/v1/timetables/periods", headers=headers).status_code == 200
    response = client.get(
        "/api/v1/timetables/calendar/term-a", headers=headers,
        params={"start": "2026-10-01", "end": "2026-10-31"},
    )
    assert response.status_code == 200, response.text
    stream = client.get(
        "/api/v1/timetables/events/term-a", headers=headers,
        params={"start": "2026-10-01", "end": "2026-10-31"},
    )
    assert stream.status_code == 200
    assert stream.json() == {"role": role}
