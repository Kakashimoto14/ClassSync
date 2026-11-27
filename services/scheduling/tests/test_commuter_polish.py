"""Commuter daily-shape polish and the 180-minute split/block pattern policy."""

import pytest
from classync_contracts.academic import AcademicConstraints
from classync_contracts.scheduling import (
    Assignment,
    DailyShapeRules,
    GenerationInput,
    scheduling_input_hash,
)
from pydantic import ValidationError

from services.academic.app.record_rules import default_constraints, initial_records
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.engine import generate_week, restrict_patterns
from services.scheduling.app.polish import polish_timetable
from services.scheduling.app.readiness import shape_rule_warnings
from services.scheduling.app.validation import validate_timetable
from services.scheduling.tests.test_engine import tiny

SINGLE = [{"id": "one", "durations": [180]}]
BOTH = [{"id": "one", "durations": [180]}, {"id": "two", "durations": [90, 90]}]


def week(count, patterns=SINGLE, *, days=range(5), rules=None, buffer=0, **teacher):
    """`count` offerings of one section, one instructor and one room, 07:00-21:00."""
    raw = tiny(patterns, count=count).model_dump()
    windows = [{"day": day, "start": 420, "end": 1260} for day in days]
    raw["operating_windows"] = windows
    raw["rooms"][0]["availability"] = windows
    raw["rooms"][0]["blocked"] = []
    raw["teachers"][0].update(availability=windows, unavailable=[], preferred_days=[], **teacher)
    raw["sections"][0]["preferred_days"] = []
    raw["transition_buffer_minutes"] = buffer
    raw["daily_shape"] = rules or {
        "min_sessions_per_active_day": 2,
        "max_sessions_per_day": 4,
        "max_daily_span_minutes": 540,
    }
    return GenerationInput.model_validate(raw)


def at(inputs, index, day, start, *, length=180, **changes):
    offering = inputs.offerings[index]
    return Assignment(
        id=f"a{index}-{day}-{start}",
        offering_id=offering.id,
        day=day,
        start=start,
        end=start + length,
        room_id=inputs.rooms[0].id,
        teacher_id=inputs.teachers[0].id,
        section_id=offering.section_id,
        subject_id=offering.subject_id,
    ).model_copy(update=changes)


def run(inputs, assignments, **options):
    """Polish with the full independent validator re-run after every accepted move."""
    assert validate_timetable(inputs, assignments).valid
    polished, report = polish_timetable(
        inputs, assignments, verify=True, wall_seconds=60, **options
    )
    assert validate_timetable(inputs, polished).valid
    assert not report.truncated
    return polished, report


def test_one_class_days_are_consolidated_and_the_result_is_deterministic():
    inputs = week(4)
    scattered = [at(inputs, i, i, 420) for i in range(4)]
    polished, report = run(inputs, scattered)
    assert report.before.orphan_section_days == 4
    assert report.after.orphan_section_days == report.after.short_section_days == 0
    assert report.after.over_span_section_days == 0 and report.unmet == []
    assert report.moves >= 2
    assert run(inputs, scattered)[0] == polished


def test_a_fourteen_hour_day_is_shortened():
    inputs = week(2)
    polished, report = run(inputs, [at(inputs, 0, 4, 420), at(inputs, 1, 4, 1080)])
    assert report.before.max_span_minutes == 840
    assert report.after.max_span_minutes <= 540
    assert len({a.day for a in polished}) == 1


def test_an_unreachable_preference_is_reported_not_turned_into_a_failure():
    # Three 180-minute blocks plus transition buffers need 10 hours on one operating day.
    inputs = week(3, days=[0], buffer=10)
    start = [at(inputs, 0, 0, 420), at(inputs, 1, 0, 630), at(inputs, 2, 0, 840)]
    _, report = run(inputs, start)
    assert [(i.day, i.sessions, i.issues) for i in report.unmet] == [(0, 3, ["over_span"])]


def test_flexible_offerings_may_split_to_fill_a_day():
    # One 180-minute block per day on two days, instructor capped at one block a day.
    inputs = week(2, BOTH, days=[0, 1], max_daily_minutes=270)
    polished, report = run(inputs, [at(inputs, 0, 0, 420), at(inputs, 1, 1, 420)])
    assert report.before.short_section_days == 2
    assert report.after.short_section_days == 0
    lengths = sorted(a.end - a.start for a in polished)
    assert lengths.count(90) >= 2 and sum(lengths) == 360


def test_polish_does_not_move_a_session_off_its_preferred_days():
    inputs = week(2)
    section = inputs.sections[0].model_copy(update={"preferred_days": [0, 1]})
    inputs = inputs.model_copy(update={"sections": [section]})
    polished, report = run(inputs, [at(inputs, 0, 0, 420), at(inputs, 1, 1, 420)])
    assert report.after.short_section_days == 0
    assert {a.day for a in polished} <= {0, 1}


def test_locked_sessions_and_previous_placements_never_move():
    inputs = week(2)
    first, second = at(inputs, 0, 0, 420), at(inputs, 1, 1, 420)
    for field in ("locked_assignments", "previous_assignments"):
        pinned = inputs.model_copy(update={field: [first, second]})
        polished, report = run(pinned, [first, second])
        assert report.moves == 0 and polished == [first, second]


@pytest.mark.parametrize(
    "teacher",
    [
        {"max_continuous_minutes": 180},
        {"max_daily_minutes": 180},
    ],
)
def test_instructor_limits_are_never_broken_to_satisfy_a_preference(teacher):
    inputs = week(2, days=[0, 1], **teacher)
    polished, report = run(inputs, [at(inputs, 0, 0, 420), at(inputs, 1, 1, 420)])
    if "max_daily_minutes" in teacher:
        assert len({a.day for a in polished}) == 2 and report.after.short_section_days == 2
    else:
        first, second = sorted(polished, key=lambda a: a.start)
        assert report.after.short_section_days == 0 and second.start - first.end >= 60


def test_unavailable_rooms_and_instructors_are_respected():
    inputs = week(2, days=[0, 1])
    raw = inputs.model_dump()
    raw["rooms"][0]["blocked"] = [{"day": 0, "start": 600, "end": 1260}]
    raw["teachers"][0]["unavailable"] = [{"day": 1, "start": 600, "end": 1260}]
    inputs = GenerationInput.model_validate(raw)
    start = [at(inputs, 0, 0, 420), at(inputs, 1, 1, 420)]
    polished, report = run(inputs, start)
    # Neither day can hold both blocks, so nothing may move onto a blocked interval.
    assert report.after.short_section_days == 2
    assert {(a.day, a.start) for a in polished} <= {(0, 420), (1, 420)}


def test_lectures_leave_specialized_rooms_when_a_classroom_is_free():
    inputs = week(2)
    raw = inputs.model_dump()
    lab = {**raw["rooms"][0], "id": "lab", "room_type": "computer_lab", "type_verified": True}
    raw["rooms"] = [raw["rooms"][0], lab]
    for offering in raw["offerings"]:
        offering["eligible_room_ids"] = ["lab", raw["rooms"][0]["id"]]
        offering["required_room_type"] = None
    inputs = GenerationInput.model_validate(raw)
    start = [at(inputs, 0, 0, 420, room_id="lab"), at(inputs, 1, 0, 600, room_id="lab")]
    polished, report = run(inputs, start)
    assert report.before.lectures_in_specialized_rooms == 2
    assert report.after.lectures_in_specialized_rooms == 0
    assert {a.room_id for a in polished} == {raw["rooms"][0]["id"]}


def test_the_evaluation_budget_bounds_the_search_deterministically():
    inputs = week(4)
    scattered = [at(inputs, i, i, 420) for i in range(4)]
    first, report = polish_timetable(inputs, scattered, budget=5, wall_seconds=60)
    assert report.evaluations == 5 and not report.truncated
    assert polish_timetable(inputs, scattered, budget=5, wall_seconds=60)[0] == first
    _, capped = polish_timetable(week(40, days=range(6)), [], wall_seconds=0)
    assert capped.moves == 0


def test_generation_polishes_only_periods_that_configure_rules():
    inputs = week(2)
    result = generate_week(inputs)
    assert result.metadata.polish.after.short_section_days == 0
    assert len({a.day for a in result.assignments}) == 1
    legacy = inputs.model_copy(update={"daily_shape": None})
    plain = generate_week(legacy)
    assert plain.metadata.polish is None
    assert "polish" not in plain.metadata.model_dump()


def test_absent_rules_keep_the_stored_payload_and_input_hash():
    inputs = tiny()
    assert "daily_shape" not in inputs.model_dump()
    assert scheduling_input_hash(inputs) == scheduling_input_hash(
        GenerationInput.model_validate(inputs.model_dump())
    )
    assert scheduling_input_hash(inputs) != scheduling_input_hash(week(1))
    assert {"daily_shape", "pattern_policy_180"}.isdisjoint(AcademicConstraints().model_dump())
    with pytest.raises(ValidationError, match="cannot exceed"):
        DailyShapeRules(min_sessions_per_active_day=3, max_sessions_per_day=2)


def test_new_periods_start_with_the_owner_authorized_preferences():
    rules = initial_records(False)[0]
    assert rules == default_constraints()
    assert rules.daily_shape.model_dump() == {
        "min_sessions_per_active_day": 2,
        "max_sessions_per_day": 4,
        "max_daily_span_minutes": 540,
    }
    assert rules.pattern_policy_180 == "flexible"


def test_campus_scale_inputs_offer_the_solver_one_pattern_except_for_locked_offerings():
    inputs = week(60, BOTH, days=range(6))
    locked = inputs.model_copy(update={"locked_assignments": [at(inputs, 0, 0, 420)]})
    reduced = restrict_patterns(locked)
    assert [len(o.patterns) for o in reduced.offerings] == [2] + [1] * 59
    small = week(2, BOTH)
    assert restrict_patterns(small) is small


def test_unreachable_shape_rules_warn_without_blocking():
    inputs = week(5, days=[0], rules={"max_sessions_per_day": 2, "max_daily_span_minutes": 120})
    codes = {d.code for d in shape_rule_warnings(inputs)}
    assert codes == {"shape_span_too_short", "shape_max_sessions_unreachable"}
    assert shape_rule_warnings(tiny()) == []


# -- pattern precedence through the persisted academic records --------------------------------
def readiness_patterns(tmp_path, *, period=None, subject=None, offering=None, **subject_fields):
    from services.academic.app.repository import AcademicRepository
    from services.academic.tests.test_academic import add, complete

    repo = AcademicRepository(tmp_path / "academic.sqlite3")
    repo.migrate()
    snapshot = complete(repo)
    pid = snapshot.period.id

    def update(kind, identity, **changes):
        current = repo.snapshot("sandbox", "development-academic-sandbox", pid)
        envelope = next(
            e for e in current.records if e.record.kind == kind and e.record.id == identity
        )
        add(repo, pid, {**envelope.record.model_dump(mode="json"), **changes}, envelope.revision)

    update("constraints", "rules", pattern_policy_180=period)
    update("subjects", "subject-a", pattern_policy=subject, **subject_fields)
    if offering:
        current = repo.snapshot("sandbox", "development-academic-sandbox", pid)
        identity = next(
            e.record.id
            for e in current.records
            if e.record.kind == "offerings" and e.record.subject_id == "subject-a"
        )
        update("offerings", identity, **offering)
    checked = academic_readiness(repo.snapshot("sandbox", "development-academic-sandbox", pid))
    assert checked.inputs is not None, [i.message for i in checked.issues]
    return {
        tuple(tuple(p.durations) for p in o.patterns)
        for o in checked.inputs.offerings
        if o.subject_id == "subject-a"
    }


ONE, TWO, EITHER = ((180,),), ((90, 90),), ((180,), (90, 90))
APPROVED = {"override_requirements_verified": True, "verification_reference": "synthetic test"}


@pytest.mark.parametrize(
    ("levels", "expected"),
    [
        ({}, {ONE}),
        ({"period": "split"}, {TWO}),
        ({"period": "flexible"}, {EITHER}),
        ({"period": "split", "subject": "single"}, {ONE}),
        ({"subject": "single", "offering": {**APPROVED, "pattern_policy": "split"}}, {TWO, ONE}),
        (
            {
                "offering": {
                    **APPROVED,
                    "pattern_policy": "split",
                    "patterns_override": [{"id": "x", "durations": [180]}],
                }
            },
            {ONE},
        ),
        # The period default keeps laboratory blocks whole; an explicit subject policy wins.
        ({"period": "split", "lab_hours": 3}, {ONE}),
        ({"period": "split", "lab_hours": 3, "subject": "split"}, {TWO}),
    ],
)
def test_pattern_policy_precedence(tmp_path, levels, expected):
    # `complete` has one offering of subject-a per section; an offering setting changes one.
    found = readiness_patterns(tmp_path, **levels)
    assert found == expected
