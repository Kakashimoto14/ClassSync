"""Dated booking expansion for reports: moves, cancellations and version supersession."""

from datetime import date
from types import SimpleNamespace

from classync_contracts.calendar import AcademicCalendar, CalendarException

from services.scheduling.app.reports import booked_sessions

MONDAY, NEXT_MONDAY = date(2026, 9, 7), date(2026, 9, 14)


def _calendar(*exceptions, start=MONDAY, end=NEXT_MONDAY):
    return AcademicCalendar(
        academic_year="2026-2027", semester="first", effective_start=start, effective_end=end,
        exceptions=list(exceptions),
    )


def _class(room="a", identity="s1"):
    return SimpleNamespace(id=identity, day=0, start=480, end=570, room_id=room)


def _booked(versions):
    return [
        (b["room_id"], b["starts_at"].date().isoformat(), b["starts_at"].hour)
        for b in booked_sessions(versions, MONDAY, NEXT_MONDAY)
    ]


def test_cancellation_and_room_move_apply_to_their_date_only():
    cancelled = _calendar(CalendarException(date=MONDAY, reason="Holiday"))
    assert _booked([("p", cancelled, [_class()])]) == [("a", "2026-09-14", 8)]
    moved = _calendar(CalendarException(
        date=MONDAY, reason="Swap", assignment_id="s1", cancelled=False,
        moved_to=date(2026, 9, 8), room_id="b", start=600,
    ))
    assert _booked([("p", moved, [_class()])]) == [
        ("b", "2026-09-08", 10), ("a", "2026-09-14", 8),
    ]


def test_a_later_version_wins_the_dates_it_covers_and_periods_stay_independent():
    old, new = _calendar(), _calendar(start=NEXT_MONDAY)
    assert _booked([("p", old, [_class("a")]), ("p", new, [_class("b")])]) == [
        ("a", "2026-09-07", 8), ("b", "2026-09-14", 8),
    ]
    assert len(_booked([("p", old, [_class("a")]), ("q", old, [_class("b")])])) == 4
