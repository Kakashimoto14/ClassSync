from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository


def repository():
    repo = MagicMock()
    repo.keys = {"tenant": "synthetic-tenant"}
    repo.head.return_value = 2
    repo.rows.return_value = [{"id": "current-version", "revision": 2}]
    room = SimpleNamespace(
        id="room-a",
        name="Invented room",
        building="Invented building",
        floor=None,
        location=None,
        room_type="laboratory",
        type_verified=False,
        capacity=40,
        capacity_verified=False,
        equipment=["unverified"],
        equipment_verified=False,
    )
    repo.decode.return_value = {
        "draft": SimpleNamespace(
            input_snapshot=SimpleNamespace(
                rooms=[room],
                enrollments=[SimpleNamespace(student_id="student-a", offering_ids=["offering-a"])],
            ),
            generation_result=SimpleNamespace(
                assignments=[SimpleNamespace(teacher_id="faculty-a")]
            ),
        )
    }
    return repo


@pytest.mark.parametrize(
    "role,field,record",
    [
        ("teacher", "faculty_id", "other-faculty"),
        ("student", "student_id", "other-student"),
    ],
)
def test_selected_role_denies_unassigned_directory_even_if_rls_exposes_admin_rows(
    role, field, record
):
    repo = repository()
    with pytest.raises(DraftError) as denied:
        PostgresPublicationRepository.room_directory(
            repo, "period-a", {"role": role, field: record}
        )
    assert denied.value.status == 403


@pytest.mark.parametrize(
    "viewer",
    [
        {"role": "teacher", "faculty_id": "faculty-a"},
        {"role": "student", "student_id": "student-a"},
        {"role": "administrator"},
    ],
)
def test_directory_returns_only_room_metadata_and_withholds_unverified_facilities(viewer):
    result = PostgresPublicationRepository.room_directory(repository(), "period-a", viewer)
    assert result["version"] == "current-version" and len(result["rooms"]) == 1
    room = result["rooms"][0]
    assert set(room) == {
        "id",
        "name",
        "building",
        "floor",
        "location",
        "room_type",
        "capacity",
        "equipment",
    }
    assert room["capacity"] is None and room["room_type"] is None and room["equipment"] == []


def test_directory_never_uses_an_old_visible_publication():
    repo = repository()
    repo.head.return_value = 3
    with pytest.raises(DraftError) as denied:
        PostgresPublicationRepository.room_directory(repo, "period-a", {"role": "administrator"})
    assert denied.value.status == 403
