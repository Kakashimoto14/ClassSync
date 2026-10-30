"""Browser mode declarations never grant server sandbox or identity privileges."""

from types import SimpleNamespace

import pytest
from classync_contracts.scheduling_security import require_identity, require_sandbox
from fastapi import HTTPException
from starlette.requests import Request


@pytest.mark.parametrize("environment", ["production", "staging", "test", "Development", ""])
@pytest.mark.parametrize("enabled", [False, True])
def test_non_development_environment_cannot_enable_sandbox(environment, enabled):
    settings = SimpleNamespace(classsync_env=environment, enable_scheduling_sandbox=enabled)
    with pytest.raises(HTTPException) as error:
        require_sandbox(settings)
    assert error.value.status_code == 403


@pytest.mark.parametrize("mode", ["presentation", "sandbox", "institutional"])
def test_browser_mode_and_preview_role_do_not_supply_verified_identity(mode):
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-classsync-mode", mode.encode()), (b"x-role", b"administrator")],
            "query_string": b"role=administrator&mode=sandbox",
        }
    )
    with pytest.raises(HTTPException) as error:
        require_identity(request, SimpleNamespace())
    assert error.value.status_code == 401


def test_explicit_local_development_still_requires_both_server_gates():
    with pytest.raises(HTTPException) as error:
        require_sandbox(
            SimpleNamespace(classsync_env="development", enable_scheduling_sandbox=False)
        )
    assert error.value.status_code == 403
    assert (
        require_sandbox(
            SimpleNamespace(classsync_env="development", enable_scheduling_sandbox=True)
        )
        is None
    )


def test_missing_firebase_credentials_fails_closed_without_leaking_details(monkeypatch):
    from classync_contracts import token_verification
    from classync_contracts.scheduling_security import SchedulingSecuritySettings
    from fastapi import FastAPI

    def unavailable(_settings):
        raise RuntimeError("Credential setup unavailable")

    monkeypatch.setattr(token_verification, "initialize_firebase", unavailable)
    request = Request(
        {
            "type": "http",
            "app": FastAPI(),
            "headers": [(b"authorization", b"Bearer e30.e30.signature")],
        }
    )
    with pytest.raises(HTTPException) as error:
        require_identity(
            request,
            SchedulingSecuritySettings(firebase_project_id="synthetic-project", _env_file=None),
        )
    assert error.value.status_code == 503
    assert error.value.detail == "University access is unavailable"
