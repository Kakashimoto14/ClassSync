"""Explicit Scheduling storage selection behind verified server authorization."""

import tempfile
from pathlib import Path

from classync_contracts.identity import VerifiedPrincipal
from fastapi import HTTPException

from .postgres_draft_repository import PostgresDraftRepository


def isolated_test_sqlite(settings):
    path = Path(settings.scheduling_database_path)
    return (
        settings.classsync_env == "test"
        and settings.enable_test_identity_adapters
        and path.is_absolute()
        and path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    )


class ScopedTestDraftRepository:
    """Bind legacy isolated identity fixtures, never an institutional fallback."""

    def __init__(self, repository, owner):
        self.repository, self.owner = repository, owner

    def remember_run(self, inputs, result):
        return self.repository.remember_run(inputs, result, "administrator", self.owner)

    def save(self, body):
        return self.repository.save(body, "administrator", self.owner)

    def get(self, draft_id):
        return self.repository.get(draft_id, "administrator", self.owner)

    def list(self, *, limit=25, offset=0):
        return self.repository.list("administrator", self.owner, limit=limit, offset=offset)


def institutional_repository(request, settings, owner, sqlite_factory):
    # owner is the trusted require_administrator result, never a body/header grant.
    if settings.scheduling_database_url is not None:
        engine = getattr(request.app.state, "scheduling_engine", None)
        if engine is None:
            raise HTTPException(503, "Scheduling storage is unavailable")
        return PostgresDraftRepository(
            engine,
            tenant_id=settings.institutional_tenant_id,
            firebase_project_id=settings.firebase_project_id,
            principal=VerifiedPrincipal(uid=owner),
        )
    if isolated_test_sqlite(settings):
        return ScopedTestDraftRepository(sqlite_factory(), owner)
    raise HTTPException(503, "Scheduling storage is unavailable")


def require_local_publication(settings, sandbox):
    if settings.scheduling_database_url is not None:
        if sandbox:
            raise HTTPException(503, "Synthetic publication storage is unavailable")
        return
    if sandbox:
        from classync_contracts.scheduling_security import require_sandbox

        require_sandbox(settings)
        return
    if not isolated_test_sqlite(settings):
        raise HTTPException(503, "Publication storage is unavailable")
