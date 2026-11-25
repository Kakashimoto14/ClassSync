from datetime import UTC, datetime

from classync_contracts.academic import AcademicPeriod, AcademicSnapshot, RecordEnvelope

from scripts.seed_campus_data import (
    PERIOD_ID,
    PERIOD_TITLE,
    build_academic_records,
    defense_calendar,
    load_json,
)
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.engine import generate_week
from services.scheduling.app.validation import validate_timetable


def seeded_snapshot():
    records, _ = build_academic_records(
        PERIOD_ID, load_json("packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json")
    )
    now = datetime.now(UTC).isoformat()
    return AcademicSnapshot(
        period=AcademicPeriod(
            id=PERIOD_ID,
            title=PERIOD_TITLE,
            revision=1,
            created_at=now,
            source="institutional",
            calendar=defense_calendar(),
        ),
        records=[
            RecordEnvelope(revision=1, updated_at=now, updated_by="local-fixture", record=record)
            for record in records
        ],
    )


def test_seeded_defense_dataset_is_ready_and_generates_valid_complete_timetable():
    snapshot = seeded_snapshot()
    academic_records = [envelope.record for envelope in snapshot.records]
    rooms = [record for record in academic_records if record.kind == "resources"]
    assert len(rooms) == 41
    assert all(room.schedulable and room.capacity_verified and room.type_verified for room in rooms)
    readiness = academic_readiness(snapshot)
    assert readiness.ready and readiness.inputs is not None
    assert (readiness.subjects, readiness.sections, readiness.faculty, readiness.offerings) == (
        32,
        8,
        12,
        54,
    )
    result = generate_week(readiness.inputs)
    assert result.solver_status in {"feasible", "optimal"}
    assert result.total_offerings_scheduled == 54
    assert result.validation and result.validation.valid
    assert result.hard_conflict_count == 0
    assert not (
        {room.id for room in rooms if not room.schedulable}
        & {a.room_id for a in result.assignments}
    )


def test_manual_assignment_override_still_runs_independent_conflict_checks():
    snapshot = seeded_snapshot()
    inputs = academic_readiness(snapshot).inputs
    assert inputs is not None
    result = generate_week(inputs)
    assert len(result.assignments) >= 2
    first, second = result.assignments[:2]
    second = second.model_copy(
        update={
            "day": first.day,
            "start": first.start,
            "end": first.end,
            "room_id": first.room_id,
            "teacher_id": first.teacher_id,
            "section_id": first.section_id,
        }
    )
    assignments = [first, second, *result.assignments[2:]]
    checked = validate_timetable(inputs, assignments)
    codes = {issue.code for issue in checked.conflicts}
    assert not checked.valid
    assert {"room_overlap", "teacher_overlap", "section_overlap"} <= codes
