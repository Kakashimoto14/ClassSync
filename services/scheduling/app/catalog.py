"""Owner-supplied catalogs and explicitly fictional INPUTS, never solver outputs."""

import json
from pathlib import Path

from classync_contracts import scheduling


def catalogs():
    root = Path(scheduling.__file__).parent / "catalogs"
    programs = [
        scheduling.Program.model_validate(p)
        for p in json.loads((root / "programs.json").read_text())
    ]
    rooms = [
        scheduling.Room(
            **{k: v for k, v in r.items() if k != "aliasUnconfirmed" and k != "alias"},
            source="cdm-provisional",
        )
        for r in json.loads((root / "cdm-spaces.json").read_text())
    ]
    return {"programs": programs, "cdm_spaces": rooms}


def synthetic_scenario(infeasible=False):
    programs = catalogs()["programs"]
    selected = [p for p in programs if p.id in {"bsit", "bscpe", "bsba-hrm"}]
    windows = [
        scheduling.Window(day=d, start=a, end=b)
        for d in range(5)
        for a, b in [(480, 720), (780, 1020)]
    ]
    teachers = [
        scheduling.Teacher(
            id=f"synthetic-teacher-{i}",
            name=f"Example Instructor {chr(65 + i)} (synthetic)",
            availability=windows,
            preferred_days=[0, 2, 4] if i % 2 == 0 else [1, 3],
        )
        for i in range(4)
    ]
    teachers[0].unavailable = [scheduling.Window(day=1, start=780, end=1020)]
    sections = [
        scheduling.Section(
            id=f"synthetic-section-{i}", program_id=pid, year_level=year, section_letter=letter
        )
        for i, (pid, year, letter) in enumerate(
            [("bsit", 3, "A"), ("bsit", 3, "B"), ("bscpe", 2, "A"), ("bsba-hrm", 1, "A")]
        )
    ]
    rooms = [
        scheduling.Room(
            id=f"synthetic-room-{i}",
            name=f"Example {'Lab' if i > 1 else 'Room'} {i + 1}",
            building="Synthetic East" if i % 2 == 0 else "Synthetic West",
            floor="Example Floor 1",
            source="synthetic",
            schedulable=True,
            condition="operational",
            room_type="lab" if i > 1 else "lecture",
            type_verified=True,
            capacity=30 if i > 1 else 50,
            capacity_verified=True,
            equipment=["projector", "computers"] if i > 1 else ["projector"],
            equipment_verified=True,
            availability=windows,
        )
        for i in range(4)
    ]
    offerings = []
    for si, section in enumerate(sections):
        for subject in range(3):
            patterns = (
                [scheduling.SessionPattern(id="one-180", durations=[180])]
                if subject == 0
                else [scheduling.SessionPattern(id="two-90", durations=[90, 90])]
                if subject == 1
                else [
                    scheduling.SessionPattern(id="one-180", durations=[180]),
                    scheduling.SessionPattern(id="two-90", durations=[90, 90]),
                ]
            )
            offerings.append(
                scheduling.Offering(
                    id=f"synthetic-offering-{si}-{subject}",
                    subject_id=f"synthetic-subject-{subject}",
                    subject_name=["Example Seminar", "Example Applied Lab", "Example Workshop"][
                        subject
                    ],
                    section_id=section.id,
                    eligible_teacher_ids=[teachers[si % 4].id, teachers[(si + 1) % 4].id],
                    eligible_room_ids=[
                        r.id for r in rooms if (r.room_type == "lab") == (subject == 1)
                    ],
                    patterns=patterns,
                    minimum_capacity=25,
                    required_room_type="lab" if subject == 1 else "lecture",
                    required_equipment=["computers"] if subject == 1 else ["projector"],
                )
            )
    return scheduling.GenerationInput(
        options=scheduling.SolverOptions(time_limit_seconds=15.0),
        period_id="synthetic-week-infeasible" if infeasible else "synthetic-week",
        data_version="synthetic-v1",
        synthetic=True,
        all_intended_offerings_supplied=True,
        scope_description="Synthetic presentation batch: 3 programs, 4 sections, 12 offerings. "
        "Not CdM curriculum, faculty, enrollment or resource metadata.",
        programs=selected,
        sections=sections,
        teachers=teachers,
        rooms=rooms,
        offerings=offerings,
        operating_windows=[scheduling.Window(day=0, start=480, end=660)] if infeasible else windows,
        enrollments=[
            scheduling.Enrollment(
                student_id="synthetic-cross-section-student",
                offering_ids=[offerings[0].id, offerings[4].id],
            )
        ],
    )
