"""Explicit, configurable synthetic imports; never replaces existing academic records."""

import hashlib
import itertools
from uuid import NAMESPACE_URL, uuid5

from classync_contracts.academic import AcademicConstraints, RecordWrite
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.scheduling import Contract
from pydantic import Field, model_validator

from .repository import adapter, catalog_data, timestamp


class FixtureRequest(Contract):
    program_ids: list[str] = Field(default_factory=lambda: ["bsit"], min_length=1, max_length=9)
    year_levels: list[int] = Field(default_factory=lambda: [3], min_length=1, max_length=4)
    section_letters: list[str] = Field(default_factory=lambda: ["A"], min_length=1, max_length=4)
    certificate_groups: list[str] = Field(default_factory=lambda: ["Certificate A"], max_length=4)
    calendar: AcademicCalendar

    @model_validator(mode="after")
    def configured(self):
        programs = {p["id"] for p in catalog_data()[0]}
        if (
            not set(self.program_ids) <= programs
            or not set(self.year_levels) <= {1, 2, 3, 4}
            or not set(self.section_letters) <= set("ABCD")
        ):
            raise ValueError("Choose catalog programs, years 1–4 and mock sections A–D")
        for values in [
            self.program_ids,
            self.year_levels,
            self.section_letters,
            self.certificate_groups,
        ]:
            if len(values) != len(set(values)):
                raise ValueError("Fixture configuration cannot contain duplicates")
        if any(not s.strip() or len(s) > 40 for s in self.certificate_groups):
            raise ValueError("Use short nonempty certificate group labels")
        if self.calendar.published_version:
            raise ValueError("A fixture cannot declare publication")
        return self


NAMES = {
    "bsit": ["Computing Foundations", "Software Design"],
    "bscpe": ["Digital Logic", "Computer Architecture"],
    "bsed-sci": ["Science Teaching Methods", "Laboratory Inquiry"],
    "beed-gen": ["Elementary Learning Design", "Literacy Development"],
    "beed-eced": ["Early Childhood Learning", "Play and Development"],
    "btled-ict": ["ICT Instruction", "Digital Learning Resources"],
    "bsba-hrm": ["Human Resource Planning", "Organizational Learning"],
    "bse": ["Enterprise Planning", "Market Research"],
    "tcp": ["Learning Assessment", "Teaching Practice"],
}


def fixture_records(body, pid):
    programs, rooms = catalog_data()
    windows = [{"day": d, "start": 480, "end": 1020} for d in body.calendar.instructional_days]
    records = [{**p, "kind": "programs"} for p in programs]
    records += [
        {
            **{k: v for k, v in r.items() if k not in {"alias", "aliasUnconfirmed"}},
            "kind": "resources",
            "source": "cdm-provisional",
            "alias": r.get("alias"),
            "alias_unconfirmed": r.get("aliasUnconfirmed", False),
        }
        for r in rooms
    ]
    # These IDs and locations are separate from all 59 provisional inventory entries.
    resources = [f"synthetic-room-{i}" for i in range(1, 5)]
    records += [
        {
            "kind": "resources",
            "id": rid,
            "name": f"Synthetic Room {i + 1}",
            "building": "Synthetic teaching facility",
            "source": "synthetic",
            "schedulable": True,
            "condition": "operational",
            "availability": windows,
            "verification_note": "Synthetic solver assumption; not a verified CdM room.",
        }
        for i, rid in enumerate(resources)
    ]
    for p in programs:
        for year, semester, index in itertools.product(
            ([None] if p["id"] == "tcp" else range(1, 5)), ["first", "second"], range(2)
        ):
            identity = f"syn-{p['id']}-{year or 'certificate'}-{semester}-{index + 1}"
            records.append(
                {
                    "kind": "subjects",
                    "id": identity,
                    "code": identity.upper(),
                    "name": f"{NAMES[p['id']][index]} {year or 'Certificate'} (synthetic)",
                    "program_ids": [p["id"]],
                    "year_level": year,
                    "semester": semester,
                    "provenance": "synthetic",
                    "required_weekly_minutes": 180,
                    "patterns": [{"id": "split-90", "durations": [90, 90]}],
                }
            )
            tid = f"teacher-{identity}"
            records.append(
                {
                    "kind": "faculty",
                    "id": tid,
                    "name": f"Sample Instructor {identity.upper()}",
                    "subject_ids": [identity],
                    "availability": windows,
                    "max_weekly_minutes": 2160,
                    "max_daily_minutes": 360,
                }
            )
    for program in body.program_ids:
        groups = (
            [(None, None, group) for group in body.certificate_groups]
            if program == "tcp"
            else [
                (y, s, None) for y, s in itertools.product(body.year_levels, body.section_letters)
            ]
        )
        for year, letter, custom in groups:
            group_id = letter or hashlib.sha256(custom.encode()).hexdigest()[:8]
            sid = f"syn-{program}-{year or 'certificate'}-{group_id}"
            records.append(
                {
                    "kind": "sections",
                    "id": sid,
                    "period_id": pid,
                    "program_id": program,
                    "year_level": year,
                    "section_letter": letter,
                    "custom_label": custom,
                }
            )
            for index in range(2):
                subject = (
                    f"syn-{program}-{year or 'certificate'}-{body.calendar.semester}-{index + 1}"
                )
                records.append(
                    {
                        "kind": "offerings",
                        "id": f"{sid}-{index + 1}",
                        "subject_id": subject,
                        "section_id": sid,
                        "teacher_ids": [f"teacher-{subject}"],
                        "room_ids": resources,
                    }
                )
    rules = AcademicConstraints.model_validate(
        {
            "operating_windows": windows,
            "all_intended_offerings_supplied": True,
            "options": {"time_limit_seconds": 3.0},
        }
    )
    records.append(rules.model_dump())
    return [adapter.validate_python(r) for r in records]


def import_fixture(repo, body, scope, owner):
    payload = body.model_dump_json()
    pid = str(uuid5(NAMESPACE_URL, "classsync-c1-v1:" + payload))
    with repo.connection(True) as db:
        existing = db.execute(
            "SELECT 1 FROM academic_periods WHERE scope=? AND owner=? AND id=?", (scope, owner, pid)
        ).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO academic_periods VALUES (?,?,?,?,1,?)",
                (
                    scope,
                    owner,
                    pid,
                    f"Synthetic {body.calendar.academic_year} · {body.calendar.semester} semester",
                    timestamp(),
                ),
            )
            db.execute(
                "INSERT INTO academic_calendars VALUES (?,?,?,?)",
                (scope, owner, pid, body.calendar.model_dump_json()),
            )
            for record in fixture_records(body, pid):
                repo.write_in(
                    db, scope, owner, pid, RecordWrite(expected_revision=0, record=record)
                )
    return repo.snapshot(scope, owner, pid)
