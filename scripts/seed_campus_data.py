"""Owner-authorized, tenant-scoped AY 2026–2027 defense dataset seeder.

Dry-run is read-only. --apply is explicit, requires CLASSYNC_SEED_ENV=defense and
an existing Administrator membership. It never creates users or memberships.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages/api-contracts"), str(ROOT / "packages/persistence")]

from classync_contracts.academic import (  # noqa: E402
    AcademicCalendar,
    AcademicConstraints,
    AcademicFaculty,
    AcademicOffering,
    AcademicProgram,
    AcademicResource,
    AcademicSection,
    AcademicSubject,
    RecordWrite,
)
from classync_contracts.identity import VerifiedPrincipal  # noqa: E402
from classync_contracts.scheduling import Enrollment, Window  # noqa: E402
from classync_persistence.configuration import postgres_configuration  # noqa: E402
from classync_persistence.database import postgres_engine  # noqa: E402
from classync_persistence.schema import migrate  # noqa: E402
from pydantic import SecretStr, TypeAdapter  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

PERIOD_TITLE = "AY 2026-2027 · 1st Semester"
LEGACY_PERIOD_ID = "defense-ay-2026-2027-first"
SEED_NAMESPACE = uuid5(NAMESPACE_URL, "classsync:authorized-defense-dataset:v1")


def stable_uuid(kind: str, identity: str) -> str:
    return str(uuid5(SEED_NAMESPACE, f"{kind}:{identity}"))


PERIOD_ID = stable_uuid("period", "ay-2026-2027-first")
REFERENCE = "Owner-authorized ClassSync defense dataset · administrator editable"
adapter = TypeAdapter(AcademicResource)


def load_json(path: str) -> list[dict]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def room_defaults(room: dict) -> AcademicResource:
    """Return defaults only for a catalog row already marked schedulable."""
    if room.get("schedulable") is not True:
        raise ValueError("Excluded campus spaces cannot be activated by the seed")
    room_type = room.get("room_type")
    if room_type == "computer_lab":
        capacity = 40
    elif room_type in {"athletic_space", "special_activity"}:
        capacity = 60
    elif room_type in {"lecture_classroom", "science_lab"}:
        capacity = 45
    else:
        room_type, capacity = "lecture_classroom", 45
    return adapter.validate_python(
        {
            **{k: v for k, v in room.items() if k not in {"alias", "aliasUnconfirmed"}},
            "kind": "resources",
            "source": "cdm-provisional",
            "condition": "operational",
            "capacity": room.get("capacity") or capacity,
            "room_type": room_type,
            "schedulable": True,
            "type_verified": True,
            "capacity_verified": True,
            "availability": [{"day": day, "start": 420, "end": 1260} for day in range(6)],
            "availability_verified": True,
            "verification_note": REFERENCE,
            "alias_unconfirmed": room.get("aliasUnconfirmed", False),
        }
    )


def merge_room_defaults(existing: AcademicResource, defaults: AcademicResource) -> AcademicResource:
    """Fill unverified gaps while retaining administrator-entered values and restrictions."""
    if not existing.schedulable or existing.condition == "maintenance":
        return existing
    return existing.model_copy(
        update={
            "condition": "operational",
            "room_type": (
                existing.room_type
                if existing.room_type
                in {
                    "lecture_classroom",
                    "computer_lab",
                    "science_lab",
                    "special_activity",
                    "athletic_space",
                }
                else defaults.room_type
            ),
            "type_verified": True,
            "capacity": existing.capacity or defaults.capacity,
            "capacity_verified": True,
            "availability": existing.availability or defaults.availability,
            "availability_verified": True,
            "verification_note": existing.verification_note or defaults.verification_note,
        }
    )


def defense_calendar() -> AcademicCalendar:
    return AcademicCalendar(
        academic_year="2026-2027",
        semester="first",
        effective_start="2026-08-01",
        effective_end="2026-12-31",
        timezone="Asia/Manila",
        instructional_days=list(range(6)),
    )


def _course_hours(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def curriculum_subjects() -> list[AcademicSubject]:
    catalog = json.loads(
        (
            ROOT / "packages/api-contracts/classync_contracts/catalogs/curriculum-review.json"
        ).read_text(encoding="utf-8")
    )
    cohorts = {"1": "2026", "2": "2025", "3": "2024", "4": "2023"}
    result = []
    for year, cohort in cohorts.items():
        version = next(
            v for v in catalog["versions"] if v["program"] == "BSIT" and v["entry_cohort"] == cohort
        )
        courses = [
            c
            for c in catalog["courses"]
            if c["curriculum_version_id"] == version["id"] and c["year_level"] == year
        ]
        first = [c for c in courses if c["semester"] == "1"]
        later = [c for c in courses if c["semester"] == "2"]
        # Keep a 32–36 subject catalogue; only first-semester courses receive offerings.
        selected = first + later[: max(0, 8 - len(first))]
        if int(year) == 4 and len(selected) < 8:
            for extra_cohort in ("2022", "2024", "2025", "2026"):
                extra_version = next(
                    v
                    for v in catalog["versions"]
                    if v["program"] == "BSIT" and v["entry_cohort"] == extra_cohort
                )
                extra = next(
                    (
                        c
                        for c in catalog["courses"]
                        if c["curriculum_version_id"] == extra_version["id"]
                        and c["year_level"] == "4"
                        and c["id"] not in {x["id"] for x in selected}
                    ),
                    None,
                )
                if extra:
                    selected.append(extra)
                if len(selected) >= 8:
                    break
        for c in selected:
            lec, lab = _course_hours(c["lec_hours_printed"]), _course_hours(c["lab_hours_printed"])
            weekly = max(30, (lec + lab) * 60)
            pattern = [weekly] if weekly <= 240 and weekly % 30 == 0 else [180, 180]
            if sum(pattern) != weekly:
                pattern = [weekly // 2, weekly // 2]
            result.append(
                AcademicSubject(
                    id=stable_uuid("subject", f"{c['curriculum_version_id']}:{c['id']}"),
                    kind="subjects",
                    code=c["subject_code"],
                    name=c["subject_title"],
                    curriculum_version_id=c["curriculum_version_id"],
                    curriculum_course_id=c["id"],
                    curriculum_review_verified=True,
                    curriculum_review_reference=REFERENCE,
                    contact_minutes_verified=True,
                    contact_minutes_reference=REFERENCE,
                    year_level=int(year),
                    semester="first" if c["semester"] == "1" else "second",
                    provenance="administrator-entered",
                    program_ids=[stable_uuid("program", "BSIT")],
                    required_weekly_minutes=weekly,
                    patterns=[
                        {
                            "id": stable_uuid("pattern", f"{c['curriculum_version_id']}:{c['id']}"),
                            "durations": pattern,
                            "distinct_days": True,
                        }
                    ],
                    required_room_type=(
                        "athletic_space"
                        if any(
                            k in c["subject_title"].lower()
                            for k in ("pahfit", "physical education", "pe ")
                        )
                        else "computer_lab"
                        if lab
                        else "lecture_classroom"
                    ),
                    lec_hours=lec,
                    lab_hours=lab,
                    units=_course_hours(c["units_printed"]),
                )
            )
    if not 32 <= len(result) <= 36:
        raise ValueError(f"Curriculum catalog produced {len(result)} subjects, expected 32–36")
    return result


def build_academic_records(period_id: str, room_catalog: list[dict]) -> list:
    subjects = curriculum_subjects()
    subject_by_year = defaultdict(list)
    for subject in subjects:
        subject_by_year[subject.year_level].append(subject)
    sections = []
    for year in range(1, 5):
        for letter, capacity in (("A", 35 + year), ("B", 37 + year)):
            version_id = next(s.curriculum_version_id for s in subject_by_year[year])
            sections.append(
                AcademicSection(
                    id=stable_uuid("section", f"BSIT-{year}{letter}"),
                    kind="sections",
                    period_id=period_id,
                    program_id=stable_uuid("program", "BSIT"),
                    year_level=year,
                    section_letter=letter,
                    entry_cohort_year=2027 - year,
                    curriculum_version_id=version_id,
                    cohort_assignment_verified=True,
                    identity_verified=True,
                    population=12,
                    population_verified=True,
                    capacity=capacity,
                    verification_reference=REFERENCE,
                )
            )
    faculty = []
    specialties = ["Programming", "Database/Web", "Networking/OS", "Math/Theory", "GenEd/PE"]
    names = [
        "Maria Santos",
        "Jose Reyes",
        "Ana Cruz",
        "Mark Garcia",
        "Liza Mendoza",
        "Ramon Dela Cruz",
        "Grace Bautista",
        "Noel Villanueva",
        "Teresa Flores",
        "Paolo Navarro",
        "Celia Ramos",
        "Daniel Aquino",
    ]
    for index, name in enumerate(names):
        covered = [
            s
            for s in subjects
            if (s.year_level + index) % len(specialties) == index % len(specialties)
        ]
        if not covered:
            covered = subjects[index::12]
        faculty.append(
            AcademicFaculty(
                id=stable_uuid("faculty", f"{index + 1:02}"),
                name=f"{name} · {specialties[index % 5]}",
                subject_ids=[s.id for s in covered],
                availability=[Window(day=d, start=420, end=1260) for d in range(6)],
                max_weekly_minutes=1440,
                max_daily_minutes=480,
                weekly_unit_cap=18 + index % 7,
                eligibility_verified=True,
                availability_verified=True,
                workload_verified=True,
                verification_reference=REFERENCE,
            )
        )
    rooms = [room_defaults(r) for r in room_catalog if r.get("schedulable")]
    if len(rooms) != 41 or len([r for r in rooms if r.room_type == "computer_lab"]) < 4:
        raise ValueError("Campus catalog must contain exactly 41 schedulable rooms and four labs")
    offerings = []
    for section in sections:
        for subject in subject_by_year[section.year_level]:
            if (
                subject.semester != "first"
                or subject.curriculum_version_id != section.curriculum_version_id
            ):
                continue
            teachers = [f.id for f in faculty if subject.id in f.subject_ids]
            compatible = [r.id for r in rooms if r.room_type == subject.required_room_type]
            offerings.append(
                AcademicOffering(
                    id=stable_uuid("offering", f"{subject.id}:{section.id}"),
                    subject_id=subject.id,
                    section_id=section.id,
                    activity_type="pahfit"
                    if subject.required_room_type == "athletic_space"
                    else "computer_lab_instruction"
                    if subject.required_room_type == "computer_lab"
                    else "academic_instruction",
                    teacher_ids=teachers[:1],
                    room_ids=compatible[:8],
                    required_room_type=subject.required_room_type,
                    minimum_capacity=section.population,
                    term_offering_verified=True,
                    verification_reference=REFERENCE,
                )
            )
    if not 32 <= len(subjects) <= 36 or not offerings:
        raise ValueError("Seed curriculum/offerings did not satisfy required counts")
    constraints = AcademicConstraints(
        id="rules",
        kind="constraints",
        operating_windows=[Window(day=d, start=420, end=1260) for d in range(6)],
        transition_buffer_minutes=10,
        all_intended_offerings_supplied=True,
        operating_windows_verified=True,
        verification_reference=REFERENCE,
        shared_scope_verified=True,
        shared_scope_reference=REFERENCE,
        enrollments=[],
    )
    offering_by_section = defaultdict(list)
    for offering in offerings:
        offering_by_section[offering.section_id].append(offering.id)
    student_first_names = [
        "Aira",
        "Miguel",
        "Janelle",
        "Joshua",
        "Kyra",
        "Nathan",
        "Angel",
        "Gabriel",
        "Sofia",
        "Liam",
        "Trisha",
        "Ethan",
    ]
    surnames = [
        "Dela Cruz",
        "Santos",
        "Reyes",
        "Garcia",
        "Mendoza",
        "Bautista",
        "Villanueva",
        "Ramos",
        "Flores",
        "Navarro",
        "Aquino",
        "Castro",
    ]
    students = []
    for section in sections:
        year = section.year_level
        cohort = 2027 - year
        prefix = str(cohort)[-2:]
        for n in range(12):
            roster_number = 101 + n + (12 if section.section_letter == "B" else 0)
            student_id = f"{prefix}-{roster_number:05}"
            students.append(
                {
                    "id": student_id,
                    "person_id": stable_uuid("student-person", student_id),
                    "display_name": (
                        f"{student_first_names[n]} {surnames[(n + year) % len(surnames)]}"
                    ),
                    "registered_email": (f"student.{prefix}.{roster_number:05}@student.pnm.edu.ph"),
                    "section_id": section.id,
                    "enrollment": Enrollment(
                        student_id=student_id,
                        offering_ids=offering_by_section[section.id],
                        entry_cohort_year=section.entry_cohort_year,
                        curriculum_version_id=section.curriculum_version_id,
                    ),
                }
            )
    constraints.enrollments = [s["enrollment"] for s in students]
    program = AcademicProgram(
        id=stable_uuid("program", "BSIT"),
        kind="programs",
        acronym="BSIT",
        name="Information Technology",
        institute="Institute of Computer Studies",
        section_policy="degree",
        allowed_year_levels=[1, 2, 3, 4],
    )
    return [program, *subjects, *sections, *faculty, *rooms, *offerings, constraints], students


def _same(a, b) -> bool:
    return json.dumps(a.model_dump(mode="json"), sort_keys=True) == json.dumps(
        b.model_dump(mode="json"), sort_keys=True
    )


def apply_seed(repo) -> tuple[int, int]:
    """Apply all new/seed-default rows atomically; preserve existing admin edits."""
    calendar = defense_calendar()
    with repo.session(write=True) as db:
        _archive_legacy_period(db, repo)
        rows = (
            db.execute(
                text(
                    "SELECT id FROM classsync_academic.period_metadata "
                    "WHERE tenant_id=:tenant AND owner_uid=:owner AND title=:title"
                ),
                {**repo.keys, "title": PERIOD_TITLE},
            )
            .scalars()
            .all()
        )
        if len(rows) > 1:
            raise ValueError("Multiple periods use the defense title; review them before seeding")
        if rows:
            period_id = rows[0]
            snapshot = repo.snapshot_in(db, period_id)
        else:
            period_id = PERIOD_ID
            db.execute(
                text(
                    "INSERT INTO classsync_academic.period_metadata "
                    "(tenant_id,owner_uid,id,title) VALUES (:tenant,:owner,:period,:title)"
                ),
                repo.params(period_id, title=PERIOD_TITLE),
            )
            from services.academic.app.record_rules import initial_records

            for initial in initial_records(True):
                repo.write_in(db, period_id, RecordWrite(expected_revision=0, record=initial))
            snapshot = repo.snapshot_in(db, period_id)
        if snapshot.period.calendar is None:
            repo.calendar_in(db, period_id, calendar)
            repo.bump(db, period_id)
            snapshot = repo.snapshot_in(db, period_id)
        elif snapshot.period.calendar != calendar:
            raise ValueError(
                "Existing period dates differ; review/edit them in Admin before seeding"
            )
        catalog = load_json("packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json")
        records, students = build_academic_records(period_id, catalog)
        index = {(e.record.kind, e.record.id): e for e in snapshot.records}
        written = 0
        for record in records:
            previous = index.get((record.kind, record.id))
            if previous:
                if (
                    record.kind == "resources"
                    and record.schedulable
                    and not (
                        previous.record.type_verified
                        and previous.record.capacity_verified
                        and previous.record.availability_verified
                        and previous.record.condition == "operational"
                    )
                ):
                    record = merge_room_defaults(previous.record, record)
                    if not _same(previous.record, record):
                        repo.write_in(
                            db,
                            period_id,
                            RecordWrite(expected_revision=previous.revision, record=record),
                        )
                        written += 1
                        # Refresh revisions after each successful record write.
                        index = {
                            (e.record.kind, e.record.id): e
                            for e in repo.snapshot_in(db, period_id).records
                        }
                elif record.kind == "constraints" and _same(previous.record, AcademicConstraints()):
                    repo.write_in(
                        db,
                        period_id,
                        RecordWrite(expected_revision=previous.revision, record=record),
                    )
                    written += 1
                    index = {
                        (e.record.kind, e.record.id): e
                        for e in repo.snapshot_in(db, period_id).records
                    }
                elif not _same(previous.record, record) and record.kind != "resources":
                    # Existing records belong to the administrator; never overwrite edits.
                    continue
                continue
            repo.write_in(db, period_id, RecordWrite(expected_revision=0, record=record))
            written += 1
            index = {
                (e.record.kind, e.record.id): e for e in repo.snapshot_in(db, period_id).records
            }
        inserted_students = 0
        for student in students:
            if db.scalar(
                text(
                    "SELECT 1 FROM classsync_identity.students "
                    "WHERE tenant_id=:tenant AND id=:student"
                ),
                {**repo.keys, "student": student["id"]},
            ):
                continue
            db.execute(
                text(
                    "INSERT INTO classsync_identity.people "
                    "(tenant_id,id,display_name) VALUES (:tenant,:person,:name)"
                ),
                {**repo.keys, "person": student["person_id"], "name": student["display_name"]},
            )
            db.execute(
                text(
                    "INSERT INTO classsync_identity.students "
                    "(tenant_id,id,person_id,registered_email,enrollment_status,"
                    "verification_source) "
                    "VALUES (:tenant,:student,:person,:email,'unverified','unverified')"
                ),
                {
                    **repo.keys,
                    "student": student["id"],
                    "person": student["person_id"],
                    "email": student["registered_email"],
                },
            )
            inserted_students += 1
    return written, inserted_students


def _archive_legacy_period(db, repo) -> bool:
    """Retire the known broken ID without violating append-only audit references."""
    legacy = (
        db.execute(
            text("""
                SELECT id,title,data_mode FROM classsync_academic.period_metadata
                WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:legacy
                FOR UPDATE
            """),
            {**repo.keys, "legacy": LEGACY_PERIOD_ID},
        )
        .mappings()
        .one_or_none()
    )
    if legacy is None:
        return False
    if legacy["title"] != PERIOD_TITLE or legacy["data_mode"] != "institutional":
        raise ValueError(
            "The legacy period does not match the approved defense period; preserving it"
        )

    params = {**repo.keys, "period": LEGACY_PERIOD_ID}

    # Immutable administrative activity references the old period ID, so retain
    # its rows and move the existing record set out of the active-title target.
    archived = (
        db.execute(
            text("""
            UPDATE classsync_academic.period_metadata
            SET title=:title, revision=revision+1
            WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:period
            RETURNING revision
        """),
            {**params, "title": f"Archived invalid period · {LEGACY_PERIOD_ID}"},
        )
        .mappings()
        .one_or_none()
    )
    if archived is None:
        raise RuntimeError("The locked legacy period changed before replacement")
    db.execute(
        text("""
            INSERT INTO classsync_scheduling.administrator_activity
                (tenant_id,owner_uid,event_id,period_id,event_type,entity_type,entity_ref,revision)
            VALUES (:tenant,:owner,:event,:period,'academic.period.archived','period',:ref,
                    :revision)
        """),
        {
            **params,
            "event": str(uuid4()),
            "ref": hashlib.sha256(LEGACY_PERIOD_ID.encode("utf-8")).hexdigest(),
            "revision": archived["revision"],
        },
    )
    return True


def _arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--confirm-defense-tenant",
        help="exact tenant ID confirmation required with --apply",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _arguments(argv)
    if os.getenv("CLASSYNC_SEED_ENV") != "defense":
        raise SystemExit(
            "Set CLASSYNC_SEED_ENV=defense explicitly; other environments are refused."
        )
    url_value = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    tenant = os.getenv("INSTITUTIONAL_TENANT_ID")
    project = os.getenv("FIREBASE_PROJECT_ID")
    admin_uid = os.getenv("CLASSYNC_SEED_ADMIN_UID")
    if not all((url_value, tenant, project, admin_uid)):
        raise SystemExit(
            "Set MIGRATION_DATABASE_URL (or DATABASE_URL), INSTITUTIONAL_TENANT_ID, "
            "FIREBASE_PROJECT_ID and CLASSYNC_SEED_ADMIN_UID."
        )
    if args.apply and args.confirm_defense_tenant != tenant:
        raise SystemExit(
            "For --apply, pass --confirm-defense-tenant with the exact "
            "INSTITUTIONAL_TENANT_ID of the approved defense tenant."
        )
    import certifi

    try:
        target = make_url(url_value)
        if target.drivername in {"postgresql", "postgres"}:
            target = target.set(drivername="postgresql+psycopg")
        target = target.set(query={})
    except Exception as error:
        raise SystemExit("Database URL is invalid; expected PostgreSQL with TLS.") from error
    url, options = postgres_configuration(
        SecretStr(target.render_as_string(hide_password=False)),
        transport="verify-full",
        environment="production",
        firebase_project_id=project,
        tenant_id=tenant,
        application_name="classsync-defense-seed",
        tls_root_cert=certifi.where(),
    )
    engine = postgres_engine(url, connect_args=options, pool_size=1, max_overflow=0, pool_timeout=5)
    sys.path.insert(0, str(ROOT))
    from services.academic.app.postgres_repository import PostgresAcademicRepository

    try:
        principal = VerifiedPrincipal(uid=admin_uid)
        repo = PostgresAcademicRepository(
            engine, tenant_id=tenant, firebase_project_id=project, principal=principal
        )
        with repo.session() as db:
            period = (
                db.execute(
                    text(
                        "SELECT id,title FROM classsync_academic.period_metadata "
                        "WHERE tenant_id=:tenant AND owner_uid=:owner AND title=:title"
                    ),
                    {**repo.keys, "title": PERIOD_TITLE},
                )
                .mappings()
                .one_or_none()
            )
            current = repo.snapshot_in(db, period["id"]) if period else None
            if current and current.period.source != "institutional":
                raise ValueError("The target academic period is not an institutional period.")
            catalog = load_json(
                "packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json"
            )
            planned, students = build_academic_records(
                current.period.id if current else PERIOD_ID, catalog
            )
            print(
                f"Target: {PERIOD_TITLE}; defense; 41 schedulable rooms; "
                f"12 excluded; {len(planned)} records; {len(students)} roster rows"
            )
            print(
                "Curriculum source is an unreviewed extraction. Defense defaults are "
                "owner-authorized and administrator-editable."
            )
            if (
                current
                and current.period.calendar
                and current.period.calendar != defense_calendar()
            ):
                raise ValueError(
                    "Existing period date range differs from the approved defense range."
                )
            if args.dry_run:
                print(
                    "Dry run: no writes performed. Administrator membership and "
                    "current tenant/project were verified."
                )
                return 0
        if args.apply:
            with engine.begin() as connection:
                migrate(connection, target="head")
        written, roster = apply_seed(repo)
        print(
            f"Applied atomically: {written} academic records created/updated; "
            f"{roster} roster rows created. Student enrollment remains unverified; "
            "no memberships/accounts were created."
        )
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
