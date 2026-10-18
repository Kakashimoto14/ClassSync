"""Input/reference normalization and unary feasibility, independent of CP-SAT."""

from classync_contracts.scheduling import Diagnostic, GenerationInput


def contains(windows, day, start, end):
    return any(w.day == day and w.start <= start and end <= w.end for w in windows)


def intersects(windows, day, start, end):
    return any(w.day == day and start < w.end and w.start < end for w in windows)


def eligible_room(room, offering, program_id):
    if not room.schedulable or room.condition != "operational":
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
    return messages
