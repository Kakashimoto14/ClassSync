"""Portable owned Scheduling provider tests; no server, database or solver runs."""

from types import SimpleNamespace

import pytest
from classync_contracts.identity import MembershipAuthorizationError, MembershipErrorCode
from classync_contracts.publication import PublicationCommand, RoomRestriction
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.scheduling.app import main as scheduling
from services.scheduling.app import publication_api as publication
from services.scheduling.tests.test_calendar import configuration
from services.scheduling.tests.test_engine import tiny


def configured_settings(**changes):
    values = dict(
        classsync_env="test", firebase_project_id="demo-test", institutional_tenant_id="tenant-a",
        scheduling_database_transport="loopback-sspi-test",
        scheduling_database_url=SecretStr("postgresql+psycopg://runtime@127.0.0.1:19999/postgres"),
    )
    return scheduling.Settings(_env_file=None, **(values | changes))


def fake_request(**state):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**state)))


def test_unconfigured_institutional_storage_never_opens_original_sqlite(monkeypatch):
    monkeypatch.setattr(
        scheduling, "require_administrator", lambda *args: {"uid": "verified-unit-user"}
    )
    monkeypatch.setattr(scheduling.settings, "classsync_env", "production")
    monkeypatch.setattr(scheduling.settings, "scheduling_database_url", None)
    monkeypatch.setattr(scheduling, "repository", lambda: pytest.fail("Opened SQLite fallback"))
    with TestClient(scheduling.app) as client:
        response = client.get("/api/v1/scheduling/drafts")
    assert response.status_code == 503


def test_unconfigured_provider_leaves_unrelated_state_untouched():
    from services.scheduling.app.authorization import configured_scheduling

    sentinel = object()
    app = SimpleNamespace(state=SimpleNamespace(unrelated=sentinel))
    settings = scheduling.Settings(_env_file=None, scheduling_database_url=None)
    with configured_scheduling(app, settings):
        assert vars(app.state) == {"unrelated": sentinel}
    assert vars(app.state) == {"unrelated": sentinel}


@pytest.mark.parametrize("body_failure", [False, True])
def test_owned_pool_and_adapters_removed_and_disposed_on_exit(monkeypatch, body_failure):
    from services.scheduling.app import authorization as providers

    disposed, options = [], []
    engine = SimpleNamespace(dispose=lambda: disposed.append(True))

    def create(*args, **kwargs):
        options.append(kwargs)
        return engine

    monkeypatch.setattr(providers, "postgres_engine", create)
    app = SimpleNamespace(state=SimpleNamespace())

    def exercise():
        with providers.configured_scheduling(app, configured_settings()):
            assert app.state.scheduling_engine is engine
            assert app.state.authorization_adapters.memberships.engine is engine
            if body_failure:
                raise RuntimeError("synthetic body failure")

    if body_failure:
        with pytest.raises(RuntimeError, match="synthetic body failure"):
            exercise()
    else:
        exercise()
    assert disposed == [True]
    assert not vars(app.state)
    assert options[0]["pool_size"] == 5 and options[0]["max_overflow"] == 0
    assert options[0]["pool_timeout"] == 3
    parameters = options[0]["connect_args"]
    assert parameters["connect_timeout"] == 5
    assert "statement_timeout=5000" in parameters["options"]
    assert "lock_timeout=1500" in parameters["options"]
    assert parameters["application_name"] == "classsync-scheduling"
    assert parameters["sslmode"] == "disable" and parameters["require_auth"] == "sspi"


@pytest.mark.parametrize("existing", ["authorization_adapters", "scheduling_engine"])
def test_existing_provider_state_never_overwritten(monkeypatch, existing):
    from services.scheduling.app import authorization as providers

    sentinel = object()
    app = SimpleNamespace(state=SimpleNamespace(**{existing: sentinel}))
    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: pytest.fail("Created pool"))
    with pytest.raises(ValueError, match="already configured"):
        with providers.configured_scheduling(app, configured_settings()):
            pytest.fail("Entered conflicting provider")
    assert vars(app.state) == {existing: sentinel}


@pytest.mark.parametrize("failed_factory", ["FirebaseTokenVerifier", "PostgresMembershipLookup"])
def test_startup_constructor_failure_disposes_pool(monkeypatch, failed_factory):
    from services.scheduling.app import authorization as providers

    disposed = []
    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: SimpleNamespace(
        dispose=lambda: disposed.append(True),
    ))

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic constructor failure")

    monkeypatch.setattr(providers, failed_factory, fail)
    app = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(RuntimeError, match="synthetic constructor failure"):
        with providers.configured_scheduling(app, configured_settings()):
            pytest.fail("Entered failed provider")
    assert disposed == [True]
    assert not vars(app.state)


def test_cleanup_preserves_replacement_state_it_does_not_own(monkeypatch):
    from services.scheduling.app import authorization as providers

    disposed = []
    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: SimpleNamespace(
        dispose=lambda: disposed.append(True),
    ))
    app = SimpleNamespace(state=SimpleNamespace())
    replacements = {"scheduling_engine": object(), "authorization_adapters": object()}
    with providers.configured_scheduling(app, configured_settings()):
        for name, sentinel in replacements.items():
            setattr(app.state, name, sentinel)
    assert vars(app.state) == replacements
    assert disposed == [True]


def test_invalid_transport_target_rejected_before_pool_creation(monkeypatch):
    from services.scheduling.app import authorization as providers

    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: pytest.fail("Created pool"))
    app = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(ValueError):
        with providers.configured_scheduling(app, configured_settings(classsync_env="production")):
            pytest.fail("Entered test-only transport in production")
    assert not vars(app.state)


@pytest.mark.parametrize("environment,flag,path", [
    ("production", True, "temporary"), ("development", True, "temporary"),
    ("test", False, "temporary"), ("test", True, "var/scheduling.sqlite3"),
])
def test_sqlite_fixture_exception_cannot_enable_other_modes(
    tmp_path, environment, flag, path,
):
    from services.scheduling.app.provider import institutional_repository

    settings = scheduling.Settings(
        _env_file=None, classsync_env=environment, enable_test_identity_adapters=flag,
        scheduling_database_path=str(tmp_path / "synthetic.db") if path == "temporary" else path,
    )
    with pytest.raises(HTTPException) as denied:
        institutional_repository(fake_request(), settings, "verified-owner",
                                 lambda: pytest.fail("Opened SQLite fallback"))
    assert denied.value.status_code == 503


def test_configured_url_without_owned_lifespan_never_uses_fixture_fallback(tmp_path):
    from services.scheduling.app.provider import institutional_repository

    settings = configured_settings(enable_test_identity_adapters=True,
                                   scheduling_database_path=str(tmp_path / "synthetic.db"))
    with pytest.raises(HTTPException) as denied:
        institutional_repository(fake_request(), settings, "verified-owner",
                                 lambda: pytest.fail("Opened configured fallback"))
    assert denied.value.status_code == 503


def test_configured_store_binds_server_tenant_project_and_verified_owner():
    from services.scheduling.app.provider import institutional_repository

    engine = object()
    repository = institutional_repository(
        fake_request(scheduling_engine=engine), configured_settings(), "verified-owner",
        lambda: pytest.fail("Opened configured fallback"),
    )
    assert repository.engine is engine
    assert repository.keys == {"tenant": "tenant-a", "owner": "verified-owner"}
    assert repository.principal.uid == "verified-owner"
    assert repository.context.project_id == "demo-test"


def test_exact_temporary_test_fixture_preserves_owner_binding(tmp_path):
    from services.scheduling.app.provider import institutional_repository

    calls, sentinel = [], object()
    legacy = SimpleNamespace(list=lambda *args, **kwargs: calls.append((args, kwargs)) or sentinel)
    settings = scheduling.Settings(
        _env_file=None, classsync_env="test", enable_test_identity_adapters=True,
        scheduling_database_path=str(tmp_path / "synthetic.db"),
    )
    repository = institutional_repository(
        fake_request(), settings, "verified-owner", lambda: legacy,
    )
    assert repository.list(limit=7, offset=14) is sentinel
    assert calls == [(("administrator", "verified-owner"), {"limit": 7, "offset": 14})]


@pytest.mark.parametrize("code,status", [
    (MembershipErrorCode.DENIED, 403), (MembershipErrorCode.UNAVAILABLE, 503),
])
def test_membership_change_after_initial_guard_is_private_http_error(monkeypatch, code, status):
    monkeypatch.setattr(scheduling, "require_administrator", lambda *a: {"uid": "verified-owner"})

    def denied(**kwargs):
        raise MembershipAuthorizationError(code)

    monkeypatch.setattr(scheduling, "connected_repository", lambda *a: SimpleNamespace(list=denied))
    with TestClient(scheduling.app) as client:
        response = client.get("/api/v1/scheduling/drafts")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code.value
    assert set(response.json()["error"]) == {"code", "message"}


def test_unconfigured_generation_rejects_storage_before_solver(monkeypatch):
    monkeypatch.setattr(scheduling, "require_administrator", lambda *a: {"uid": "verified-owner"})
    monkeypatch.setattr(scheduling.settings, "classsync_env", "production")
    monkeypatch.setattr(scheduling.settings, "scheduling_database_url", None)
    monkeypatch.setattr(scheduling, "repository", lambda: pytest.fail("Opened SQLite fallback"))
    monkeypatch.setattr(scheduling, "generate_week", lambda *a: pytest.fail("Solver ran"))
    with TestClient(scheduling.app) as client:
        response = client.post("/api/v1/scheduling/generate", json=tiny().model_dump(mode="json"))
    assert response.status_code == 503


@pytest.mark.parametrize("configured", [False, True])
@pytest.mark.parametrize("method,path", [
    ("get", "/periods"),
    ("get", "/history/synthetic-period"),
    ("get", "/calendar/synthetic-period?start=2026-10-01&end=2026-10-31"),
    ("get", "/events/synthetic-period?start=2026-10-01&end=2026-10-31"),
    ("get", "/availability?room_id=room-a&start=2026-10-01T08:00:00%2B08:00"
     "&end=2026-10-01T09:00:00%2B08:00"),
    ("post", "/review"), ("post", "/publish"), ("put", "/restrictions/restriction-a"),
])
def test_publication_routes_refuse_legacy_factory_even_after_trusted_guard(
    monkeypatch, configured, method, path,
):
    settings = configured_settings() if configured else scheduling.Settings(
        _env_file=None, classsync_env="production",
    )
    claims = {"uid": "verified-owner", "tenant_id": "tenant-a", "role": "administrator"}
    monkeypatch.setattr(scheduling, "settings", settings)
    monkeypatch.setattr(publication, "identity", lambda *a: claims)
    monkeypatch.setattr(publication, "require_administrator", lambda *a: claims)
    monkeypatch.setattr(
        publication, "settings_and_repo", lambda: pytest.fail("Publication fallback"),
    )
    payload = None
    if method == "post":
        payload = PublicationCommand(
            draft_id="synthetic-draft", expected_version=0, expected_academic_revision=1,
            idempotency_key="synthetic-publish-key", calendar=configuration().calendar,
        ).model_dump(mode="json")
    elif method == "put":
        payload = RoomRestriction(
            id="restriction-a", room_id="room-a", starts_at="2026-10-01T08:00:00+08:00",
            ends_at="2026-10-01T09:00:00+08:00", kind="reservation", reason="Synthetic test",
            expected_revision=0,
        ).model_dump(mode="json")
    # Intentionally no lifespan: this proves route guards before either pool or legacy storage.
    response = TestClient(scheduling.app).request(method, "/api/v1/timetables" + path, json=payload)
    assert response.status_code == 503
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_configured_postgres_publication_allows_only_institutional_storage():
    from services.scheduling.app.provider import require_local_publication

    settings = configured_settings(classsync_env="development", enable_scheduling_sandbox=True)
    require_local_publication(settings, False)
    with pytest.raises(HTTPException) as denied:
        require_local_publication(settings, True)
    assert denied.value.status_code == 503


def test_publication_helper_keeps_only_explicit_development_sandbox_and_temp_test_fixture(tmp_path):
    from services.scheduling.app.provider import require_local_publication

    development = scheduling.Settings(
        _env_file=None, classsync_env="development", enable_scheduling_sandbox=True,
    )
    require_local_publication(development, True)
    with pytest.raises(HTTPException):
        require_local_publication(development, False)
    test = scheduling.Settings(
        _env_file=None, classsync_env="test", enable_test_identity_adapters=True,
        scheduling_database_path=str(tmp_path / "synthetic.db"),
    )
    require_local_publication(test, False)


@pytest.mark.parametrize("path", [
    "/sandbox/periods",
    "/sandbox/calendar/synthetic-period?start=2026-10-01&end=2026-10-31",
    "/sandbox/events/synthetic-period?start=2026-10-01&end=2026-10-31",
    "/sandbox/availability?room_id=room-a&start=2026-10-01T08:00:00%2B08:00"
    "&end=2026-10-01T09:00:00%2B08:00",
    "/history/synthetic-period?dataset=synthetic",
])
def test_configured_pg_does_not_reopen_anonymous_synthetic_publication(monkeypatch, path):
    settings = configured_settings(classsync_env="development", enable_scheduling_sandbox=True)
    monkeypatch.setattr(scheduling, "settings", settings)
    monkeypatch.setattr(publication, "require_administrator", lambda *a: {"uid": "verified-owner"})
    monkeypatch.setattr(
        publication, "settings_and_repo", lambda: pytest.fail("Synthetic publication fallback"),
    )
    response = TestClient(scheduling.app).get("/api/v1/timetables" + path)
    assert response.status_code == 503
    assert "text/event-stream" not in response.headers.get("content-type", "")


@pytest.mark.parametrize("status", ["unknown", "infeasible"])
def test_unsuccessful_solver_status_never_persists_a_run(monkeypatch, status):
    # Stub results test control flow; this does not run or alter solver constraints.
    result = SimpleNamespace(solver_status=status)
    monkeypatch.setattr(scheduling, "generate_week", lambda *_args: result)
    storage = SimpleNamespace(remember_run=lambda *a: pytest.fail("Persisted failed solver run"))
    assert scheduling.execute(
        object(), "administrator", "verified-owner", storage=storage,
    ) is result


def test_persistence_failure_never_returns_false_candidate_success_and_releases_slot(monkeypatch):
    from services.scheduling.app.draft_repository import DraftError

    result = SimpleNamespace(solver_status="feasible")
    monkeypatch.setattr(scheduling, "generate_week", lambda *_args: result)

    def fail(*args):
        raise DraftError(503, "persistence_unavailable", "Synthetic storage outage")

    with pytest.raises(DraftError) as denied:
        scheduling.execute(object(), "administrator", "verified-owner",
                           storage=SimpleNamespace(remember_run=fail))
    assert denied.value.status == 503
    assert scheduling.generation_slot.acquire(blocking=False)
    scheduling.generation_slot.release()


@pytest.mark.parametrize("scope", ["administrator", "student", "unknown", ""])
def test_unbound_non_sandbox_execute_rejects_before_solver_or_legacy_factory(monkeypatch, scope):
    monkeypatch.setattr(
        scheduling, "repository", lambda: pytest.fail("Opened unbound legacy store"),
    )
    monkeypatch.setattr(scheduling, "generate_week", lambda *_a: pytest.fail("Unbound solver ran"))
    with pytest.raises(HTTPException) as denied:
        scheduling.execute(object(), scope, "verified-owner")
    assert denied.value.status_code == 503
