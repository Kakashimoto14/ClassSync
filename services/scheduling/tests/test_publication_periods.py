"""Publication period listing never offers an archived academic period."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.scheduling.app.postgres_publication_repository import (
    PostgresPublicationRepository,
)

LEGACY = "defense-ay-2026-2027-first"


def listing(role, **viewer):
    db = Mock()
    heads = [{"period_id": LEGACY, "revision": 214}, {"period_id": "active", "revision": 1}]
    db.execute.return_value.mappings.return_value.all.return_value = heads
    db.scalars.return_value.all.return_value = [LEGACY]

    @contextmanager
    def session(**_):
        yield db

    payload = {
        "draft": SimpleNamespace(
            title="Timetable",
            input_snapshot=SimpleNamespace(
                enrollments=[SimpleNamespace(student_id="student-1")]
            ),
            generation_result=SimpleNamespace(
                assignments=[SimpleNamespace(teacher_id="faculty-1")]
            ),
        ),
        "calendar": SimpleNamespace(model_dump=lambda **_: {}),
    }
    repo = SimpleNamespace(
        keys={"tenant": "cdm"},
        scope=lambda *_: None,
        session=session,
        params=lambda dataset, **values: values,
        rows=lambda *_: [{"id": "version"}],
        decode=lambda *_: payload,
    )
    result = PostgresPublicationRepository.periods(repo, role, **viewer)
    return [item["id"] for item in result["periods"]], db


def test_administrator_never_sees_an_archived_period_even_with_a_higher_revision():
    ids, db = listing("administrator")
    assert ids == ["active"]
    assert db.scalars.call_args.args[1]["archived"] == "Archived invalid period · %"


@pytest.mark.parametrize(
    ("role", "viewer"),
    [("teacher", {"faculty_id": "faculty-1"}), ("student", {"student_id": "student-1"})],
)
def test_non_administrators_do_not_query_period_metadata(role, viewer):
    _, db = listing(role, **viewer)
    db.scalars.assert_not_called()
