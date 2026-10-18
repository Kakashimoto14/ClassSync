from datetime import date

import pytest
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.scheduling import SaveDraftRequest
from pydantic import ValidationError

from services.academic.app.fixtures import FixtureRequest, import_fixture
from services.academic.app.repository import AcademicRepository
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_repository import DraftRepository
from services.scheduling.app.engine import generate_week
from services.scheduling.app.occurrences import occurrences


def configuration(**kwargs):
    return FixtureRequest.model_validate(
        {
            "calendar": {
                "academic_year": "2026-2027",
                "semester": "first",
                "effective_start": "2026-10-01",
                "effective_end": "2026-12-31",
                "phases": [
                    {"name": "midterm", "start": "2026-10-01", "end": "2026-11-15"},
                    {"name": "final", "start": "2026-11-16", "end": "2026-12-31"},
                ],
            },
            **kwargs,
        }
    )


def test_calendar_edits_are_versioned_without_overwriting_records(tmp_path):
    from classync_contracts.academic import CalendarWrite

    from services.academic.app.repository import AcademicError

    repo = AcademicRepository(tmp_path / "calendar-edit.db")
    repo.migrate()
    original = import_fixture(repo, configuration(), "sandbox", "test")
    calendar = original.period.calendar.model_copy(deep=True)
    calendar.instructional_days = [0, 1, 2, 3]
    request = CalendarWrite(expected_revision=original.period.revision, calendar=calendar)
    edited = repo.save_calendar("sandbox", "test", original.period.id, request)
    assert edited.records == original.records
    assert edited.period.revision == original.period.revision + 1
    assert all(w.day != 4 for w in academic_readiness(edited).inputs.operating_windows)
    with pytest.raises(AcademicError, match="changed"):
        repo.save_calendar("sandbox", "test", original.period.id, request)


def test_idempotent_fixture_generation_calendar_and_draft_integrity(tmp_path):
    repo = AcademicRepository(tmp_path / "academic.db")
    repo.migrate()
    config = configuration()
    snapshot = import_fixture(repo, config, "sandbox", "test")
    assert snapshot == import_fixture(repo, config, "sandbox", "test")
    provisional = [
        e.record
        for e in snapshot.records
        if e.record.kind == "resources" and e.record.source == "cdm-provisional"
    ]
    assert len(provisional) == 59
    assert all(r.capacity is None and not r.capacity_verified for r in provisional)
    checked = academic_readiness(snapshot)
    assert checked.ready and checked.inputs.synthetic
    assert checked.assigned_faculty == 2
    assert checked.faculty == 132
    result = generate_week(checked.inputs)
    assert result.solver_status in {"feasible", "optimal"}
    assert result.validation.valid and result.hard_conflict_count == 0
    store = DraftRepository(tmp_path / "drafts.db")
    store.migrate()
    store.remember_run(checked.inputs, result, "academic-sandbox", "test")
    draft, _ = store.save(
        SaveDraftRequest(
            run_id=result.run_id,
            input_hash=result.input_hash,
            title="C1 generated",
            idempotency_key="c1-test-key",
        ),
        "academic-sandbox",
        "test",
    )
    before = draft.model_dump_json()
    events = occurrences(
        checked.inputs, result.assignments, config.calendar, date(2026, 10, 1), date(2026, 10, 31)
    )
    assert events and all(o["starts_at"].endswith("+08:00") for o in events)
    assert len(events) == len({o["id"] for o in events})
    assert all(o["section"]["name"] == "BSIT 3A" for o in events)
    assert store.get(draft.id, "academic-sandbox", "test").model_dump_json() == before
    day = date.fromisoformat(events[0]["date"])
    altered = config.calendar.model_copy(update={"exceptions": []})
    from classync_contracts.calendar import CalendarException

    altered.exceptions = [CalendarException(date=day, reason="Holiday")]
    assert not occurrences(checked.inputs, result.assignments, altered, day, day)


def test_all_program_year_semester_catalog_and_certificate_structure(tmp_path):
    repo = AcademicRepository(tmp_path / "a.db")
    repo.migrate()
    snapshot = import_fixture(
        repo,
        configuration(
            program_ids=["bsit", "tcp"],
            year_levels=[1, 2, 3, 4],
            section_letters=["A", "B", "C", "D"],
            certificate_groups=["Professional cohort"],
        ),
        "sandbox",
        "test",
    )
    sections = [e.record for e in snapshot.records if e.record.kind == "sections"]
    assert len(sections) == 17
    tcp = next(s for s in sections if s.program_id == "tcp")
    assert (
        tcp.year_level is None
        and tcp.section_letter is None
        and tcp.custom_label == "Professional cohort"
    )
    subjects = [e.record for e in snapshot.records if e.record.kind == "subjects"]
    assert len(subjects) == 132 and all(s.provenance == "synthetic" for s in subjects)


def test_semester_phases_validate_without_duplicating_hours():
    body = configuration().calendar
    assert len(body.phases) == 2
    with pytest.raises(ValidationError):
        AcademicCalendar.model_validate(
            {**body.model_dump(mode="json"), "effective_end": "2026-09-01"}
        )
    with pytest.raises(ValidationError):
        AcademicCalendar.model_validate(
            {
                **body.model_dump(mode="json"),
                "phases": [{"name": "midterm", "start": "2026-09-01", "end": "2026-12-31"}],
            }
        )
