from types import SimpleNamespace

import pytest

from scripts.postgres_academic_period_qualification import migrate_as_migrator
from scripts.postgres_academic_repository_qualification import assert_provisional_catalog
from scripts.postgres_driver_qualification import current_migration_head
from scripts.postgres_identity_qualification import require_unique_student_bindings
from services.academic.app.repository import catalog_data


def test_academic_period_migration_runs_only_after_non_bypass_migrator_role(monkeypatch):
    calls = []

    class Result:
        def one(self):
            return "classync_migrator_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", False, False

    class Session:
        def execute(self, statement):
            calls.append(str(statement))
            return Result()

    def migrate(session, **kwargs):
        calls.append(("migrate", kwargs))

    monkeypatch.setattr("scripts.postgres_academic_period_qualification.migrate", migrate)
    migrate_as_migrator(Session(), "classync_migrator_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    assert calls[0] == "SET LOCAL ROLE classync_migrator_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert "rolsuper" in calls[1] and "rolbypassrls" in calls[1]
    assert calls[2] == ("migrate", {})


def test_provisional_catalog_qualification_matches_canonical_ids_without_capacity():
    _, canonical_rooms = catalog_data()
    actual = [
        SimpleNamespace(
            id=room["id"],
            source="cdm-provisional",
            capacity=None,
        )
        for room in canonical_rooms
    ]

    assert_provisional_catalog(actual)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "stale", "invented_capacity"],
)
def test_provisional_catalog_qualification_rejects_catalog_or_capacity_drift(mutation):
    _, canonical_rooms = catalog_data()
    actual = [
        SimpleNamespace(
            id=room["id"],
            source="cdm-provisional",
            capacity=None,
        )
        for room in canonical_rooms
    ]
    if mutation == "missing":
        actual.pop()
    elif mutation == "stale":
        actual[0].id = "cdm-prrc-old-101"
    else:
        actual[0].capacity = 30

    with pytest.raises(RuntimeError, match="provisional catalog"):
        assert_provisional_catalog(actual)


def test_synthetic_provider_fixture_requires_unique_student_records():
    require_unique_student_bindings(
        [("uid-one", "student-one"), ("uid-two", "student-two"), ("uid-admin", None)]
    )

    with pytest.raises(RuntimeError, match="distinct synthetic student IDs"):
        require_unique_student_bindings([("uid-one", "student-a"), ("uid-two", "student-a")])


def test_provider_qualification_uses_current_alembic_head():
    assert current_migration_head() == "0025_student_roster_crud"
