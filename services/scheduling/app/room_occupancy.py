"""Expand room-only publication projections into occupied rooms for one time slot.

Rows come from `classsync_scheduling.room_occupancy_versions` (migration 0028) and carry no
subject, section, teacher or student data. The rules mirror `publication_rules.expanded` and
`occurrences.occurrences`: the latest version (by sequence) covering a date wins for its period,
cancellations remove an occurrence, and a move changes its date, room and start.
"""

from datetime import date, datetime, time, timedelta

from .occurrences import ZONE


def _date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def occupied_rooms(rows, begin, finish):
    """Rooms whose published session, padded by its transition buffer, meets [begin, finish)."""
    target = begin.astimezone(ZONE).date()
    latest = {}
    versions = []
    for row in sorted(rows, key=lambda r: r["version_rank"]):
        projection = row["projection"]
        calendar = projection["calendar"]
        first, last = _date(calendar["effective_start"]), _date(calendar["effective_end"])
        versions.append((row, projection, first, last))
        if first <= target <= last:
            latest[row["period_id"]] = row["version_id"]
    rooms = set()
    for row, projection, first, last in versions:
        if latest.get(row["period_id"]) != row["version_id"]:
            continue
        calendar = projection["calendar"]
        days = set(calendar["instructional_days"] or [])
        exceptions = [
            {**e, "date": _date(e["date"]), "moved_to": _date(e.get("moved_to"))}
            for e in calendar["exceptions"]
        ]
        if any(e["assignment_id"] is None and e["cancelled"] and e["date"] == target
               for e in exceptions):
            continue  # campus-wide cancellation of the target date
        buffer = timedelta(minutes=projection.get("buffer") or 0)
        for a in projection["assignments"]:
            # Original class dates that can land on the target: itself, or a move onto it.
            originals = {target} | {
                e["date"] for e in exceptions
                if e["assignment_id"] == a["id"] and e["moved_to"] == target
            }
            for original in originals:
                if (
                    not first <= original <= last
                    or original.weekday() != a["day"]
                    or original.weekday() not in days
                ):
                    continue
                on_date = [
                    e for e in exceptions
                    if e["date"] == original and e["assignment_id"] in (None, a["id"])
                ]
                if any(e["cancelled"] for e in on_date):
                    continue
                change = next((e for e in on_date if e["assignment_id"] == a["id"]), None)
                actual = change["moved_to"] if change and change["moved_to"] else original
                if actual != target:
                    continue
                minute = (
                    change["start"] if change and change.get("start") is not None else a["start"]
                )
                starts = datetime.combine(actual, time(), ZONE) + timedelta(minutes=minute)
                ends = starts + timedelta(minutes=a["end"] - a["start"])
                if starts - buffer < finish and begin < ends + buffer:
                    rooms.add(change["room_id"] if change and change["room_id"] else a["room_id"])
    return rooms
