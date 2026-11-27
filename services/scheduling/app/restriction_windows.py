"""Project dated room restrictions onto the weekly grid the solver uses.

Publication rejects any dated occurrence that overlaps a room restriction or reservation
(`publish_in` -> `restrictions`). A weekly placement repeats on every instructional date of the
term, so one overlapping date is enough to make the whole placement unpublishable. Each
restriction therefore blocks its room at that weekday and time for the full week pattern.
"""

from collections.abc import Sequence
from datetime import datetime, time, timedelta

from classync_contracts.calendar import AcademicCalendar
from classync_contracts.scheduling import GenerationInput, Window

from .occurrences import ZONE


def weekly_blocks(
    restrictions: Sequence[dict], calendar: AcademicCalendar
) -> dict[str, list[Window]]:
    """Return {room_id: [Window]} for restrictions touching the calendar's instructional dates."""
    _require_types(restrictions, calendar)
    blocks = {}
    first, last = calendar.effective_start, calendar.effective_end
    for restriction in restrictions:
        start = datetime.fromisoformat(restriction["starts_at"]).astimezone(ZONE)
        end = datetime.fromisoformat(restriction["ends_at"]).astimezone(ZONE)
        day = max(start.date(), first)
        while day <= min(end.date(), last):
            if day.weekday() in calendar.instructional_days:
                midnight = datetime.combine(day, time(), ZONE)
                begin = max(start, midnight)
                finish = min(end, midnight + timedelta(days=1))
                lower = int((begin - midnight).total_seconds() // 60) // 30 * 30
                upper = -(-int((finish - midnight).total_seconds() // 60) // 30) * 30
                if lower < upper:
                    blocks.setdefault(restriction["room_id"], set()).add(
                        (day.weekday(), lower, min(upper, 1440))
                    )
            day += timedelta(days=1)
    return {
        room: [Window(day=d, start=a, end=b) for d, a, b in sorted(merge(values))]
        for room, values in blocks.items()
    }


def merge(intervals):
    merged = []
    for day, start, end in sorted(intervals):
        if merged and merged[-1][0] == day and start <= merged[-1][2]:
            merged[-1][2] = max(merged[-1][2], end)
        else:
            merged.append([day, start, end])
    return [tuple(item) for item in merged]


def _require_types(restrictions, calendar):
    # Both arguments are keyword-only in `with_room_restrictions`; this also fails loudly if a
    # caller passes them swapped (the calendar as the restriction list, or a list as calendar).
    if not isinstance(calendar, AcademicCalendar):
        raise TypeError(f"calendar must be an AcademicCalendar, not {type(calendar).__name__}")
    if isinstance(restrictions, (str, bytes, dict)) or not isinstance(restrictions, Sequence):
        raise TypeError(f"restrictions must be a list, not {type(restrictions).__name__}")


def with_room_restrictions(
    inputs: GenerationInput,
    *,
    restrictions: Sequence[dict],
    calendar: AcademicCalendar | None,
) -> GenerationInput:
    """Copy generation input with restricted weekly room times added to `blocked`.

    A period without a calendar cannot have dated occurrences, so it is returned unchanged.
    """
    if calendar is None:
        return inputs
    _require_types(restrictions, calendar)
    if not restrictions:
        return inputs
    blocks = weekly_blocks(restrictions, calendar)
    if not blocks:
        return inputs
    rooms = [
        room.model_copy(
            update={
                "blocked": [
                    Window(day=d, start=a, end=b)
                    for d, a, b in merge(
                        [(w.day, w.start, w.end) for w in room.blocked]
                        + [(w.day, w.start, w.end) for w in blocks.get(room.id, [])]
                    )
                ]
            }
        )
        if room.id in blocks
        else room
        for room in inputs.rooms
    ]
    return inputs.model_copy(update={"rooms": rooms})
