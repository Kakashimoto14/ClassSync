"""Read-only utilization and workload figures from authoritative records and publications.

Pure functions. Room utilization is dated: for every instructional date of the period, booked
published minutes inside operating hours, divided by operating minutes less active room
restrictions. Rooms are shared, so bookings include every publication dated inside the period.
Faculty, program and section figures describe this period's published week only; without a
publication they are empty. Nothing is estimated or sampled.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from .catalog import schedulable_spaces
from .occurrences import ZONE


def merged(intervals):
    result = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return [tuple(item) for item in result]


def intersect(first, second):
    """Intersection of two merged interval lists."""
    result = []
    for a, b in first:
        for c, d in second:
            low, high = max(a, c), min(b, d)
            if low < high:
                result.append((low, high))
    return result


def minutes(intervals):
    return sum(end - start for start, end in intervals)


def percent(part, whole):
    return round(part * 100 / whole, 1) if whole else None


def instructional_dates(calendar):
    cancelled = {e.date for e in calendar.exceptions if e.assignment_id is None and e.cancelled}
    day, result = calendar.effective_start, []
    while day <= calendar.effective_end:
        if day.weekday() in calendar.instructional_days and day not in cancelled:
            result.append(day)
        day += timedelta(days=1)
    return result


def booked_sessions(versions, first, last):
    """Dated {room, starts_at, ends_at} of the winning versions inside [first, last].

    `versions` are (period id, calendar, assignments) in publication order. Same rules as
    `publication_rules.expanded`, in one pass and without re-checking constraints that were
    validated at publication: the latest version covering a date wins for its period.
    """
    latest = {}
    for index, (period, calendar, _) in enumerate(versions):
        day = max(first, calendar.effective_start)
        while day <= min(last, calendar.effective_end):
            latest[period, day] = index
            day += timedelta(days=1)
    result = []
    for index, (period, calendar, assignments) in enumerate(versions):
        weekdays = defaultdict(list)
        for assignment in assignments:
            weekdays[assignment.day].append(assignment)
        exceptions = defaultdict(list)
        for item in calendar.exceptions:
            exceptions[item.date].append(item)
        day = calendar.effective_start
        while day <= calendar.effective_end:
            todays = weekdays[day.weekday()] if day.weekday() in calendar.instructional_days else []
            for a in todays:
                own = [e for e in exceptions.get(day, ()) if e.assignment_id in (None, a.id)]
                if any(e.cancelled for e in own):
                    continue
                change = next((e for e in own if e.assignment_id == a.id), None)
                actual = change.moved_to if change and change.moved_to else day
                if any(
                    e.assignment_id is None and e.cancelled for e in exceptions.get(actual, ())
                ) or latest.get((period, actual)) != index:
                    continue
                minute = change.start if change and change.start is not None else a.start
                starts = datetime.combine(actual, time(), ZONE) + timedelta(minutes=minute)
                result.append(
                    {
                        "room_id": change.room_id if change and change.room_id else a.room_id,
                        "starts_at": starts,
                        "ends_at": starts + timedelta(minutes=a.end - a.start),
                    }
                )
            day += timedelta(days=1)
    return result


def _by_room_date(items):
    """{(room, date): [(start minute, end minute)]} for (room, aware start, aware end)."""
    result = defaultdict(list)
    for room, start, end in items:
        start, end = start.astimezone(ZONE), end.astimezone(ZONE)
        day = start.date()
        while day <= end.date():
            midnight = datetime.combine(day, time(), ZONE)
            low = max(0, int((start - midnight).total_seconds() // 60))
            high = min(1440, int((end - midnight).total_seconds() // 60))
            if low < high:
                result[room, day].append((low, high))
            day += timedelta(days=1)
    return result


def _group(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    result = []
    for name, members in sorted(groups.items()):
        available = sum(r["available_minutes"] for r in members)
        booked = sum(r["booked_minutes"] for r in members)
        result.append(
            {
                "name": name,
                "rooms": len(members),
                "available_minutes": available,
                "restricted_minutes": sum(r["restricted_minutes"] for r in members),
                "booked_minutes": booked,
                "utilization": percent(booked, available),
            }
        )
    return result


def room_utilization(calendar, windows, events, restrictions, room_types):
    dates: list[date] = instructional_dates(calendar) if calendar else []
    hours = defaultdict(list)
    for window in windows:
        hours[window.day].append((window.start, window.end))
    hours = {day: merged(values) for day, values in hours.items()}
    booked = _by_room_date((e["room_id"], e["starts_at"], e["ends_at"]) for e in events)
    restricted = _by_room_date(
        (r["room_id"], datetime.fromisoformat(r["starts_at"]),
         datetime.fromisoformat(r["ends_at"]))
        for r in restrictions
        if r.get("status", "active") == "active"
    )
    rows = []
    for room in schedulable_spaces():
        operating = blocked = used = 0
        for day in dates:
            open_hours = hours.get(day.weekday(), [])
            operating += minutes(open_hours)
            closed = intersect(open_hours, merged(restricted.get((room.id, day), [])))
            blocked += minutes(closed)
            taken = intersect(open_hours, merged(booked.get((room.id, day), [])))
            used += minutes(taken) - minutes(intersect(merged(taken), merged(closed)))
        available = operating - blocked
        rows.append(
            {
                "id": room.id,
                "name": room.name,
                "building": room.building,
                "floor": room.floor,
                "room_type": room_types.get(room.id) or room.room_type or "unknown",
                "operating_minutes": operating,
                "restricted_minutes": blocked,
                "available_minutes": available,
                "booked_minutes": used,
                "utilization": percent(used, available),
            }
        )
    return rows, len(dates)


def _section_label(section, programs):
    program = programs.get(section.program_id)
    return section.custom_label or (
        f"{program.acronym if program else ''} {section.year_level}{section.section_letter}"
    )


def build_report(records, calendar, published, events, restrictions):
    """`published` is a decoded publication payload or None; `records` are academic records."""
    kinds = defaultdict(list)
    for record in records:
        kinds[record.kind].append(record)
    constraints = kinds["constraints"][0] if kinds["constraints"] else None
    inputs = published["draft"].input_snapshot if published else None
    assignments = published["draft"].generation_result.assignments if published else []
    calendar = published["calendar"] if published else calendar
    windows = (
        inputs.operating_windows
        if inputs
        else constraints.operating_windows
        if constraints
        else []
    )
    rooms, date_count = room_utilization(
        calendar,
        windows,
        events,
        restrictions,
        {r.id: r.room_type for r in kinds["resources"]},
    )

    loads = defaultdict(lambda: [0, 0])
    for a in assignments:
        loads[a.teacher_id][0] += a.end - a.start
        loads[a.teacher_id][1] += 1
    faculty = [
        {
            "id": member.id,
            "name": member.name,
            "active": member.active,
            "weekly_minutes": loads[member.id][0],
            "sessions": loads[member.id][1],
            "max_weekly_minutes": member.max_weekly_minutes,
            "load": percent(loads[member.id][0], member.max_weekly_minutes),
        }
        for member in sorted(kinds["faculty"], key=lambda f: (f.name.casefold(), f.id))
    ]

    programs = {p.id: p for p in kinds["programs"]}
    sections = {s.id: s for s in kinds["sections"]}
    offering_program = {
        o.id: sections[o.section_id].program_id
        for o in kinds["offerings"]
        if o.section_id in sections
    }
    students = defaultdict(set)
    for enrollment in constraints.enrollments if constraints else []:
        for offering in enrollment.offering_ids:
            if offering in offering_program:
                students[offering_program[offering]].add(enrollment.student_id)
    distribution = []
    for program in sorted(programs.values(), key=lambda p: (p.institute, p.acronym)):
        own = [a for a in assignments if sections.get(a.section_id) is not None
               and sections[a.section_id].program_id == program.id]
        row = {
            "id": program.id,
            "program": program.acronym,
            "institute": program.institute,
            "sections": sum(s.program_id == program.id for s in sections.values()),
            "offerings": sum(value == program.id for value in offering_program.values()),
            "students": len(students[program.id]),
            "sessions": len(own),
            "weekly_minutes": sum(a.end - a.start for a in own),
        }
        if row["sections"] or row["offerings"]:
            distribution.append(row)
    institutes = []
    for name in sorted({row["institute"] for row in distribution}):
        members = [row for row in distribution if row["institute"] == name]
        institutes.append(
            {"institute": name, "programs": len(members)}
            | {
                key: sum(row[key] for row in members)
                for key in ("sections", "offerings", "students", "sessions", "weekly_minutes")
            }
        )

    days = defaultdict(list)
    for a in assignments:
        days[a.section_id, a.day].append((a.start, a.end))
    shape = []
    for section in sections.values():
        week = [values for (identity, _), values in days.items() if identity == section.id]
        if not week:
            continue
        spans = [max(e for _, e in v) - min(s for s, _ in v) for v in week]
        shape.append(
            {
                "id": section.id,
                "label": _section_label(section, programs),
                "program": programs[section.program_id].acronym
                if section.program_id in programs
                else "",
                "active_days": len(week),
                "sessions": sum(len(v) for v in week),
                "one_class_days": sum(len(v) == 1 for v in week),
                "max_sessions_per_day": max(len(v) for v in week),
                "longest_span_minutes": max(spans),
                "idle_minutes": sum(
                    span - minutes(merged(v)) for span, v in zip(spans, week, strict=True)
                ),
            }
        )
    rules = constraints.daily_shape if constraints else None
    return {
        "timezone": "Asia/Manila",
        "basis": {
            "effective_start": calendar.effective_start.isoformat(),
            "effective_end": calendar.effective_end.isoformat(),
            "instructional_dates": date_count,
        }
        if calendar
        else None,
        "rooms": rooms,
        "buildings": _group(rooms, "building"),
        "room_types": _group(rooms, "room_type"),
        "faculty": faculty,
        "programs": distribution,
        "institutes": institutes,
        "sections": sorted(shape, key=lambda row: row["label"]),
        "daily_shape": rules.model_dump(mode="json") if rules else None,
    }
