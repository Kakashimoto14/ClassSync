"""Create an explicitly synthetic local CdM bootstrap review period.

This is not an institutional Registrar/Facilities import and does not create identity
records, a production PostgreSQL tenant, or a published timetable. Use only an isolated
SQLite path ending in ``.bootstrap-sandbox.sqlite3``.
"""

import argparse
import json
from pathlib import Path

from classync_contracts.academic import PeriodCreate, RecordWrite

from services.academic.app.repository import AcademicRepository

SOURCE = "owner_bootstrap_seed"
OWNER = "development-academic-sandbox"
SCOPE = "sandbox"
TITLE = "AY 2026-2027 · 1st Semester"
WINDOWS = [{"day": day, "start": 480, "end": 1020} for day in range(5)]
SUBJECTS = (
    ("ITHUMCI", "Human-Computer Interaction", "FAC-CDM-001"),
    ("ITDMATH", "Discrete Mathematics", "FAC-CDM-003"),
    ("ITELECT3", "IT Elective 3", "FAC-CDM-002"),
    ("ITASE1", "Application Systems Engineering 1", "FAC-CDM-002"),
    ("ITAPPSD", "Applications Development and Emerging Technologies", "FAC-CDM-002"),
    ("ITADBMS", "Advanced Database Management Systems", "FAC-CDM-001"),
    ("ITNETW2", "Networking 2", "FAC-CDM-003"),
    ("ITINFOM", "Information Management", "FAC-CDM-001"),
    ("ITOPSYS", "Operating Systems", "FAC-CDM-003"),
    ("UNDSELF", "Understanding the Self", "FAC-CDM-004"),
)
FACULTY = (
    ("FAC-CDM-001", "Prof. Maria Santos", ["ithumci", "itadbms", "itinfom"]),
    ("FAC-CDM-002", "Prof. Jose Reyes", ["itappsd", "itase1", "itelect3"]),
    ("FAC-CDM-003", "Prof. Elena Cruz", ["itnetw2", "itopsys", "itdmath"]),
    ("FAC-CDM-004", "Prof. Roberto Lim", ["undself"]),
)
def upsert(repo, period_id, snapshot, record):
    current = next(
        (item for item in snapshot.records
         if item.record.kind == record["kind"] and item.record.id == record["id"]),
        None,
    )
    expected = current.revision if current else 0
    body = RecordWrite.model_validate({"expected_revision": expected, "record": record})
    return repo.save(SCOPE, OWNER, period_id, body.record.kind, body.record.id, body)


def seed(path: Path):
    path = path.expanduser().resolve()
    if not path.name.endswith(".bootstrap-sandbox.sqlite3"):
        raise ValueError("Refusing to seed: use an isolated *.bootstrap-sandbox.sqlite3 file")
    repo = AcademicRepository(path)
    repo.migrate()
    period = next((item for item in repo.periods(SCOPE, OWNER) if item.title == TITLE), None)
    snapshot = (
        repo.snapshot(SCOPE, OWNER, period.id)
        if period else repo.create_period(PeriodCreate(title=TITLE), SCOPE, OWNER)
    )
    pid = snapshot.period.id
    for code, name, _ in SUBJECTS:
        snapshot = upsert(repo, pid, snapshot, {
            "kind": "subjects", "id": code.lower(), "code": code, "name": name,
            "program_ids": ["bsit", "btled-ict"], "required_weekly_minutes": 180,
            "patterns": [{"id": "two-90", "durations": [90, 90]}],
            "provenance": "synthetic", "curriculum_review_reference": SOURCE,
            "contact_minutes_reference": SOURCE,
        })
    for faculty_id, name, subjects in FACULTY:
        snapshot = upsert(repo, pid, snapshot, {
            "kind": "faculty", "id": faculty_id, "name": name, "synthetic": True,
            "subject_ids": subjects, "availability": WINDOWS,
            "verification_reference": SOURCE,
        })
    section_ids = {"BSIT": "bsit-3a", "BTLED": "btled-ict-1a"}
    for program_id, section_id, year in (
        ("bsit", section_ids["BSIT"], 3), ("btled-ict", section_ids["BTLED"], 1),
    ):
        snapshot = upsert(repo, pid, snapshot, {
            "kind": "sections", "id": section_id, "program_id": program_id,
            "period_id": pid, "year_level": year, "section_letter": "A",
            "identity_verified": False, "cohort_assignment_verified": False,
            "verification_reference": SOURCE,
        })
    for index, (code, _, faculty_id) in enumerate(SUBJECTS):
        for section_id in section_ids.values():
            snapshot = upsert(repo, pid, snapshot, {
                "kind": "offerings", "id": f"seed-offering-{index}-{section_id}",
                "subject_id": code.lower(), "section_id": section_id,
                "teacher_ids": [faculty_id], "room_ids": [],
                "term_offering_verified": False, "verification_reference": SOURCE,
            })
    snapshot = upsert(repo, pid, snapshot, {
        "kind": "constraints", "id": "rules", "operating_windows": WINDOWS,
        "operating_windows_verified": False, "all_intended_offerings_supplied": False,
        "verification_reference": SOURCE,
    })
    manifest = {
        "source": SOURCE,
        "scope": "local synthetic sandbox only",
        "official_publication_created": False,
        "student_identity_records_created": False,
        "room_capacity_or_schedulability_overrides_created": False,
        "period_id": pid,
        "academic_record_count": len(snapshot.records),
        "catalog_room_count": sum(item.record.kind == "resources" for item in snapshot.records),
        "note": (
            "Owner bootstrap values are synthetic. Canonical CdM room records remain provisional; "
            "capacity and operational availability were not inferred or overridden."
        ),
    }
    manifest_path = path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-path", type=Path,
        default=Path("var/bootstrap-sandbox/classsync.bootstrap-sandbox.sqlite3"),
    )
    args = parser.parse_args()
    try:
        result = seed(args.database_path)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
