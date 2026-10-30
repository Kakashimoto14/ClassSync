"""Bind institutional routes to verified ownership and an explicitly owned pool."""

import tempfile
from pathlib import Path

from classync_contracts.identity import VerifiedPrincipal
from fastapi import HTTPException

from .postgres_repository import PostgresAcademicRepository


class ScopedTestRepository:
    """Preserve existing isolated SQLite identity fixtures; never production fallback."""

    def __init__(self, repository, owner):
        self.repository, self.owner = repository, owner

    def periods(self):
        return self.repository.periods("administrator", self.owner)

    def create_period(self, body):
        return self.repository.create_period(body, "administrator", self.owner)

    def snapshot(self, period_id):
        return self.repository.snapshot("administrator", self.owner, period_id)

    def save(self, period_id, kind, record_id, body):
        return self.repository.save("administrator", self.owner, period_id, kind, record_id, body)

    def save_calendar(self, period_id, body):
        return self.repository.save_calendar("administrator", self.owner, period_id, body)


def institutional_repository(request, settings, owner, sqlite_factory):
    # owner is the server require_administrator result, never a header/body grant.
    if settings.academic_database_url is not None:
        engine = getattr(request.app.state, "academic_engine", None)
        if engine is None:
            raise HTTPException(503, "Academic storage is unavailable")
        return PostgresAcademicRepository(
            engine,
            tenant_id=settings.institutional_tenant_id,
            firebase_project_id=settings.firebase_project_id,
            principal=VerifiedPrincipal(uid=owner),
        )
    path = Path(settings.academic_database_path)
    if (
        settings.classsync_env == "test"
        and settings.enable_test_identity_adapters
        and path.is_absolute()
        and path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    ):
        return ScopedTestRepository(sqlite_factory(), owner)
    raise HTTPException(503, "Academic storage is unavailable")
