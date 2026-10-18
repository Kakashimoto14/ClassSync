"""Pure occurrence expansion with half-open Manila intervals and explicit exceptions."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .draft_repository import DraftError

ZONE = ZoneInfo("Asia/Manila")


def occurrences(inputs, assignments, calendar, start, end):
    if start > end or (end - start).days > 62:
        raise DraftError(422, "calendar_range", "Choose a date range of at most 63 days.")
    subjects = {o.subject_id: (o.subject_id, o.subject_name) for o in inputs.offerings}
    sections = {s.id: s for s in inputs.sections}
    programs = {p.id: p for p in inputs.programs}
    teachers = {t.id: t for t in inputs.teachers}
    rooms = {r.id: r for r in inputs.rooms}
    ids = {a.id for a in assignments}
    if any(e.assignment_id and e.assignment_id not in ids for e in calendar.exceptions):
        raise DraftError(
            422, "exception_assignment", "An exception references an absent assignment."
        )
    by_id = {a.id: a for a in assignments}
    if any(
        e.assignment_id
        and (
            e.date.weekday() != by_id[e.assignment_id].day
            or e.date.weekday() not in calendar.instructional_days
        )
        for e in calendar.exceptions
    ):
        raise DraftError(
            422, "exception_date", "An exception must reference a scheduled class date."
        )
    result = []
    day = calendar.effective_start
    while day <= calendar.effective_end:
        for a in assignments:
            if day.weekday() != a.day or day.weekday() not in calendar.instructional_days:
                continue
            exceptions = [
                e
                for e in calendar.exceptions
                if e.date == day and (e.assignment_id is None or e.assignment_id == a.id)
            ]
            if any(e.cancelled for e in exceptions):
                continue
            change = next((e for e in exceptions if e.assignment_id == a.id), None)
            actual = change.moved_to if change and change.moved_to else day
            if any(
                e.date == actual and e.assignment_id is None and e.cancelled
                for e in calendar.exceptions
            ):
                continue
            if not start <= actual <= end:
                continue
            room_id = change.room_id if change and change.room_id else a.room_id
            if room_id not in rooms:
                raise DraftError(422, "exception_room", "An exception references an unknown room.")
            minute = change.start if change and change.start is not None else a.start
            begin = datetime.combine(actual, time(), ZONE) + timedelta(minutes=minute)
            finish = begin + timedelta(minutes=a.end - a.start)
            if minute + a.end - a.start > 1440:
                raise DraftError(
                    422, "exception_duration", "Moved classes must finish on the selected day."
                )
            section = sections[a.section_id]
            program = programs[section.program_id]
            room = rooms[room_id]
            result.append(
                {
                    "id": f"{a.id}:{day}",
                    "assignment_id": a.id,
                    "offering_id": a.offering_id,
                    "date": actual.isoformat(),
                    "starts_at": begin.isoformat(),
                    "ends_at": finish.isoformat(),
                    "subject": {
                        "id": a.subject_id,
                        "code": subjects[a.subject_id][0],
                        "name": subjects[a.subject_id][1],
                    },
                    "section": {
                        "id": section.id,
                        "name": section.custom_label
                        or f"{program.acronym} {section.year_level}{section.section_letter}",
                    },
                    "teacher": {"id": a.teacher_id, "name": teachers[a.teacher_id].name},
                    "room": {
                        "id": room.id,
                        "name": room.name,
                        "building": room.building,
                        "floor": room.floor,
                    },
                    "changed": bool(change),
                }
            )
        day += timedelta(days=1)
    return sorted(result, key=lambda o: (o["starts_at"], o["id"]))


def dated_occurrences(inputs, assignments, calendar, start, end):
    """Recheck dated moves against physical windows and attach internal validation metadata."""
    events = occurrences(inputs, assignments, calendar, start, end)
    teachers = {t.id: t for t in inputs.teachers}
    rooms = {r.id: r for r in inputs.rooms}
    offerings = {o.id: o for o in inputs.offerings}
    for event in events:
        begin = datetime.fromisoformat(event["starts_at"])
        finish = datetime.fromisoformat(event["ends_at"])
        day = begin.weekday()
        a = begin.hour * 60 + begin.minute
        b = a + int((finish - begin).total_seconds() / 60)
        teacher, room = teachers[event["teacher"]["id"]], rooms[event["room"]["id"]]

        def contains(windows, day=day, a=a, b=b):
            return any(w.day == day and w.start <= a and b <= w.end for w in windows)

        def blocked(windows, day=day, a=a, b=b):
            return any(w.day == day and w.start < b and a < w.end for w in windows)

        if (
            not contains(inputs.operating_windows)
            or not contains(teacher.availability)
            or blocked(teacher.unavailable)
            or (room.availability and not contains(room.availability))
            or blocked(room.blocked)
            or room.condition != "operational"
            or not room.schedulable
            or room.id not in offerings[event["offering_id"]].eligible_room_ids
        ):
            raise DraftError(
                422,
                "dated_constraints",
                "An occurrence violates current teaching or room constraints.",
            )
        event.update(
            {
                "buffer": inputs.transition_buffer_minutes,
                "students": [
                    e.student_id
                    for e in inputs.enrollments
                    if event["offering_id"] in e.offering_ids
                ],
                "max_daily": teacher.max_daily_minutes,
                "max_weekly": teacher.max_weekly_minutes,
            }
        )
    return events
