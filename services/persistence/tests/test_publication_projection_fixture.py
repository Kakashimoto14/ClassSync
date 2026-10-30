"""Qualification identities need persisted enrollment, not a preview section hint."""

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.scheduling import scheduling_input_hash

from scripts.postgres_publication_repository_qualification import enrolled_projection_fixture
from services.academic.app.repository import AcademicRepository
from services.academic.tests.test_academic import complete
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository


def test_generated_projection_fixture_saves_disjoint_enrollment_before_hashing(tmp_path):
    academic = AcademicRepository(tmp_path / "generated.sqlite3")
    academic.migrate()
    original = complete(academic)
    before = academic_readiness(original)
    assert before.ready and before.inputs.enrollments == []  # Exact old fixture defect.
    bound = SimpleNamespace(save=lambda period, kind, identity, body: academic.save(
        "sandbox", "development-academic-sandbox", period, kind, identity, body,
    ))
    linked = enrolled_projection_fixture(bound, original)
    after = academic_readiness(linked)
    assert after.ready
    assert linked.period.revision == original.period.revision + 1
    assert scheduling_input_hash(before.inputs) != scheduling_input_hash(after.inputs)
    assert before.inputs.enrollments == []
    memberships = {entry.student_id: set(entry.offering_ids) for entry in after.inputs.enrollments}
    assert set(memberships) == {"student-a", "student-other"}
    assert "student-unassigned" not in memberships
    assert memberships["student-a"] and memberships["student-other"]
    assert memberships["student-a"].isdisjoint(memberships["student-other"])
    offerings = {offering.id: offering.section_id for offering in after.inputs.offerings}
    assert {offerings[key] for key in memberships["student-a"]} == {"section-a"}
    assert {offerings[key] for key in memberships["student-other"]} == {"section-b"}
    restored = academic.snapshot(
        "sandbox", "development-academic-sandbox", linked.period.id,
    )
    assert academic_readiness(restored).inputs.enrollments == after.inputs.enrollments


@pytest.mark.parametrize("visible,current", [([], 0), ([{"revision": 1}], 0),
                                            ([{"revision": 1}], 2)])
def test_student_guard_never_falls_back_to_older_visible_publication(monkeypatch, visible, current):
    reader = PostgresPublicationRepository(object(), tenant_id="tenant-a",
        firebase_project_id="synthetic-project", principal=VerifiedPrincipal(uid="uid-student"))

    @contextmanager
    def session(**_kwargs):
        yield object()

    monkeypatch.setattr(reader, "session", session)
    monkeypatch.setattr(reader, "rows", lambda *_args: visible)
    monkeypatch.setattr(reader, "head", lambda *_args: current)
    monkeypatch.setattr(reader, "project", lambda *_args: pytest.fail("Stale projection exposed"))
    with pytest.raises(DraftError) as caught:
        reader.calendar("tenant-a", "institutional", "period-a", date(2026, 10, 1),
                        date(2026, 10, 31), {"role": "student", "student_id": "student-a"})
    assert caught.value.code == "projection_forbidden"
