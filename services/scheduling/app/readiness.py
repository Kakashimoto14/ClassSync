"""Input/reference normalization and unary feasibility, independent of CP-SAT."""

from classync_contracts.scheduling import Diagnostic, GenerationInput


def contains(windows, day, start, end):
    return any(w.day == day and w.start <= start and end <= w.end for w in windows)


def intersects(windows, day, start, end):
    return any(w.day == day and start < w.end and w.start < end for w in windows)


def eligible_room(room, offering, program_id):
    if not room.schedulable or room.condition != "operational":
        return False
    if room.allowed_activity_types is not None:
        if not room.type_verified or offering.activity_type not in room.allowed_activity_types:
            return False
    if offering.required_room_type and (
        not room.type_verified or room.room_type != offering.required_room_type
    ):
        return False
    if offering.minimum_capacity is not None and (
        not room.capacity_verified
        or room.capacity is None
        or room.capacity < offering.minimum_capacity
    ):
        return False
    if offering.required_equipment and (
        not room.equipment_verified or not set(offering.required_equipment) <= set(room.equipment)
    ):
        return False
    if room.allowed_program_ids is not None and program_id not in room.allowed_program_ids:
        return False
    return offering.allowed_buildings is None or room.building in offering.allowed_buildings


def readiness(inputs: GenerationInput):
    errors = []

    def issue(code, message, offering_id=None):
        errors.append(Diagnostic(code=code, message=message, offering_id=offering_id))

    for field in ("operating_windows", "programs", "sections", "teachers", "rooms", "offerings"):
        if not getattr(inputs, field):
            issue("missing_inputs", f"Supply {field.replace('_', ' ')} before generation.")
    maps = {}
    for field in ("programs", "sections", "teachers", "rooms", "offerings"):
        items = getattr(inputs, field)
        maps[field] = {item.id: item for item in items}
        if len(maps[field]) != len(items):
            issue("duplicate_identity", f"{field} contain duplicate stable IDs.")
    for section in inputs.sections:
        program = maps["programs"].get(section.program_id)
        if program is None:
            issue("missing_reference", f"Section {section.id} references an unknown program.")
        elif program.section_policy == "degree" and (
            section.year_level is None or not section.section_letter
        ):
            issue(
                "section_naming", f"Section {section.id} needs structured year and letter fields."
            )
        elif program.section_policy == "custom" and not section.custom_label:
            issue("section_naming", f"Section {section.id} needs a program-specific custom label.")
        elif program.allowed_year_levels is not None and (
            section.year_level not in program.allowed_year_levels
        ):
            issue(
                "section_naming", f"Section {section.id} violates its configured year-level policy."
            )
        if any(day not in range(7) for day in section.preferred_days):
            issue("invalid_preference", f"Section {section.id} has an invalid preferred day.")
    for teacher in inputs.teachers:
        if teacher.synthetic and not inputs.synthetic:
            issue("synthetic_faculty", "Synthetic faculty cannot serve institutional scheduling.")
        if not teacher.availability:
            issue("teacher_availability_missing", f"Supply availability for {teacher.name}.")
        if any(day not in range(7) for day in teacher.preferred_days):
            issue("invalid_preference", f"Teacher {teacher.id} has an invalid preferred day.")
    for room in inputs.rooms:
        if room.allowed_program_ids is not None and any(
            pid not in maps["programs"] for pid in room.allowed_program_ids
        ):
            issue("missing_reference", f"Room {room.id} references an unknown program.")
    for offering in inputs.offerings:
        section = maps["sections"].get(offering.section_id)
        if section is None:
            issue("missing_reference", "Offering references an unknown section.", offering.id)
        for field, collection in (
            ("eligible_teacher_ids", "teachers"),
            ("eligible_room_ids", "rooms"),
        ):
            refs = getattr(offering, field)
            if (
                not refs
                or any(ref not in maps[collection] for ref in refs)
                or len(refs) != len(set(refs))
            ):
                issue(
                    "missing_reference",
                    f"Supply unique, valid {field} for this offering.",
                    offering.id,
                )
        if section and not any(
            eligible_room(maps["rooms"][rid], offering, section.program_id)
            and maps["rooms"][rid].availability
            for rid in offering.eligible_room_ids
            if rid in maps["rooms"]
        ):
            issue(
                "no_eligible_room",
                "No eligible operational classroom with the required verified "
                "type, equipment, capacity and program/building permissions. Unknown resources "
                "remain excluded until the necessary data is supplied.",
                offering.id,
            )
    seen_students = set()
    for enrollment in inputs.enrollments:
        if enrollment.student_id in seen_students:
            issue("duplicate_identity", "Combine each student's offering IDs into one enrollment.")
        seen_students.add(enrollment.student_id)
        if len(set(enrollment.offering_ids)) != len(enrollment.offering_ids) or any(
            oid not in maps["offerings"] for oid in enrollment.offering_ids
        ):
            issue(
                "missing_reference", "Student enrollment contains duplicate or unknown offerings."
            )
    for field in ("locked_assignments", "previous_assignments"):
        values = getattr(inputs, field)
        if len({a.id for a in values}) != len(values):
            issue("duplicate_identity", f"{field} contain duplicate assignment IDs.")
        for a in values:
            o = maps["offerings"].get(a.offering_id)
            if (
                o is None
                or a.room_id not in maps["rooms"]
                or a.teacher_id not in maps["teachers"]
                or a.section_id != o.section_id
                or a.subject_id != o.subject_id
            ):
                issue("missing_reference", f"{field}: assignment {a.id} has invalid references.")
    return errors


def placements(inputs, offering, duration):
    """Enumerate unary-legal discrete placements, never relax an unknown requirement."""
    sections = {s.id: s for s in inputs.sections}
    teachers = {t.id: t for t in inputs.teachers}
    eligible = [
        (i, room)
        for i, room in enumerate(inputs.rooms)
        if room.id in offering.eligible_room_ids
        and eligible_room(room, offering, sections[offering.section_id].program_id)
    ]
    teacher_indices = {t.id: i for i, t in enumerate(inputs.teachers)}
    found = set()
    for w in inputs.operating_windows:
        for start in range(w.start, w.end - duration + 1, 30):
            end = start + duration
            for tid in offering.eligible_teacher_ids:
                teacher = teachers[tid]
                if not contains(teacher.availability, w.day, start, end) or intersects(
                    teacher.unavailable, w.day, start, end
                ):
                    continue
                for ri, room in eligible:
                    if contains(room.availability, w.day, start, end) and not intersects(
                        room.blocked, w.day, start, end
                    ):
                        found.add((w.day * 1440 + start, ri, teacher_indices[tid]))
    return sorted(found)


def slot_runs(slots):
    """Contiguous (day, length) runs of a set of 30-minute (day, minute) slots."""
    runs = []
    for day, minute in sorted(slots):
        if runs and runs[-1][0] == day and runs[-1][2] == minute:
            runs[-1][1] += 30
            runs[-1][2] = minute + 30
        else:
            runs.append([day, 30, minute + 30])
    return [(day, length) for day, length, _ in runs]


def capacity_audit(inputs):
    """Necessary room, faculty and section time bounds with the setup screen that fixes each.

    Each session also reserves the transition buffer, rounded up to the 30-minute grid. A run of
    free time of length W fits sessions whose durations plus buffers total at most W + buffer.
    These are proven bounds only: passing them does not guarantee a timetable exists.
    """
    buffer = -(-inputs.transition_buffer_minutes // 30) * 30
    operating = {
        (w.day, minute) for w in inputs.operating_windows for minute in range(w.start, w.end, 30)
    }

    def free(windows, blocked=()):
        slots = {(w.day, m) for w in windows for m in range(w.start, w.end, 30)} & operating
        slots -= {(w.day, m) for w in blocked for m in range(w.start, w.end, 30)}
        return sum(length + buffer for _, length in slot_runs(slots))

    def demand(offering):
        return min(sum(d + buffer for d in p.durations) for p in offering.patterns)

    sections = {s.id: s for s in inputs.sections}
    rooms = {r.id: r for r in inputs.rooms}
    teachers = {t.id: t for t in inputs.teachers}
    room_supply = {r.id: free(r.availability, r.blocked) for r in inputs.rooms}
    teacher_supply = {t.id: free(t.availability, t.unavailable) for t in inputs.teachers}
    room_groups = {}
    for o in inputs.offerings:
        section = sections.get(o.section_id)
        room_groups[o.id] = frozenset(
            rid
            for rid in o.eligible_room_ids
            if rid in rooms and section and eligible_room(rooms[rid], o, section.program_id)
        )
    teacher_groups = {
        o.id: frozenset(t for t in o.eligible_teacher_ids if t in teachers)
        for o in inputs.offerings
    }
    messages = []

    def check(groups, supply, code, noun, action):
        for pool in sorted(set(groups.values()), key=sorted):
            if not pool:
                continue
            needed = sum(demand(o) for o in inputs.offerings if groups[o.id] <= pool)
            available = sum(supply[i] for i in pool)
            if needed > available:
                names = ", ".join(sorted(pool)[:4]) + (" and others" if len(pool) > 4 else "")
                messages.append(
                    Diagnostic(
                        code=code,
                        action_path=action,
                        message=(
                            f"Offerings limited to {noun} {names} need {needed} minutes a week "
                            f"including transition buffers; those {noun} have only {available}. "
                            f"Add eligible {noun} or widen their windows."
                        ),
                    )
                )

    check(room_groups, room_supply, "room_pool_capacity", "rooms", "/admin/academic/resources")
    check(teacher_groups, teacher_supply, "faculty_pool_capacity", "instructors", "/admin/teachers")
    for teacher in inputs.teachers:
        if teacher.max_weekly_minutes is None:
            continue
        needed = sum(
            min(sum(p.durations) for p in o.patterns)
            for o in inputs.offerings
            if teacher_groups[o.id] == {teacher.id}
        )
        if needed > teacher.max_weekly_minutes:
            messages.append(
                Diagnostic(
                    code="faculty_pool_capacity",
                    action_path="/admin/teachers",
                    message=(
                        f"{teacher.name} is the only eligible instructor for {needed} weekly "
                        f"minutes; the workload limit is {teacher.max_weekly_minutes}."
                    ),
                )
            )
    week = free(inputs.operating_windows)
    for section in inputs.sections:
        needed = sum(demand(o) for o in inputs.offerings if o.section_id == section.id)
        if needed > week:
            messages.append(
                Diagnostic(
                    code="section_time_capacity",
                    action_path="/admin/sections",
                    message=(
                        f"Section {section.id} needs {needed} minutes a week including "
                        f"transition buffers; the operating week allows {week}."
                    ),
                )
            )
    return messages


def infeasibility_diagnostics(inputs):
    """Proven necessary-bound failures, not a claim to a minimal unsat core."""
    slots = {
        (w.day, minute) for w in inputs.operating_windows for minute in range(w.start, w.end, 30)
    }
    total = len(slots) * 30
    days = {day for day, _ in slots}
    messages = []
    for section in inputs.sections:
        required = sum(
            o.required_weekly_minutes for o in inputs.offerings if o.section_id == section.id
        )
        if required > total:
            messages.append(
                Diagnostic(
                    code="insufficient_weekly_time",
                    message=(
                        f"Section {section.id} needs {required} minutes; the allowed week has "
                        f"only {total}. Expand operating times or correct the offerings."
                    ),
                )
            )
    for o in inputs.offerings:
        if all(p.distinct_days and len(p.durations) > len(days) for p in o.patterns):
            messages.append(
                Diagnostic(
                    code="insufficient_distinct_days",
                    offering_id=o.id,
                    message="Every permitted pattern requires more distinct days than are allowed.",
                )
            )
        elif not any(
            all(placements(inputs, o, duration) for duration in set(p.durations))
            for p in o.patterns
        ):
            messages.append(
                Diagnostic(
                    code="no_legal_placement",
                    offering_id=o.id,
                    message="No complete pattern fits teacher availability, room operating "
                    "restrictions and allowed weekly hours.",
                )
            )
    return messages + capacity_audit(inputs)
