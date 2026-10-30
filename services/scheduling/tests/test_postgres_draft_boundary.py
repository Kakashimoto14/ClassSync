from contextlib import contextmanager

import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.scheduling import SaveDraftRequest

from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository


@pytest.mark.parametrize("principal", [None, "uid", {"uid": "uid", "role": "administrator"}])
def test_drafts_require_verified_principal_before_database_access(principal):
    with pytest.raises(ValueError, match="verified principal"):
        PostgresDraftRepository(
            object(), tenant_id="tenant", firebase_project_id="demo", principal=principal
        )


@pytest.mark.parametrize("binding", [{"tenant_id": ""}, {"firebase_project_id": " "}])
def test_drafts_require_explicit_server_binding_without_startup_migration(binding):
    values = {"tenant_id": "tenant", "firebase_project_id": "demo", **binding}
    with pytest.raises(ValueError):
        PostgresDraftRepository(object(), principal=VerifiedPrincipal(uid="uid"), **values)


@pytest.mark.parametrize(
    "page", [{"limit": 0}, {"limit": 101}, {"limit": True}, {"offset": -1}, {"offset": True}]
)
def test_invalid_draft_pagination_never_reaches_storage(page):
    repository = PostgresDraftRepository(
        object(),
        tenant_id="tenant",
        firebase_project_id="demo",
        principal=VerifiedPrincipal(uid="uid"),
    )
    with pytest.raises(DraftError) as denied:
        repository.list(**page)
    assert denied.value.status == 422


def test_existing_run_rejects_unbound_second_save_key_before_reporting_success(monkeypatch):
    repository = PostgresDraftRepository(
        object(),
        tenant_id="tenant",
        firebase_project_id="demo",
        principal=VerifiedPrincipal(uid="uid"),
    )

    class ExistingRun:
        def execute(self, *_args, **_kwargs):
            return self

        def mappings(self):
            return self

        def all(self):
            # The owner-scoped SQL found this run under its original key.
            # No snapshot decode or successful response is allowed for another key.
            return [{"idempotency_key": "original-save-key"}]

    @contextmanager
    def session(**_kwargs):
        yield ExistingRun()

    monkeypatch.setattr(repository, "session", session)
    request = SaveDraftRequest(
        run_id="server-run",
        input_hash="a" * 64,
        title="Review",
        idempotency_key="second-save-key",
    )
    with pytest.raises(DraftError) as conflict:
        repository.save(request)
    assert (conflict.value.status, conflict.value.code) == (409, "idempotency_conflict")
