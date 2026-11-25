import pytest
from classync_contracts.academic import AcademicOffering, AcademicSection, RosterStudentWrite
from classync_contracts.scheduling import Enrollment
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.academic.app import main as academic
from services.academic.app.record_rules import AcademicError
from services.academic.app.student_roster import enrollment_for_section


def student_payload(**changes):
    return {
        "expected_period_revision": 4,
        "student_id": "24-00101",
        "full_name": "  Aira Santos  ",
        "email": " Aira.Santos@Student.PNM.edu.ph ",
        "year_level": 3,
        "section_id": "bsit-3a",
        "enrollment_status": "unverified",
        **changes,
    }


def test_roster_student_contract_normalizes_fields_and_keeps_general_email_domains():
    record = RosterStudentWrite.model_validate(student_payload())
    assert record.full_name == "Aira Santos"
    assert record.email == "aira.santos@student.pnm.edu.ph"


@pytest.mark.parametrize(
    "changes",
    [
        {"student_id": "bad-id"},
        {"full_name": "  "},
        {"email": "not-an-email"},
        {"year_level": 5},
        {"section_id": " "},
    ],
)
def test_roster_student_contract_rejects_invalid_fields(changes):
    with pytest.raises(ValidationError):
        RosterStudentWrite.model_validate(student_payload(**changes))


def test_roster_edit_moves_student_to_selected_year_and_section_offerings():
    section = AcademicSection(
        id="bsit-2b",
        period_id="period-a",
        program_id="bsit",
        year_level=2,
        section_letter="B",
        entry_cohort_year=2025,
    )
    offerings = [
        AcademicOffering(id="math-2b", subject_id="math", section_id="bsit-2b"),
        AcademicOffering(id="pe-2b", subject_id="pe", section_id="bsit-2b"),
    ]
    body = RosterStudentWrite.model_validate(student_payload(year_level=2, section_id="bsit-2b"))
    enrollment = enrollment_for_section("24-00101", body, section, offerings)
    assert enrollment == Enrollment(
        student_id="24-00101", offering_ids=["math-2b", "pe-2b"], entry_cohort_year=2025
    )


def test_roster_rejects_section_that_does_not_match_year_or_has_no_offerings():
    section = AcademicSection(
        id="bsit-2a",
        period_id="period-a",
        program_id="bsit",
        year_level=2,
        section_letter="A",
    )
    body = RosterStudentWrite.model_validate(student_payload(year_level=3, section_id="bsit-2a"))
    with pytest.raises(AcademicError, match="active section for that year"):
        enrollment_for_section("24-00101", body, section, [])
    matching = body.model_copy(update={"year_level": 2})
    with pytest.raises(AcademicError, match="no active offerings"):
        enrollment_for_section("24-00101", matching, section, [])


def test_create_endpoint_requires_admin_and_delegates_scoped_period_write(monkeypatch):
    calls = []

    class Repository:
        def create_roster_student(self, period_id, body):
            calls.append((period_id, body.student_id, body.year_level, body.section_id))

    monkeypatch.setattr(
        academic, "authorize", lambda request, sandbox: ("administrator", "admin-uid")
    )
    monkeypatch.setattr(academic, "connected_repository", lambda request, owner: Repository())
    response = TestClient(academic.app).post(
        "/api/v1/academic/periods/period-a/roster", json=student_payload()
    )
    assert response.status_code == 201
    assert calls == [("period-a", "24-00101", 3, "bsit-3a")]


def test_roster_create_denies_non_administrator_before_opening_repository(monkeypatch):
    def deny(request, sandbox):
        raise HTTPException(status_code=403, detail="Administrator required")

    monkeypatch.setattr(academic, "authorize", deny)
    monkeypatch.setattr(
        academic,
        "connected_repository",
        lambda *_: pytest.fail("Repository must not be accessed for a denied request"),
    )
    response = TestClient(academic.app).post(
        "/api/v1/academic/periods/period-a/roster", json=student_payload()
    )
    assert response.status_code == 403


def test_roster_update_and_delete_use_admin_repository_methods(monkeypatch):
    calls = []

    class Repository:
        def update_roster_student(self, period_id, student_id, body):
            calls.append(("update", period_id, student_id, body.student_id))

        def delete_roster_student(self, period_id, student_id, expected_period_revision):
            calls.append(("delete", period_id, student_id, expected_period_revision))

    monkeypatch.setattr(
        academic, "authorize", lambda request, sandbox: ("administrator", "admin-uid")
    )
    monkeypatch.setattr(academic, "connected_repository", lambda request, owner: Repository())
    client = TestClient(academic.app)
    updated = client.put(
        "/api/v1/academic/periods/period-a/roster/24-00101",
        json=student_payload(student_id="24-00109", section_id="bsit-3b"),
    )
    deleted = client.delete(
        "/api/v1/academic/periods/period-a/roster/24-00109?expected_period_revision=5"
    )
    assert updated.status_code == 200
    assert deleted.status_code == 200
    assert calls == [
        ("update", "period-a", "24-00101", "24-00109"),
        ("delete", "period-a", "24-00109", 5),
    ]
