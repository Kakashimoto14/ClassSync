from copy import deepcopy

import pytest
from classync_contracts.scheduling import Assignment, GenerationInput
from ortools.sat.python import cp_model
from pydantic import ValidationError

from services.scheduling.app.catalog import catalogs, synthetic_scenario
from services.scheduling.app.engine import generate_week
from services.scheduling.app.validation import validate_timetable


def tiny(patterns=None, *, count=1):
    raw = synthetic_scenario().model_dump()
    raw["programs"] = raw["programs"][:1]
    raw["sections"] = [s for s in raw["sections"] if s["program_id"] == raw["programs"][0]["id"]][
        :1
    ]
    raw["rooms"] = [raw["rooms"][0]]
    raw["teachers"] = [raw["teachers"][0]]
    raw["enrollments"] = []
    first = deepcopy(raw["offerings"][0])
    first.update(
        section_id=raw["sections"][0]["id"],
        eligible_teacher_ids=[raw["teachers"][0]["id"]],
        eligible_room_ids=[raw["rooms"][0]["id"]],
    )
    if patterns is not None:
        first["patterns"] = patterns
    raw["offerings"] = [{**first, "id": f"test-{i}"} for i in range(count)]
    raw["options"]["time_limit_seconds"] = 3.0
    raw["options"]["weights"] = dict.fromkeys(raw["options"]["weights"], 0)
    return GenerationInput.model_validate(raw)


def solve(inputs):
    result = generate_week(inputs)
    assert result.solver_status in {"optimal", "feasible"}, result.model_dump()
    assert result.validation.valid
    assert result.hard_conflict_count == 0
    assert validate_timetable(inputs, result.assignments).valid
    return result


def test_one_180_and_same_seed_are_reproducible():
    inputs = tiny()
    first = solve(inputs)
    assert len(first.assignments) == 1
    assert first.assignments[0].end - first.assignments[0].start == 180
    assert first.assignments == solve(inputs).assignments
    assert first.input_hash == solve(inputs).input_hash


def test_two_90_on_distinct_days():
    result = solve(tiny([{"id": "two", "durations": [90, 90], "distinct_days": True}]))
    assert len(result.assignments) == 2
    assert len({a.day for a in result.assignments}) == 2
    assert sum(a.end - a.start for a in result.assignments) == 180


def test_bad_weekly_duration_rejected():
    with pytest.raises(ValidationError, match="exactly required"):
        tiny([{"id": "bad", "durations": [120], "distinct_days": True}])


@pytest.mark.parametrize("shared", ["teacher", "room", "section", "student"])
def test_each_resource_excludes_overlapping_sessions(shared):
    inputs = tiny(count=2)
    # Isolate each contention: different sections, rooms and teachers unless shared.
    if shared != "section":
        other = inputs.sections[0].model_copy(update={"id": "other-section", "section_letter": "B"})
        inputs.sections.append(other)
        inputs.offerings[1].section_id = other.id
    if shared != "room":
        other = inputs.rooms[0].model_copy(update={"id": "other-room"})
        inputs.rooms.append(other)
        inputs.offerings[1].eligible_room_ids = [other.id]
    if shared != "teacher":
        other = inputs.teachers[0].model_copy(update={"id": "other-teacher"})
        inputs.teachers.append(other)
        inputs.offerings[1].eligible_teacher_ids = [other.id]
    if shared == "student":
        from classync_contracts.scheduling import Enrollment

        inputs.enrollments = [
            Enrollment(student_id="explicit-student", offering_ids=[o.id for o in inputs.offerings])
        ]
    result = solve(inputs)
    a, b = result.assignments
    assert a.day != b.day or a.end <= b.start or b.end <= a.start
    broken = b.model_copy(update={"day": a.day, "start": a.start, "end": a.end})
    validation = validate_timetable(inputs, [a, broken])
    assert not validation.valid
    assert any(
        c.code == f"{shared}_overlap" and set(c.assignment_ids) == {a.id, b.id}
        for c in validation.conflicts
    )


def test_availability_and_room_operations():
    from classync_contracts.scheduling import Window

    inputs = tiny()
    inputs.teachers[0].availability = [Window(day=2, start=480, end=720)]
    inputs.teachers[0].unavailable = [Window(day=2, start=480, end=510)]
    inputs.rooms[0].blocked = [Window(day=2, start=690, end=720)]
    result = solve(inputs)
    assert (result.assignments[0].day, result.assignments[0].start, result.assignments[0].end) == (
        2,
        510,
        690,
    )
    inputs.rooms[0].condition = "maintenance"
    result = generate_week(inputs)
    assert result.solver_status == "invalid_input"
    assert any(d.code == "no_eligible_room" for d in result.diagnostics)


def test_verified_capacity_equipment_type_and_program_restrictions():
    inputs = tiny()
    for update in (
        {"capacity": 10},
        {"capacity_verified": False},
        {"equipment_verified": False},
        {"type_verified": False},
        {"allowed_program_ids": []},
        {"building": "Excluded"},
    ):
        modified = inputs.model_copy(deep=True)
        modified.offerings[0].allowed_buildings = [inputs.rooms[0].building]
        for key, value in update.items():
            setattr(modified.rooms[0], key, value)
        assert generate_week(modified).solver_status == "invalid_input"


def test_locked_session_preserved_and_disruption_preference():
    inputs = tiny()
    a = solve(inputs).assignments[0]
    a.id = "locked-original"
    inputs.locked_assignments = [a]
    assert solve(inputs).assignments == [a]
    inputs.locked_assignments = []
    inputs.previous_assignments = [a]
    inputs.options.weights.disruption = 100
    assert solve(inputs).assignments[0].model_dump(exclude={"id"}) == a.model_dump(exclude={"id"})


def test_half_open_boundaries_and_transition_buffer():
    inputs = tiny(count=2)
    a = Assignment(
        id="a",
        offering_id="test-0",
        day=0,
        start=480,
        end=660,
        room_id=inputs.rooms[0].id,
        teacher_id=inputs.teachers[0].id,
        section_id=inputs.sections[0].id,
        subject_id=inputs.offerings[0].subject_id,
    )
    b = a.model_copy(update={"id": "b", "offering_id": "test-1", "start": 660, "end": 840})
    # Use one continuous operating interval so this tests boundaries, not lunch.
    from classync_contracts.scheduling import Window

    for target in (inputs, inputs.rooms[0], inputs.teachers[0]):
        setattr(
            target,
            "operating_windows" if target is inputs else "availability",
            [Window(day=0, start=480, end=900)],
        )
    assert validate_timetable(inputs, [a, b]).valid
    inputs.transition_buffer_minutes = 30
    assert any(c.code == "room_overlap" for c in validate_timetable(inputs, [a, b]).conflicts)


def test_infeasible_and_unknown_are_different(monkeypatch):
    inputs = tiny(count=2)
    from classync_contracts.scheduling import Window

    inputs.operating_windows = [Window(day=0, start=480, end=660)]
    result = generate_week(inputs)
    assert result.solver_status == "infeasible"
    assert not result.assignments and result.hard_conflict_count is None
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda *_: cp_model.UNKNOWN)
    result = generate_week(tiny())
    assert result.solver_status == "unknown"
    assert not result.assignments and result.validation is None
    assert "not been proven" in result.diagnostics[0].message


def test_time_limit_and_invalid_model_are_honest(monkeypatch):
    inputs = tiny()
    inputs.options.time_limit_seconds = 0.000001
    assert generate_week(inputs).solver_status == "unknown"
    monkeypatch.setattr(cp_model.CpModel, "validate", lambda *_: "test invalid model")
    assert generate_week(tiny()).solver_status == "invalid_model"


def test_complete_multi_program_batch_and_independent_minutes_check():
    inputs = synthetic_scenario()
    inputs.options.time_limit_seconds = 8.0
    result = solve(inputs)
    assert result.total_offerings_scheduled == result.total_offerings_requested == 12
    assert len({s.program_id for s in inputs.sections}) == 3
    assert all(c.required_minutes == c.allocated_minutes == 180 for c in result.coverage)
    assert any(a.end - a.start == 180 for a in result.assignments)
    assert any(a.end - a.start == 90 for a in result.assignments)
    assert not validate_timetable(inputs, result.assignments[:-1]).valid


def test_incomplete_and_missing_references():
    assert (
        generate_week(
            GenerationInput(period_id="p", data_version="v", scope_description="empty")
        ).solver_status
        == "invalid_input"
    )
    inputs = tiny()
    inputs.offerings[0].eligible_teacher_ids = ["unknown"]
    assert generate_week(inputs).solver_status == "invalid_input"


def test_cdm_inventory_and_program_policy():
    data = catalogs()
    assert len(data["cdm_spaces"]) == 59
    assert all(not r.schedulable and r.capacity is None for r in data["cdm_spaces"])
    assert not any(
        r.id in {"cdm-prrc-304", "cdm-prrc-305", "cdm-prrc-306"} for r in data["cdm_spaces"]
    )
    assert next(p for p in data["programs"] if p.id == "tcp").section_policy == "custom"


def test_nonstandard_lab_override_and_distinct_day_validation():
    from classync_contracts.scheduling import SessionPattern

    inputs = tiny()
    inputs.offerings[0].required_weekly_minutes = 240
    inputs.offerings[0].patterns = [SessionPattern(id="lab-240", durations=[120, 120])]
    result = solve(inputs)
    assert sum(a.end - a.start for a in result.assignments) == 240
    assert len({a.day for a in result.assignments}) == 2
    with pytest.raises(ValidationError, match="distinct"):
        SessionPattern(id="bad-two-day", durations=[90, 90], distinct_days=False)
    inputs = tiny([{"id": "two", "durations": [90, 90], "distinct_days": True}])
    a, b = solve(inputs).assignments
    b = b.model_copy(update={"day": a.day, "start": a.end, "end": a.end + 90})
    assert any(
        d.code == "unsatisfied_requirement" for d in validate_timetable(inputs, [a, b]).conflicts
    )


def test_conflicting_locks_and_instructor_consistency():
    inputs = tiny(count=2)
    values = solve(inputs).assignments
    values[1] = values[1].model_copy(
        update={"day": values[0].day, "start": values[0].start, "end": values[0].end}
    )
    inputs.locked_assignments = values
    assert generate_week(inputs).solver_status == "infeasible"


def test_unsuccessful_independent_validation_never_returns_success(monkeypatch):
    import services.scheduling.app.engine as engine

    original = engine.validate_timetable

    def reject(inputs, assignments, **kwargs):
        value = original(inputs, assignments, **kwargs)
        if not kwargs.get("partial"):
            value.valid = False
            value.hard_conflict_count = 1
        return value

    monkeypatch.setattr(engine, "validate_timetable", reject)
    result = engine.generate_week(tiny())
    assert result.solver_status == "validation_failed"
    assert result.assignments == []
    assert result.total_offerings_scheduled == 0


def test_buffer_across_midnight_and_recurring_week_boundary():
    from classync_contracts.scheduling import SessionPattern, Window

    inputs = tiny(count=2)
    windows = [Window(day=6, start=1380, end=1440), Window(day=0, start=0, end=60)]
    inputs.operating_windows = windows
    inputs.teachers[0].availability = windows
    inputs.rooms[0].availability = windows
    for offering in inputs.offerings:
        offering.required_weekly_minutes = 60
        offering.patterns = [SessionPattern(id="sixty", durations=[60])]
    result = solve(inputs)
    inputs.transition_buffer_minutes = 30
    assert not validate_timetable(inputs, result.assignments).valid
    assert generate_week(inputs).solver_status == "infeasible"
