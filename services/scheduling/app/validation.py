"""Reusable candidate validation: no solver variables, state, or CP-SAT dependency."""

from collections import Counter, defaultdict
from itertools import combinations

from classync_contracts.scheduling import Coverage, Diagnostic, GenerationInput, ValidationResult

from .readiness import contains, eligible_room, intersects, readiness


def same_placement(a, b):
    return all(
        getattr(a, key) == getattr(b, key)
        for key in (
            "offering_id",
            "day",
            "start",
            "end",
            "room_id",
            "teacher_id",
            "section_id",
            "subject_id",
        )
    )


def validate_timetable(inputs: GenerationInput, assignments, *, partial=False):
    errors = list(readiness(inputs))
    offerings = {o.id: o for o in inputs.offerings}
    teachers = {t.id: t for t in inputs.teachers}
    rooms = {r.id: r for r in inputs.rooms}
    sections = {s.id: s for s in inputs.sections}
    by_offering = defaultdict(list)
    seen = set()

    def issue(code, message, ids):
        errors.append(Diagnostic(code=code, message=message, assignment_ids=ids))

    for a in assignments:
        if a.id in seen:
            issue("duplicate_assignment", "Assignment IDs must be unique.", [a.id])
        seen.add(a.id)
        o = offerings.get(a.offering_id)
        room, teacher = rooms.get(a.room_id), teachers.get(a.teacher_id)
        if (
            not o
            or not room
            or not teacher
            or o.section_id not in sections
            or a.subject_id != o.subject_id
            or a.section_id != o.section_id
        ):
            issue(
                "invalid_reference", "Assignment identity or academic reference is invalid.", [a.id]
            )
            continue
        by_offering[o.id].append(a)
        if a.teacher_id not in o.eligible_teacher_ids or a.room_id not in o.eligible_room_ids:
            issue("ineligible_assignment", "Instructor or room is not explicitly eligible.", [a.id])
        if not eligible_room(room, o, sections[o.section_id].program_id):
            issue(
                "room_requirements",
                "Room cannot satisfy the supplied verified constraints.",
                [a.id],
            )
        if not contains(inputs.operating_windows, a.day, a.start, a.end):
            issue("operating_hours", "Session is outside an allowed operating interval.", [a.id])
        if not contains(teacher.availability, a.day, a.start, a.end) or intersects(
            teacher.unavailable, a.day, a.start, a.end
        ):
            issue("teacher_unavailable", "Teacher is unavailable for the full interval.", [a.id])
        if not contains(room.availability, a.day, a.start, a.end) or intersects(
            room.blocked, a.day, a.start, a.end
        ):
            issue("room_unavailable", "Room is unavailable for the full interval.", [a.id])
    coverage = []
    for o in inputs.offerings:
        values = by_offering[o.id]
        minutes = sum(a.end - a.start for a in values)
        coverage.append(
            Coverage(
                offering_id=o.id,
                required_minutes=o.required_weekly_minutes,
                allocated_minutes=minutes,
            )
        )
        if not partial:
            valid_pattern = any(
                Counter(p.durations) == Counter(a.end - a.start for a in values)
                and (not p.distinct_days or len({a.day for a in values}) == len(values))
                for p in o.patterns
            )
            if minutes != o.required_weekly_minutes or not valid_pattern:
                errors.append(
                    Diagnostic(
                        code="unsatisfied_requirement",
                        offering_id=o.id,
                        message="Weekly minutes, session pattern or distinct days are incorrect.",
                        assignment_ids=[a.id for a in values],
                    )
                )
        if len({a.teacher_id for a in values}) > 1:
            issue(
                "instructor_consistency",
                "One offering must have one eligible instructor.",
                [a.id for a in values],
            )
    enrollment_sets = [set(e.offering_ids) for e in inputs.enrollments]
    for teacher in inputs.teachers:
        taught = [a for a in assignments if a.teacher_id == teacher.id]
        if (
            teacher.max_weekly_minutes is not None
            and sum(a.end - a.start for a in taught) > teacher.max_weekly_minutes
        ):
            issue(
                "teacher_weekly_workload",
                "Instructor exceeds the supplied weekly workload limit.",
                [a.id for a in taught],
            )
        if teacher.max_daily_minutes is not None:
            for day in range(7):
                daily = [a for a in taught if a.day == day]
                if sum(a.end - a.start for a in daily) > teacher.max_daily_minutes:
                    issue(
                        "teacher_daily_workload",
                        "Instructor exceeds the supplied daily workload limit.",
                        [a.id for a in daily],
                    )
    for a, b in combinations(assignments, 2):
        a_start, a_end = a.day * 1440 + a.start, a.day * 1440 + a.end
        b_start, b_end = b.day * 1440 + b.start, b.day * 1440 + b.end
        buffer = inputs.transition_buffer_minutes
        if not any(
            a_start < b_end + offset + buffer and b_start + offset < a_end + buffer
            for offset in (-10080, 0, 10080)
        ):
            continue
        for key, label in (
            ("room_id", "room"),
            ("teacher_id", "teacher"),
            ("section_id", "section"),
        ):
            if getattr(a, key) == getattr(b, key):
                issue(
                    f"{label}_overlap",
                    f"Overlapping {label} assignments (including buffer).",
                    [a.id, b.id],
                )
        for i, enrolled in enumerate(enrollment_sets):
            if a.offering_id in enrolled and b.offering_id in enrolled:
                issue(
                    "student_overlap",
                    f"Student {inputs.enrollments[i].student_id} has "
                    "overlapping enrolled offerings.",
                    [a.id, b.id],
                )
    if not partial:
        for locked in inputs.locked_assignments:
            if not any(a.id == locked.id and same_placement(a, locked) for a in assignments):
                issue(
                    "locked_assignment_changed",
                    "A locked assignment is absent or changed.",
                    [locked.id],
                )
    return ValidationResult(
        valid=not errors, hard_conflict_count=len(errors), conflicts=errors, coverage=coverage
    )
