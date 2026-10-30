"""Reproducible synthetic Student sample; no database access or institutional claims."""

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from classync_contracts.calendar import AcademicCalendar, CalendarException
from classync_contracts.scheduling import Assignment, GenerationInput, scheduling_input_hash

from services.scheduling.app.catalog import synthetic_scenario
from services.scheduling.app.occurrences import dated_occurrences, occurrences
from services.scheduling.app.validation import validate_timetable


def fixture(*, room_change=False):
    raw = synthetic_scenario().model_dump()
    raw.update(period_id="classsync-presentation-v1", data_version="student-synthetic-v2")
    raw["scope_description"] = (
        "Synthetic BSIT 3A example; not official curriculum, people or facilities."
    )
    raw["programs"] = raw["programs"][:1]
    raw["sections"] = [raw["sections"][0]]
    raw["sections"][0].update(id="syn-bsit-3-A", year_level=3, section_letter="A")
    raw["teachers"] = [deepcopy(raw["teachers"][0]) for _ in range(3)]
    raw["rooms"] = [deepcopy(raw["rooms"][0]) for _ in range(3)]
    raw["enrollments"] = []
    offerings, assignments = [], []
    subjects = [
        (
            "ITADBMS",
            "Advanced Database Systems",
            "Maria Clara Santos",
            "LAB-201",
            [(0, 480, 570), (2, 480, 570), (4, 480, 570)],
        ),
        (
            "ITAPPSDEV",
            "Application Development",
            "Carlo Mendoza",
            "LAB-202",
            [(1, 600, 720), (3, 600, 720), (4, 570, 690)],
        ),
        (
            "ITIASE1",
            "Information Assurance 1",
            "Nina Villanueva",
            "AVR-101",
            [(0, 780, 840), (2, 780, 840), (4, 780, 840)],
        ),
    ]
    for i, (code, name, teacher, room, sessions) in enumerate(subjects):
        tid, rid, oid = (
            f"teacher-syn-bsit-3-first-{i + 1}",
            f"synthetic-student-room-{i + 1}",
            f"student-offering-{i + 1}",
        )
        raw["teachers"][i].update(
            id=tid, name=teacher, unavailable=[], max_daily_minutes=None, max_weekly_minutes=None
        )
        raw["rooms"][i].update(id=rid, name=room, building="Example IT Complex", floor=None)
        offering = deepcopy(raw["offerings"][0])
        durations = [end - start for _, start, end in sessions]
        offering.update(
            id=oid,
            subject_id=code,
            subject_name=name,
            section_id="syn-bsit-3-A",
            eligible_teacher_ids=[tid],
            eligible_room_ids=[rid],
            required_weekly_minutes=sum(durations),
            patterns=[{"id": "weekly", "durations": durations, "distinct_days": True}],
        )
        offerings.append(offering)
        for j, (day, start, end) in enumerate(sessions):
            assignments.append(
                Assignment(
                    id=f"student-{i}-{j}",
                    offering_id=oid,
                    subject_id=code,
                    section_id="syn-bsit-3-A",
                    teacher_id=tid,
                    room_id=rid,
                    day=day,
                    start=start,
                    end=end,
                )
            )
    raw["offerings"] = offerings
    if room_change:
        # A separate synthetic revision scenario, never part of the default bundle.
        raw["offerings"][0]["eligible_room_ids"].append(raw["rooms"][1]["id"])
    inputs = GenerationInput.model_validate(raw)
    report = validate_timetable(inputs, assignments)
    assert report.valid, report.model_dump()
    calendar = AcademicCalendar(
        academic_year="2026-2027",
        semester="first",
        effective_start=date(2026, 10, 1),
        effective_end=date(2026, 12, 31),
    )
    if room_change:
        calendar.exceptions = [
            CalendarException(
                date=date(2026, 10, 30),
                moved_to=date(2026, 10, 30),
                reason="Synthetic room-change scenario",
                assignment_id="student-0-2",
                cancelled=False,
                room_id=raw["rooms"][1]["id"],
            )
        ]
    events = []
    for start, end in [
        (date(2026, 10, 1), date(2026, 11, 30)),
        (date(2026, 12, 1), date(2026, 12, 31)),
    ]:
        dated_occurrences(inputs, assignments, calendar, start, end)
        events.extend(occurrences(inputs, assignments, calendar, start, end))
    return {
        "metadata": {
            "version": "classsync-presentation-v1",
            "source": (
                "Explicit synthetic example inspired by owner mockups; "
                "domain-validated fixed assignments"
            ),
            "input_hash": scheduling_input_hash(inputs),
            "validated_at_export": True,
            "hard_conflicts_at_export": 0,
            "live": False,
            "candidate_rooms": 3,
            "offerings": 3,
            "sessions_per_week": 9,
        },
        "calendar": {
            "version": "classsync-presentation-v1",
            "status": "presentation-sample",
            "calendar": calendar.model_dump(mode="json"),
            "sections": [inputs.sections[0].model_dump(mode="json")],
            "teachers": [{"id": t.id, "name": t.name} for t in inputs.teachers],
            "occurrences": events,
        },
    }


if __name__ == "__main__":
    target = (
        Path(__file__).resolve().parents[1] / "apps/web/src/data/presentation-timetable.v1.json"
    )
    target.write_text(json.dumps(fixture(), indent=2) + "\n", encoding="utf-8")
    print("Exported validated synthetic sample: 3 subjects, 9 weekly sessions; no database opened.")
