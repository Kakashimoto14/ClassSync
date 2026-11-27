"""Phase B hard and soft rules: continuous teaching, restrictions, audits and soft terms."""

from datetime import date

from classync_contracts.calendar import AcademicCalendar
from classync_contracts.scheduling import (
    Assignment,
    Diagnostic,
    GenerationInput,
    scheduling_input_hash,
)

from services.scheduling.app.engine import generate_week
from services.scheduling.app.readiness import capacity_audit
from services.scheduling.app.restriction_windows import weekly_blocks, with_room_restrictions
from services.scheduling.app.validation import teaching_blocks, validate_timetable
from services.scheduling.tests.test_engine import tiny

DAY = [{"day": 0, "start": 480, "end": 720}, {"day": 0, "start": 780, "end": 1020}]
LONG_DAYS = [{"day": d, "start": 420, "end": 1260} for d in (0, 1)]


def build(count, minutes, *, windows=DAY, weights=None, **teacher):
    raw = tiny(count=count).model_dump()
    raw["operating_windows"] = windows
    raw["rooms"][0]["availability"] = windows
    raw["teachers"][0]["availability"] = windows
    raw["teachers"][0].update(teacher)
    for offering in raw["offerings"]:
        offering["required_weekly_minutes"] = minutes
        offering["patterns"] = [{"id": f"one-{minutes}", "durations": [minutes]}]
    raw["options"]["weights"].update(weights or {})
    return GenerationInput.model_validate(raw)


def placed(inputs):
    result = generate_week(inputs)
    assert result.solver_status in {"optimal", "feasible"}, result.diagnostics
    assert validate_timetable(inputs, result.assignments).valid
    return result.assignments


def test_continuous_cap_allows_adjacent_pairs_within_the_limit():
    inputs = build(3, 120, max_continuous_minutes=240)
    assignments = placed(inputs)
    assert len(assignments) == 3
    assert all(
        sum(a.end - a.start for a in block) <= 240 for block in teaching_blocks(assignments)
    )


def test_continuous_cap_is_a_hard_constraint_not_a_dropped_offering():
    # Two 120-minute sessions need a 60-minute break; each 4-hour window then fits only one.
    result = generate_week(build(3, 120, max_continuous_minutes=120))
    assert result.solver_status == "infeasible"
    assert result.assignments == []


def test_continuous_cap_forbids_three_short_sessions_in_one_block():
    # 300 minutes: three 90s fit only without a 60-minute break between them.
    windows = [{"day": 0, "start": 480, "end": 780}]
    result = generate_week(build(3, 90, windows=windows, max_continuous_minutes=240))
    assert result.solver_status == "infeasible"
    assert [a.end - a.start for a in placed(build(2, 90, windows=windows,
                                                  max_continuous_minutes=240))] == [90, 90]


def test_validator_reports_continuous_teaching_blocks():
    inputs = build(3, 120, max_continuous_minutes=240)
    base = inputs.offerings
    assignments = [
        Assignment(
            id=f"a{i}", offering_id=base[i].id, day=0, start=start, end=start + 120,
            room_id=inputs.rooms[0].id, teacher_id=inputs.teachers[0].id,
            section_id=base[i].section_id, subject_id=base[i].subject_id,
        )
        for i, start in enumerate((480, 600, 780))
    ]
    # 08:00-12:00 is one 240-minute block; the 60-minute lunch break ends it.
    assert validate_timetable(inputs, assignments).valid
    late = [*assignments[:2], assignments[2].model_copy(update={"start": 720, "end": 840})]
    codes = {c.code for c in validate_timetable(inputs, late, partial=True).conflicts}
    assert "teacher_continuous_teaching" in codes


def test_specialized_rooms_are_kept_for_offerings_that_need_them():
    raw = build(1, 180, weights={"specialized_rooms": 5}).model_dump()
    lab = {**raw["rooms"][0], "id": "lab", "room_type": "computer_lab"}
    raw["rooms"] = [lab, raw["rooms"][0]]
    raw["offerings"][0]["eligible_room_ids"] = ["lab", raw["rooms"][1]["id"]]
    assert placed(GenerationInput.model_validate(raw))[0].room_id != "lab"


def test_shift_compactness_keeps_a_section_day_in_one_shift():
    windows = [{"day": 0, "start": 420, "end": 1260}]
    assignments = placed(build(2, 120, windows=windows, weights={"shift_compactness": 5}))
    shifts = {(a.start >= 720) + (a.start >= 1020) for a in assignments}
    assert len(shifts) == 1


def test_faculty_rest_avoids_early_start_after_late_finish():
    raw = build(2, 180, windows=LONG_DAYS, weights={"faculty_rest": 5}).model_dump()
    first, second = raw["offerings"]
    raw["teachers"][0]["availability"] = LONG_DAYS
    raw["locked_assignments"] = [{
        "id": "late", "offering_id": first["id"], "day": 0, "start": 1080, "end": 1260,
        "room_id": raw["rooms"][0]["id"], "teacher_id": raw["teachers"][0]["id"],
        "section_id": first["section_id"], "subject_id": first["subject_id"],
    }]
    raw["operating_windows"] = LONG_DAYS
    raw["rooms"][0]["availability"] = LONG_DAYS
    raw["teachers"][0]["unavailable"] = [{"day": 0, "start": 420, "end": 1080}]
    other = next(a for a in placed(GenerationInput.model_validate(raw))
                 if a.offering_id == second["id"])
    assert other.day == 1 and other.start >= 510


def test_capacity_audit_names_the_bottleneck_and_its_setup_screen():
    windows = [{"day": 0, "start": 480, "end": 720}]
    raw = build(2, 180, windows=windows).model_dump()
    raw["operating_windows"] = DAY
    raw["teachers"][0]["availability"] = DAY
    rooms = capacity_audit(GenerationInput.model_validate(raw))
    assert [(d.code, d.action_path) for d in rooms] == [
        ("room_pool_capacity", "/admin/academic/resources")
    ]
    raw["rooms"][0]["availability"] = DAY
    raw["teachers"][0]["max_weekly_minutes"] = 180
    faculty = capacity_audit(GenerationInput.model_validate(raw))
    assert {(d.code, d.action_path) for d in faculty} == {
        ("faculty_pool_capacity", "/admin/teachers")
    }
    raw["teachers"][0]["max_weekly_minutes"] = None
    assert capacity_audit(GenerationInput.model_validate(raw)) == []


def test_transition_buffer_is_counted_in_capacity():
    windows = [{"day": 0, "start": 480, "end": 840}]
    raw = build(2, 180, windows=windows).model_dump()
    assert capacity_audit(GenerationInput.model_validate(raw)) == []
    raw["transition_buffer_minutes"] = 10
    codes = {d.code for d in capacity_audit(GenerationInput.model_validate(raw))}
    assert "room_pool_capacity" in codes and "section_time_capacity" in codes


CALENDAR = AcademicCalendar(
    academic_year="2026-2027", semester="first", effective_start=date(2026, 8, 3),
    effective_end=date(2026, 12, 18), timezone="Asia/Manila", instructional_days=[0, 1, 2, 3, 4, 5],
)


def test_dated_restrictions_become_weekly_room_blocks():
    blocks = weekly_blocks(
        [
            {"room_id": "r", "starts_at": "2026-09-02T10:00:00+08:00",
             "ends_at": "2026-09-02T12:15:00+08:00"},
            # Outside the term: ignored.
            {"room_id": "r", "starts_at": "2027-02-01T08:00:00+08:00",
             "ends_at": "2027-02-01T09:00:00+08:00"},
            # A Sunday is not an instructional day.
            {"room_id": "s", "starts_at": "2026-09-06T08:00:00+08:00",
             "ends_at": "2026-09-06T10:00:00+08:00"},
        ],
        CALENDAR,
    )
    assert [(w.day, w.start, w.end) for w in blocks["r"]] == [(2, 600, 750)]
    assert "s" not in blocks
    week = weekly_blocks(
        [{"room_id": "r", "starts_at": "2026-09-07T00:00:00+08:00",
          "ends_at": "2026-09-21T00:00:00+08:00"}],
        CALENDAR,
    )
    assert [(w.day, w.start, w.end) for w in week["r"]] == [(d, 0, 1440) for d in range(6)]


def test_generation_never_uses_a_restricted_weekly_time():
    inputs = build(1, 180)
    room = inputs.rooms[0].id
    restricted = with_room_restrictions(
        inputs,
        restrictions=[{"room_id": room, "starts_at": "2026-09-07T08:00:00+08:00",
                       "ends_at": "2026-09-07T12:00:00+08:00"}],
        calendar=CALENDAR,
    )
    assert [(w.day, w.start, w.end) for w in restricted.rooms[0].blocked] == [(0, 480, 720)]
    assert placed(restricted)[0].start >= 780
    assert inputs.rooms[0].blocked == []


def test_new_fields_preserve_existing_hashes_and_snapshots():
    inputs = tiny()
    raw = inputs.model_dump(mode="json")
    for key in ("specialized_rooms", "shift_compactness", "faculty_rest"):
        raw["options"]["weights"].pop(key)
    for teacher in raw["teachers"]:
        teacher.pop("max_continuous_minutes")
    legacy = GenerationInput.model_validate(raw)
    defaults = legacy.model_copy(deep=True)
    defaults.options.weights.specialized_rooms = 3
    assert scheduling_input_hash(legacy) == scheduling_input_hash(defaults)
    changed = legacy.model_copy(deep=True)
    changed.options.weights.faculty_rest = 9
    assert scheduling_input_hash(changed) != scheduling_input_hash(legacy)
    assert "action_path" not in Diagnostic(code="c", message="m").model_dump()
    assert Diagnostic(code="c", message="m", action_path="/admin/teachers").model_dump()[
        "action_path"
    ] == "/admin/teachers"


def test_two_step_repair_moves_a_flexible_lecture_out_of_the_way():
    from services.scheduling.app.repair import EVALUATION_LIMIT, Repair

    raw = build(2, 120, windows=[{"day": 0, "start": 480, "end": 720}]).model_dump()
    second = {**raw["teachers"][0], "id": "only-early", "name": "Early only",
              "availability": [{"day": 0, "start": 480, "end": 600}]}
    raw["teachers"].append(second)
    lecture, blocked = raw["offerings"]
    blocked["eligible_teacher_ids"] = ["only-early"]
    inputs = GenerationInput.model_validate(raw)

    def session(offering, start, teacher):
        return Assignment(
            id=offering["id"], offering_id=offering["id"], day=0, start=start, end=start + 120,
            room_id=raw["rooms"][0]["id"], teacher_id=teacher,
            section_id=offering["section_id"], subject_id=offering["subject_id"],
        )

    # The early-only instructor's class sits at 10:00 (invalid); 08:00 holds a movable lecture.
    current = [session(lecture, 480, raw["teachers"][0]["id"]),
               session(blocked, 600, "only-early")]
    repair = Repair(inputs, current)
    options = repair.suggest(current[1])
    assert options and repair.evaluations <= EVALUATION_LIMIT
    first = options[0]
    assert (first[blocked["id"]].start, first[lecture["id"]].start) == (480, 600)
    assert validate_timetable(inputs, [first[a.id] for a in current]).valid
    # A locked lecture is not flexible, so no two-step option exists.
    pinned = inputs.model_copy(update={"locked_assignments": [current[0]]})
    assert Repair(pinned, current).suggest(current[1]) == []


def occupancy_row(version, sequence, *, exceptions=(), buffer=0, period="p"):
    return {
        "period_id": period, "version_id": version, "version_rank": sequence,
        "projection": {
            "buffer": buffer,
            "assignments": [{"id": "a", "day": 0, "start": 480, "end": 570, "room_id": "r1"}],
            "calendar": {
                "effective_start": "2026-08-03", "effective_end": "2026-12-18",
                "instructional_days": [0, 1, 2, 3, 4, 5], "exceptions": list(exceptions),
            },
        },
    }


def test_room_only_projection_follows_publication_rules():
    from datetime import datetime

    from services.scheduling.app.occurrences import ZONE
    from services.scheduling.app.room_occupancy import occupied_rooms

    def slot(day, a, b):
        base = datetime.fromisoformat(f"{day}T00:00:00").replace(tzinfo=ZONE)
        return base.replace(hour=a // 60, minute=a % 60), base.replace(hour=b // 60, minute=b % 60)

    monday = "2026-09-07"
    assert occupied_rooms([occupancy_row("v1", 1)], *slot(monday, 540, 600)) == {"r1"}
    assert occupied_rooms([occupancy_row("v1", 1)], *slot(monday, 570, 600)) == set()
    # The transition buffer keeps the room from the adjacent half hour.
    assert occupied_rooms([occupancy_row("v1", 1, buffer=10)], *slot(monday, 570, 600)) == {"r1"}
    cancelled = {"date": monday, "assignment_id": "a", "cancelled": True, "moved_to": None,
                 "room_id": None, "start": None}
    assert occupied_rooms([occupancy_row("v1", 1, exceptions=[cancelled])],
                          *slot(monday, 480, 570)) == set()
    holiday = {**cancelled, "assignment_id": None}
    assert occupied_rooms([occupancy_row("v1", 1, exceptions=[holiday])],
                          *slot(monday, 480, 570)) == set()
    moved = {"date": monday, "assignment_id": "a", "cancelled": False,
             "moved_to": "2026-09-09", "room_id": "r2", "start": 600}
    rows = [occupancy_row("v1", 1, exceptions=[moved])]
    assert occupied_rooms(rows, *slot(monday, 480, 570)) == set()
    assert occupied_rooms(rows, *slot("2026-09-09", 600, 690)) == {"r2"}
    # The latest version for a period replaces earlier ones; other periods still count.
    newer = occupancy_row("v2", 2, exceptions=[cancelled])
    assert occupied_rooms([occupancy_row("v1", 1), newer], *slot(monday, 480, 570)) == set()
    other = occupancy_row("w1", 3, period="q")
    assert occupied_rooms([occupancy_row("v1", 1), newer, other],
                          *slot(monday, 480, 570)) == {"r1"}
    assert occupied_rooms([occupancy_row("v1", 1)], *slot("2027-01-04", 480, 570)) == set()
