"""Disposable institution-shaped records only; no original data or live identity."""

import pytest
from classync_contracts.publication import PublicationCommand
from classync_contracts.scheduling import Enrollment, SaveDraftRequest
from fastapi.testclient import TestClient

from services.scheduling.app import main
from services.scheduling.app import publication_api as api
from services.scheduling.app.draft_repository import DraftRepository
from services.scheduling.app.engine import generate_week
from services.scheduling.app.publication_repository import PublicationRepository
from services.scheduling.tests.test_calendar import configuration
from services.scheduling.tests.test_engine import tiny


@pytest.fixture
def institutional_publication(tmp_path, monkeypatch):
    inputs = tiny()
    # Test the institutional schema path with explicit disposable records. These
    # provenance labels do not claim real institutional verification or imports.
    inputs.synthetic = False
    for room in inputs.rooms:
        room.source = "administrator-supplied"
    inputs.enrollments = [
        Enrollment(student_id="synthetic-student", offering_ids=[inputs.offerings[0].id])
    ]
    result = generate_week(inputs)
    assert result.solver_status in {"optimal", "feasible"}
    assert result.validation.valid
    drafts = DraftRepository(tmp_path / "projection.sqlite3")
    drafts.migrate()
    drafts.remember_run(inputs, result, "administrator", "synthetic-admin")
    draft, _ = drafts.save(
        SaveDraftRequest(
            run_id=result.run_id,
            input_hash=result.input_hash,
            title="Disposable projection fixture",
            idempotency_key="disposable-projection-save",
        ),
        "administrator",
        "synthetic-admin",
    )
    publication = PublicationRepository(drafts)
    publication.publish(
        PublicationCommand(
            draft_id=draft.id,
            source="administrator",
            dataset="institutional",
            expected_version=0,
            expected_academic_revision=1,
            idempotency_key="disposable-projection-publish",
            calendar=configuration().calendar,
        ),
        draft,
        "synthetic-tenant",
        "synthetic-admin",
        commit=True,
    )
    monkeypatch.setattr(api, "settings_and_repo", lambda: (main.settings, publication))
    return draft.period_id, result.assignments[0].teacher_id


@pytest.mark.parametrize(
    "role,linked",
    [
        ("student", True),
        ("student", False),
        ("teacher", True),
        ("teacher", False),
    ],
)
def test_institutional_http_projection_uses_linked_records_not_uid(
    institutional_publication, identity_adapters, role, linked
):
    period, faculty = institutional_publication
    record = "synthetic-student" if role == "student" else faculty
    field = "student_id" if role == "student" else "faculty_id"
    identity_adapters(
        main,
        role,
        uid=record if not linked else "distinct-authentication-uid",
        **{field: record if linked else "unrelated-record"},
    )
    client = TestClient(main.app)
    headers = {"Authorization": "Bearer e30.e30.synthetic-signature"}
    periods = client.get("/api/v1/timetables/periods", headers=headers)
    assert periods.status_code == 200
    assert bool(periods.json()["periods"]) is linked
    response = client.get(
        f"/api/v1/timetables/calendar/{period}",
        headers=headers,
        params={"start": "2026-10-01", "end": "2026-10-31"},
    )
    assert response.status_code == (200 if linked else 403), response.text
    if linked:
        assert response.json()["occurrences"]
        assert response.json()["sections"] == []
        assert response.json()["teachers"] == []
        assert all("students" not in item for item in response.json()["occurrences"])
