import hashlib
import json
from copy import deepcopy

import pytest
from classync_contracts.academic import AcademicSnapshot, PeriodCreate, RecordWrite
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.curriculum import catalog
from classync_contracts.scheduling import (
    Assignment,
    GenerationInput,
    Offering,
    SessionPattern,
    scheduling_input_hash,
)

from scripts import build_curriculum_review_catalog as catalog_builder
from services.academic.app.cohort_pilot import pilot_records
from services.academic.app.curriculum_catalog import subject_from_course
from services.academic.app.record_rules import AcademicError, validate_record
from services.academic.app.repository import AcademicRepository
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.engine import generate_week
from services.scheduling.app.validation import validate_timetable

from .synthetic_review_inputs import install_synthetic_review, write_csv


def snapshot():
    records = pilot_records()
    for record in records:
        if record.kind == "sections":
            record.period_id = "synthetic-review"
    return AcademicSnapshot.model_validate(
        dict(
            period=dict(
                id="synthetic-review",
                title="Synthetic pilot",
                revision=1,
                created_at="2026-10-31T00:00:00Z",
                source="development-entered",
                calendar=AcademicCalendar(
                    academic_year="2026-2027",
                    semester="first",
                    effective_start="2026-10-01",
                    effective_end="2026-12-31",
                    instructional_days=[0, 1, 2, 3, 4, 5],
                ),
            ),
            records=[
                dict(
                    record=r,
                    revision=1,
                    updated_at="2026-10-31T00:00:00Z",
                    updated_by="synthetic-review",
                )
                for r in records
            ],
        )
    )


def test_packaged_runtime_catalog_preserves_all_sources_and_rows():
    data = catalog()
    assert len(data["versions"]) == 39
    assert len(data["courses"]) == 2062
    assert len({v["program"] for v in data["versions"]}) == 8
    assert len({v["source_sha256"] for v in data["versions"]}) == 20
    assert all(v["source_archive_member"] for v in data["versions"])
    assert len({v["id"] for v in data["versions"]}) == 39
    assert len({c["id"] for c in data["courses"]}) == 2062
    # Independent sources survive identical bytes; API copies cannot alter evidence.
    data["courses"][0]["subject_code"] = "CHANGED"
    assert catalog()["courses"][0]["subject_code"] != "CHANGED"


def test_catalog_builder_preserves_synthetic_source_rows_and_distinct_cohorts(
    monkeypatch, tmp_path
):
    fixture = install_synthetic_review(monkeypatch, tmp_path)
    data = catalog_builder.build()
    assert data == fixture.catalog
    assert len(data["versions"]) == 39 and len(data["courses"]) == 2062
    assert all(v["review_status"] == "unreviewed" for v in data["versions"])
    pair = [v for v in data["versions"] if v["entry_cohort"] in {"2023", "2024"}]
    assert len(pair) == 2 and pair[0]["source_sha256"] == pair[1]["source_sha256"]
    assert pair[0]["id"] != pair[1]["id"]
    assert {c["curriculum_version_id"] for c in data["courses"]} == {
        v["id"] for v in data["versions"]
    }


def test_course_keys_survive_extraction_row_reordering(monkeypatch, tmp_path):
    fixture = install_synthetic_review(monkeypatch, tmp_path)
    original = catalog_builder.rows
    monkeypatch.setattr(
        catalog_builder,
        "rows",
        lambda name: (
            list(reversed(original(name))) if name.startswith("all_programs") else original(name)
        ),
    )
    assert {c["id"] for c in catalog_builder.build()["courses"]} == {
        c["id"] for c in fixture.catalog["courses"]
    }


@pytest.mark.parametrize("change", [{"pdf_sha256": "0" * 64}, {"pdf_page": "4"}])
def test_catalog_builder_rejects_synthetic_course_provenance_mismatch(
    monkeypatch, tmp_path, change
):
    fixture = install_synthetic_review(monkeypatch, tmp_path)
    rows = [dict(row) for row in fixture.courses]
    rows[0].update(change)
    write_csv(fixture.kit / "all_programs_curriculum_extracted_REVIEW_ONLY.csv", rows)
    with pytest.raises(AssertionError):
        catalog_builder.build()


def test_legacy_saved_input_hash_remains_valid_with_new_optional_fields():
    from services.scheduling.tests.test_engine import tiny

    inputs = tiny()
    for teacher in inputs.teachers:
        teacher.synthetic = False
    legacy = inputs.model_dump(mode="json")
    legacy["enrollments"] = [
        {"student_id": "legacy-student", "offering_ids": [inputs.offerings[0].id]}
    ]
    for teacher in legacy["teachers"]:
        teacher.pop("synthetic")
        for key in ("max_weekly_minutes", "max_daily_minutes"):
            if teacher[key] is None:
                teacher.pop(key)
    expected = hashlib.sha256(
        json.dumps(legacy, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert scheduling_input_hash(GenerationInput.model_validate(legacy)) == expected


def test_source_course_minutes_do_not_inherit_180_default():
    row = catalog()["courses"][0]
    subject = subject_from_course(row["id"])
    assert subject.required_weekly_minutes is None and subject.patterns == []
    raw = subject.model_dump(exclude={"required_weekly_minutes", "patterns"})
    assert (
        RecordWrite.model_validate(
            dict(expected_revision=0, record=raw)
        ).record.required_weekly_minutes
        is None
    )


@pytest.mark.parametrize(
    "change", [{"code": "ITASE1"}, {"name": "Renamed"}, {"curriculum_version_id": "missing"}]
)
def test_exact_source_subject_match_not_alias(change):
    row = next(c for c in catalog()["courses"] if c["subject_code"] == "ITIASE1")
    record = subject_from_course(row["id"]).model_copy(update=change)
    with pytest.raises(AcademicError, match="exact version-scoped"):
        validate_record(record, "synthetic-review", lambda *args: object())


def test_binding_and_source_subject_are_persisted_and_cannot_auto_upgrade(tmp_path):
    repo = AcademicRepository(tmp_path / "review.sqlite3")
    repo.migrate()
    saved = repo.create_period(
        PeriodCreate(
            title="Synthetic",
            include_cdm_catalog=False,
            calendar=AcademicCalendar(
                academic_year="2026-2027",
                semester="first",
                effective_start="2026-10-01",
                effective_end="2026-12-31",
                instructional_days=[0, 1, 2, 3, 4, 5],
            ),
        ),
        "sandbox",
        "review",
    )
    for record in pilot_records():
        if record.kind == "sections":
            record = record.model_copy(update={"period_id": saved.period.id})
        saved = repo.save(
            "sandbox",
            "review",
            saved.period.id,
            record.kind,
            record.id,
            RecordWrite(
                expected_revision=next(
                    (
                        e.revision
                        for e in saved.records
                        if e.record.id == record.id and e.record.kind == record.kind
                    ),
                    0,
                ),
                record=record,
            ),
        )
    assert academic_readiness(saved).ready
    entry = next(
        e
        for e in saved.records
        if e.record.kind == "sections" and e.record.entry_cohort_year == 2024
    )
    other = next(
        v for v in catalog()["versions"] if v["program"] == "BSIT" and v["entry_cohort"] == "2026"
    )
    changed = entry.record.model_copy(update={"year_level": 4, "section_letter": "B"})
    saved = repo.save(
        "sandbox",
        "review",
        saved.period.id,
        "sections",
        changed.id,
        RecordWrite(expected_revision=entry.revision, record=changed),
    )
    assert (
        next(e.record for e in saved.records if e.record.id == changed.id).entry_cohort_year == 2024
    )
    before = saved.model_dump_json()
    with pytest.raises(AcademicError, match="automatically migrated"):
        repo.save(
            "sandbox",
            "review",
            saved.period.id,
            "sections",
            changed.id,
            RecordWrite(
                expected_revision=entry.revision + 1,
                record=changed.model_copy(
                    update={"entry_cohort_year": 2026, "curriculum_version_id": other["id"]}
                ),
            ),
        )
    assert repo.snapshot("sandbox", "review", saved.period.id).model_dump_json() == before


def test_pilot_is_hypothetical_three_candidates_per_code_and_exact_versions():
    saved = snapshot()
    checked = academic_readiness(saved)
    assert checked.ready, checked.issues
    assert checked.inputs.synthetic
    assert len(checked.inputs.teachers) == 81 and all(t.synthetic for t in checked.inputs.teachers)
    assert len(checked.inputs.offerings) == 27
    assert all(len(o.eligible_teacher_ids) == 3 for o in checked.inputs.offerings)
    assert all(not t.institutional_id for t in pilot_records() if t.kind == "faculty")
    third = next(
        e.record for e in saved.records if e.record.kind == "sections" and e.record.year_level == 3
    )
    codes = {
        c["subject_code"]
        for c in catalog()["courses"]
        if c["curriculum_version_id"] == third.curriculum_version_id
    }
    assert "ITIASE1" in codes and "ITELEC3" in codes and "ITDMATH" not in codes


def test_enrollment_cannot_attach_an_unbound_subject_to_a_version():
    saved = snapshot()
    records = {(e.record.kind, e.record.id): e.record for e in saved.records}
    rules = next(e.record for e in saved.records if e.record.kind == "constraints")
    offering = records[("offerings", rules.enrollments[0].offering_ids[0])]
    subject = records[("subjects", offering.subject_id)]
    records[("subjects", offering.subject_id)] = subject.model_copy(
        update={"curriculum_version_id": None, "curriculum_course_id": None}
    )
    with pytest.raises(AcademicError, match="retain its assigned curriculum"):
        validate_record(
            rules, saved.period.id, lambda kind, identity: records.get((kind, identity))
        )


def test_unreviewed_curriculum_synthetic_faculty_and_provisional_rooms_block_real():
    saved = snapshot()
    for envelope in saved.records:
        if envelope.record.kind == "resources":
            envelope.record.source = "cdm-provisional"
            envelope.record.schedulable = False
    checked = academic_readiness(saved)
    assert not checked.ready
    codes = {i.code for i in checked.issues}
    assert {"curriculum_unreviewed", "contact_minutes_unverified", "synthetic_faculty"} <= codes


def test_synthetic_records_in_institutional_period_cannot_enter_simulation_mode():
    saved = snapshot()
    saved.period = saved.period.model_copy(update={"source": "institutional"})
    for envelope in saved.records:
        if envelope.record.kind == "resources":
            envelope.record.source = "synthetic"
        elif envelope.record.kind == "faculty":
            envelope.record.synthetic = True
    checked = academic_readiness(saved)
    codes = {i.code for i in checked.issues}
    assert not checked.ready and checked.inputs is None
    assert {"synthetic_faculty", "noninstitutional_room", "cohort_assignment_unverified"} <= codes


def test_application_candidates_cannot_be_relabelled_as_institutional_inputs():
    from services.scheduling.app.catalog import synthetic_scenario
    from services.scheduling.app.readiness import readiness

    inputs = synthetic_scenario()
    assert all(t.synthetic for t in inputs.teachers)
    inputs.synthetic = False
    for room in inputs.rooms:
        room.source = "administrator-supplied"
    assert "synthetic_faculty" in {d.code for d in readiness(inputs)}
    assert generate_week(inputs).solver_status == "invalid_input"


def test_independent_validation_feasible_infeasible_and_cross_institute_locks():
    inputs = academic_readiness(snapshot()).inputs
    # Test-only feasibility settings; no policy or source hours inferred.
    inputs.options.weights = inputs.options.weights.model_copy(
        update=dict.fromkeys(type(inputs.options.weights).model_fields, 0)
    )
    shared_room = inputs.rooms[0].id
    teacher = inputs.teachers[0].id
    for index, institute in enumerate(("IBE", "ITE")):
        program = inputs.programs[0].model_copy(update={"id": institute, "institute": institute})
        inputs.programs.append(program)
        section = inputs.sections[0].model_copy(
            update={"id": f"SYN-{institute}", "program_id": institute}
        )
        inputs.sections.append(section)
        oid = f"SYN-lock-{institute}"
        inputs.offerings.append(
            Offering(
                id=oid,
                subject_id=oid,
                subject_name="Synthetic shared lock",
                section_id=section.id,
                eligible_teacher_ids=[teacher],
                eligible_room_ids=[shared_room],
                patterns=[SessionPattern(id="one-180", durations=[180])],
            )
        )
        inputs.locked_assignments.append(
            Assignment(
                id=oid,
                offering_id=oid,
                subject_id=oid,
                section_id=section.id,
                teacher_id=teacher,
                room_id=shared_room,
                day=0,
                start=420 + index * 180,
                end=600 + index * 180,
            )
        )
    result = generate_week(inputs)
    assert result.solver_status in {"feasible", "optimal"}, result.diagnostics
    assert validate_timetable(inputs, result.assignments).valid
    assert len(result.assignments) == 56
    conflicting = inputs.model_copy(deep=True)
    conflicting.locked_assignments[1] = conflicting.locked_assignments[1].model_copy(
        update={
            "day": conflicting.locked_assignments[0].day,
            "start": conflicting.locked_assignments[0].start,
            "end": conflicting.locked_assignments[0].end,
        }
    )
    assert generate_week(conflicting).solver_status == "infeasible"
    assert not validate_timetable(conflicting, conflicting.locked_assignments).valid
    corrupted = deepcopy(result.assignments)
    corrupted[0] = corrupted[1].model_copy(update={"id": corrupted[0].id})
    assert not validate_timetable(inputs, corrupted).valid
    impossible = inputs.model_copy(deep=True)
    impossible.rooms[0].availability = []
    assert generate_week(impossible).solver_status not in {"feasible", "optimal"}
