from types import SimpleNamespace

import pytest
from classync_contracts.identity import MembershipAuthorizationError, MembershipErrorCode
from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.academic.app import main as academic


def configured_settings(**changes):
    values = dict(
        classsync_env="test",
        firebase_project_id="demo-test",
        institutional_tenant_id="tenant-a",
        academic_database_transport="loopback-sspi-test",
        academic_database_url=SecretStr("postgresql+psycopg://runtime@127.0.0.1:19999/postgres"),
    )
    values.update(changes)
    return academic.Settings(_env_file=None, **values)


def test_unconfigured_institutional_storage_never_opens_original_sqlite(monkeypatch):
    monkeypatch.setattr(
        academic, "require_administrator", lambda *args: {"uid": "verified-unit-user"}
    )
    monkeypatch.setattr(academic.settings, "classsync_env", "production")
    monkeypatch.setattr(academic, "repository", lambda: pytest.fail("Opened SQLite fallback"))
    with TestClient(academic.app) as client:
        response = client.get("/api/v1/academic/periods")
    assert response.status_code == 503


def test_configured_provider_owns_pool_and_cleans_up_on_body_failure(monkeypatch):
    from services.academic.app import authorization as providers

    disposed = []
    engine = SimpleNamespace(dispose=lambda: disposed.append(True))
    monkeypatch.setattr(providers, "postgres_engine", lambda *args, **kwargs: engine)
    settings = academic.Settings(
        _env_file=None,
        classsync_env="test",
        firebase_project_id="demo-test",
        institutional_tenant_id="tenant-a",
        academic_database_transport="loopback-sspi-test",
        academic_database_url=SecretStr("postgresql+psycopg://runtime@127.0.0.1:19999/postgres"),
    )
    app = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(RuntimeError, match="synthetic body failure"):
        with providers.configured_academic(app, settings):
            assert app.state.academic_engine is engine
            assert app.state.authorization_adapters.memberships.engine is engine
            raise RuntimeError("synthetic body failure")
    assert not hasattr(app.state, "academic_engine")
    assert not hasattr(app.state, "authorization_adapters")
    assert disposed == [True]


@pytest.mark.parametrize(
    "code,status", [(MembershipErrorCode.DENIED, 403), (MembershipErrorCode.UNAVAILABLE, 503)]
)
def test_membership_change_after_request_guard_is_private_http_error(monkeypatch, code, status):
    monkeypatch.setattr(
        academic, "require_administrator", lambda *args: {"uid": "verified-unit-user"}
    )

    def denied():
        raise MembershipAuthorizationError(code)

    monkeypatch.setattr(
        academic, "connected_repository", lambda *args: SimpleNamespace(periods=denied)
    )
    with TestClient(academic.app) as client:
        response = client.get("/api/v1/academic/periods")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code.value
    assert set(response.json()["error"]) == {"code", "message"}


def test_normal_owned_cleanup_and_bounded_pool_without_migrations(monkeypatch):
    from services.academic.app import authorization as providers

    disposed, options = [], []
    engine = SimpleNamespace(dispose=lambda: disposed.append(True))

    def create(*args, **kwargs):
        options.append(kwargs)
        return engine

    monkeypatch.setattr(providers, "postgres_engine", create)
    app = SimpleNamespace(state=SimpleNamespace())
    with providers.configured_academic(app, configured_settings()):
        assert app.state.academic_engine is engine
    assert disposed == [True]
    assert options[0]["pool_size"] == 5 and options[0]["max_overflow"] == 0
    assert options[0]["pool_timeout"] == 3
    assert "statement_timeout=5000" in options[0]["connect_args"]["options"]
    assert options[0]["connect_args"]["application_name"] == "classsync-academic"


@pytest.mark.parametrize("existing", ["authorization_adapters", "academic_engine"])
def test_existing_provider_is_never_overwritten(monkeypatch, existing):
    from services.academic.app import authorization as providers

    sentinel = object()
    app = SimpleNamespace(state=SimpleNamespace(**{existing: sentinel}))
    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: pytest.fail("Created pool"))
    with pytest.raises(ValueError, match="already configured"):
        with providers.configured_academic(app, configured_settings()):
            pytest.fail("Entered conflicting provider")
    assert getattr(app.state, existing) is sentinel


@pytest.mark.parametrize("failed_factory", ["FirebaseTokenVerifier", "PostgresMembershipLookup"])
def test_startup_constructor_failure_disposes_owned_pool(monkeypatch, failed_factory):
    from services.academic.app import authorization as providers

    disposed = []
    monkeypatch.setattr(
        providers,
        "postgres_engine",
        lambda *a, **k: SimpleNamespace(dispose=lambda: disposed.append(True)),
    )

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic startup failure")

    monkeypatch.setattr(providers, failed_factory, fail)
    app = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(RuntimeError, match="synthetic startup failure"):
        with providers.configured_academic(app, configured_settings()):
            pytest.fail("Entered failed provider")
    assert disposed == [True]
    assert not vars(app.state)


@pytest.mark.parametrize(
    "environment,flag,path",
    [
        ("production", True, "temporary"),
        ("development", True, "temporary"),
        ("test", False, "temporary"),
        ("test", True, "var/academic.sqlite3"),
    ],
)
def test_sqlite_test_exception_cannot_enable_other_modes(
    monkeypatch, tmp_path, environment, flag, path
):
    from services.academic.app.provider import institutional_repository

    settings = academic.Settings(
        _env_file=None,
        classsync_env=environment,
        enable_test_identity_adapters=flag,
        academic_database_path=str(tmp_path / "synthetic.db") if path == "temporary" else path,
    )
    with pytest.raises(academic.HTTPException) as denied:
        institutional_repository(
            SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())),
            settings,
            "verified-unit-user",
            lambda: pytest.fail("Opened fallback"),
        )
    assert denied.value.status_code == 503


def test_configured_url_without_lifespan_never_uses_test_fallback(tmp_path):
    from services.academic.app.provider import institutional_repository

    settings = configured_settings(
        enable_test_identity_adapters=True, academic_database_path=str(tmp_path / "synthetic.db")
    )
    with pytest.raises(academic.HTTPException) as denied:
        institutional_repository(
            SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())),
            settings,
            "verified-unit-user",
            lambda: pytest.fail("Opened configured fallback"),
        )
    assert denied.value.status_code == 503
