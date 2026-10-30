from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from services.gateway.app import authorization as providers
from services.gateway.app.main import Settings


def settings(**changes):
    return Settings(_env_file=None, firebase_project_id="synthetic-project",
                    institutional_tenant_id="tenant-a", identity_database_url=None, **changes)


def configured(**changes):
    base = dict(classsync_env="test", identity_database_transport="loopback-sspi-test")
    base.update(changes)
    value = settings(**base)
    value.identity_database_url = SecretStr(
        "postgresql+psycopg://synthetic-runtime@127.0.0.1:19999/postgres"
    )
    return value


def test_unconfigured_lifecycle_preserves_explicit_adapter_without_engine(monkeypatch):
    sentinel = object()
    app = SimpleNamespace(state=SimpleNamespace(authorization_adapters=sentinel))
    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: pytest.fail("Created engine"))
    with providers.configured_authorization(app, settings()):
        assert app.state.authorization_adapters is sentinel
    assert app.state.authorization_adapters is sentinel


@pytest.mark.parametrize("exceptional", [False, True])
def test_owned_provider_removed_and_disposed_even_on_body_error(monkeypatch, exceptional):
    disposed = []
    engine = SimpleNamespace(dispose=lambda: disposed.append(True))
    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: engine)
    app = SimpleNamespace(state=SimpleNamespace())
    entered = False
    try:
        with providers.configured_authorization(app, configured()):
            entered = True
            assert app.state.authorization_adapters.memberships.engine is engine
            if exceptional:
                raise RuntimeError("synthetic body failure")
    except RuntimeError as error:
        assert exceptional
        assert str(error) == "synthetic body failure"
    assert entered
    assert not hasattr(app.state, "authorization_adapters")
    assert disposed == [True]


def test_provider_construction_failure_still_disposes_engine(monkeypatch):
    disposed = []
    engine = SimpleNamespace(dispose=lambda: disposed.append(True))
    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: engine)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic constructor failure")

    monkeypatch.setattr(providers, "PostgresMembershipLookup", fail)
    app = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(RuntimeError, match="synthetic constructor failure"):
        with providers.configured_authorization(app, configured()):
            pytest.fail("Failed construction yielded")
    assert disposed == [True]
    assert not hasattr(app.state, "authorization_adapters")


@pytest.mark.parametrize("field", ["firebase_project_id", "institutional_tenant_id"])
@pytest.mark.parametrize("missing", [None, "", " "])
def test_incomplete_binding_fails_before_creating_provider(field, missing):
    value = configured()
    setattr(value, field, missing)
    with pytest.raises(ValueError, match="Identity database configuration is invalid"):
        providers.connection_configuration(value)


@pytest.mark.parametrize("environment", ["production", "staging", "development"])
def test_loopback_transport_cannot_enable_non_test_runtime(environment):
    with pytest.raises(ValueError, match="Identity database configuration is invalid"):
        providers.connection_configuration(configured(classsync_env=environment))


@pytest.mark.parametrize("url", [
    "sqlite:///original.sqlite3", "postgresql://user@127.0.0.1:19999/postgres",
    "postgresql+psycopg://user@/postgres", "postgresql+psycopg://127.0.0.1:19999/postgres",
    "postgresql+psycopg://user@127.0.0.1/postgres",
    "postgresql+psycopg://user@127.0.0.1:19999/postgres?host=other",
    "postgresql+psycopg://user:private-sentinel@127.0.0.1:19999/postgres",
    "postgresql+psycopg://user@localhost:19999/postgres",
    "postgresql+psycopg://user@127.0.0.1:5432/postgres",
])
def test_invalid_or_ambiguous_local_configuration_is_redacted(url):
    value = configured()
    value.identity_database_url = SecretStr(url)
    with pytest.raises(ValueError) as caught:
        providers.connection_configuration(value)
    assert str(caught.value) == "Identity database configuration is invalid"
    assert "private-sentinel" not in repr(value)


def test_ambient_pg_settings_fail_without_exposing_value(monkeypatch):
    monkeypatch.setenv("pGpAsSwOrD", "private-sentinel")
    with pytest.raises(ValueError) as caught:
        providers.connection_configuration(configured())
    assert str(caught.value) == "Identity database configuration is invalid"


def test_default_transport_requires_verified_tls_and_scram():
    value = configured(classsync_env="production", identity_database_transport="verify-full")
    _, parameters = providers.connection_configuration(value)
    assert parameters["sslmode"] == "verify-full"
    assert parameters["sslrootcert"] == "system"
    assert parameters["require_auth"] == "scram-sha-256"
    assert parameters["connect_timeout"] == 5
    assert parameters["options"] == "-c statement_timeout=5000 -c lock_timeout=1500"


def test_configured_provider_conflict_creates_no_engine(monkeypatch):
    app = SimpleNamespace(state=SimpleNamespace(authorization_adapters=object()))
    monkeypatch.setattr(providers, "postgres_engine", lambda *a, **k: pytest.fail("Created engine"))
    with pytest.raises(ValueError, match="already configured"):
        with providers.configured_authorization(app, configured()):
            pytest.fail("Conflicting provider started")


def test_settings_hide_secret_url():
    value = configured()
    assert "synthetic-runtime" not in repr(value)
    assert isinstance(value.identity_database_url, SecretStr)
