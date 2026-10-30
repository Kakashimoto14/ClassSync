"""Revision boundaries must include retained contact minutes in the same ISO week.

These manually placed, independently validated fixtures start no solver or database.
"""

from datetime import date

import pytest
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.publication import PublicationCommand
from classync_contracts.scheduling import (
    Assignment,
    DraftDetail,
    GenerationResult,
    RunMetadata,
    Window,
    scheduling_input_hash,
)

from services.scheduling.app.draft_rules import DraftError, DraftSnapshot, digest, encode
from services.scheduling.app.publication_rules import PublicationRules
from services.scheduling.app.validation import validate_timetable
from services.scheduling.tests.test_engine import tiny


class EmptyRestrictions(PublicationRules):
    def restrictions(self, _db, _tenant, _dataset, _events):
        """The fixture contains no restrictions; domain validation remains real."""


def fixture(*, version, period, days, start, end, limit, windows=None, buffer=0):
    inputs = tiny([{"id": "two-ninety", "durations": [90, 90], "distinct_days": True}])
    inputs.period_id = period
    inputs.teachers[0].max_weekly_minutes = limit
    inputs.transition_buffer_minutes = buffer
    if windows is not None:
        inputs.operating_windows = [Window.model_validate(window) for window in windows]
        inputs.teachers[0].availability = inputs.operating_windows[:]
        inputs.rooms[0].availability = inputs.operating_windows[:]
    offering = inputs.offerings[0]
    assignments = []
    for index, day in enumerate(days):
        window = next(window for window in inputs.operating_windows if window.day == day)
        assignments.append(Assignment(
            id=f"session-{index}", offering_id=offering.id, subject_id=offering.subject_id,
            section_id=offering.section_id, teacher_id=offering.eligible_teacher_ids[0],
            room_id=offering.eligible_room_ids[0], day=day,
            start=window.start, end=window.start + 90,
        ))
    validation = validate_timetable(inputs, assignments)
    assert validation.valid and validation.hard_conflict_count == 0, validation.model_dump()
    result = GenerationResult(
        run_id=f"manual-run-{version}", period_id=period, input_hash=scheduling_input_hash(inputs),
        data_version=inputs.data_version, solver_status="feasible", assignments=assignments,
        total_offerings_requested=1, total_offerings_scheduled=1, coverage=validation.coverage,
        hard_conflict_count=0, diagnostics=[], validation=validation,
        metadata=RunMetadata(solver="manual fixture; no solver executed", solver_version="not-run",
                             seed=inputs.options.seed, wall_time_seconds=0,
                             time_limit_seconds=inputs.options.time_limit_seconds),
    )
    metadata = {"id": f"draft-{version}", "title": "Generated weekly boundary fixture",
                "created_at": "2026-10-28T00:00:00+00:00", "owner": "synthetic-admin",
                "scope": "administrator"}
    draft = DraftDetail(**DraftSnapshot().make_summary(inputs, result, metadata).model_dump(),
                        input_snapshot=inputs, generation_result=result, validation=validation)
    calendar = AcademicCalendar(academic_year="2026-2027", semester="first",
                                effective_start=date.fromisoformat(start),
                                effective_end=date.fromisoformat(end),
                                instructional_days=list(range(7)) if windows else list(range(5)))
    payload = encode({"draft": draft.model_dump(mode="json"),
                      "calendar": calendar.model_dump(mode="json"), "review": {}})
    row = {"id": f"version-{version}", "sequence": version, "revision": version,
           "period_id": period, "draft_id": draft.id, "dataset": "synthetic",
           "tenant": "generated-tenant", "actor": "synthetic-admin",
           "created_at": metadata["created_at"], "payload": payload, "checksum": digest(payload)}
    command = PublicationCommand(draft_id=draft.id, dataset="synthetic", source="administrator",
                                  expected_version=version - 1, expected_academic_revision=1,
                                  idempotency_key=f"generated-week-boundary-{version}",
                                  calendar=calendar)
    return row, draft, command


@pytest.fixture(autouse=True)
def prohibit_solver_and_database(monkeypatch):
    import sqlite3

    from ortools.sat.python import cp_model

    monkeypatch.setattr(sqlite3, "connect", lambda *_a, **_k: pytest.fail("Database opened"))
    monkeypatch.setattr(cp_model.CpSolver, "solve",
                        lambda *_a, **_k: pytest.fail("Solver executed"))


@pytest.mark.parametrize("case", ["same-period-earlier", "different-period-earlier",
                                  "different-period-later", "same-period-later", "week-year"])
@pytest.mark.parametrize("limit", [180, 270])
def test_publication_checks_retained_minutes_outside_effective_dates_in_same_week(case, limit):
    old_period = "period-a"
    new_period = "period-a" if case.startswith("same") or case == "week-year" else "period-b"
    old_days, old_start, old_end = (0, 2), "2026-10-05", "2026-10-11"
    new_days, new_start, new_end = (2, 4), "2026-10-07", "2026-10-11"
    if case == "different-period-earlier":
        old_end = old_start  # Retain Monday only, entirely before the new effective interval.
    elif case in {"different-period-later", "same-period-later"}:
        old_days, old_start = (0, 4), "2026-10-09"
        if case == "same-period-later":
            old_start = "2026-10-05"
        new_days, new_start, new_end = (0, 2), "2026-10-05", "2026-10-07"
    elif case == "week-year":
        old_start, old_end = "2026-12-28", "2027-01-03"
        new_start, new_end = "2026-12-30", "2027-01-03"
    old, _, _ = fixture(version=1, period=old_period, days=old_days, start=old_start,
                        end=old_end, limit=limit)
    new, draft, command = fixture(version=2, period=new_period, days=new_days,
                                  start=new_start, end=new_end, limit=limit)
    rules = EmptyRestrictions()
    week_start = date(2026, 12, 28) if case == "week-year" else date(2026, 10, 5)
    week_end = date(2027, 1, 3) if case == "week-year" else date(2026, 10, 11)
    full_week = rules.expanded([old, new], week_start, week_end)
    assert sum(90 for _ in full_week) == 270
    if limit == 180:
        with pytest.raises(DraftError) as independently_denied:
            rules.conflicts(full_week)
        assert independently_denied.value.code == "publication_workload"
        with pytest.raises(DraftError) as denied:
            rules.review_scope(object(), "generated-tenant", command, draft, [old], 1)
        assert (denied.value.status, denied.value.code) == (422, "publication_workload")
    else:
        rules.conflicts(full_week)
        report = rules.review_scope(object(), "generated-tenant", command, draft, [old], 1)
        assert report["status"] == "ready-for-review" and report["occurrences"] == 2


@pytest.mark.parametrize("neighbor", ["before", "after"])
@pytest.mark.parametrize("buffer", [0, 30])
def test_transition_buffer_includes_neighboring_iso_week_at_midnight(neighbor, buffer):
    windows = [{"day": 0, "start": 0, "end": 90},
               {"day": 2, "start": 480, "end": 570},
               {"day": 4, "start": 480, "end": 570},
               {"day": 6, "start": 1350, "end": 1440}]
    sunday = {"days": (4, 6), "start": "2026-10-11", "end": "2026-10-11"}
    monday = {"days": (0, 2), "start": "2026-10-12", "end": "2026-10-12"}
    old_placement, new_placement = (sunday, monday) if neighbor == "before" else (monday, sunday)
    old, _, _ = fixture(version=1, period="period-a", limit=180,
                        windows=windows, buffer=buffer, **old_placement)
    new, draft, command = fixture(version=2, period="period-a", limit=180,
                                  windows=windows, buffer=buffer, **new_placement)
    rules = EmptyRestrictions()
    expanded = rules.expanded([old, new], date(2026, 10, 11), date(2026, 10, 12))
    assert len(expanded) == 2
    assert expanded[0]["ends_at"] == expanded[1]["starts_at"]
    if buffer:
        with pytest.raises(DraftError) as independent:
            rules.conflicts(expanded)
        assert independent.value.code == "publication_conflict"
        with pytest.raises(DraftError) as denied:
            rules.review_scope(object(), "generated-tenant", command, draft, [old], 1)
        assert (denied.value.status, denied.value.code) == (422, "publication_conflict")
    else:
        rules.conflicts(expanded)
        report = rules.review_scope(object(), "generated-tenant", command, draft, [old], 1)
        assert report["status"] == "ready-for-review" and report["occurrences"] == 1
