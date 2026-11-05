"""Disposable contract controls for scanner projections; never institutional import.

These invented identities, availability, verification references and contact minutes
exist ONLY inside the newly marked qualification database. Public catalog code/title
identity is retained to exercise exact-code matching, not to attest curriculum approval.
"""

from uuid import uuid4

from classync_contracts.academic import PeriodCreate, RecordWrite
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.curriculum import catalog
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence.database import transaction
from sqlalchemy import text

from scripts.postgres_driver_qualification import require
from services.academic.app.curriculum_catalog import subject_from_course
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_rules import verified_result
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository


def prepare(connection, owner, runtime, *, uid, project, requests=False):
    with transaction(owner) as db:
        if requests:
            db.execute(
                text(
                    "GRANT SELECT,INSERT,UPDATE ON classsync_academic.announcements "
                    f"TO {connection.runtime}"
                )
            )
            db.execute(
                text(
                    "GRANT SELECT,INSERT,UPDATE ON "
                    f"classsync_scheduling.classroom_requests TO {connection.runtime}"
                )
            )
        db.execute(
            text(
                "GRANT USAGE ON SCHEMA classsync_academic,classsync_scheduling "
                f"TO {connection.runtime}"
            )
        )
        for table in (
            "period_metadata",
            "records",
            "record_references",
            "calendars",
            "cohort_bindings",
        ):
            db.execute(
                text(f"GRANT SELECT,INSERT ON classsync_academic.{table} TO {connection.runtime}")
            )
        db.execute(
            text(
                "GRANT UPDATE(revision) ON classsync_academic.period_metadata "
                f"TO {connection.runtime}"
            )
        )
        for table in ("records", "record_references", "calendars"):
            db.execute(text(f"GRANT UPDATE ON classsync_academic.{table} TO {connection.runtime}"))
        db.execute(
            text(f"GRANT DELETE ON classsync_academic.record_references TO {connection.runtime}")
        )
        for table in ("solver_runs", "drafts", "published_versions"):
            db.execute(
                text(f"GRANT SELECT,INSERT ON classsync_scheduling.{table} TO {connection.runtime}")
            )
        for table in ("publication_heads", "room_restrictions"):
            db.execute(
                text(
                    f"GRANT SELECT,INSERT,UPDATE ON classsync_scheduling.{table} "
                    f"TO {connection.runtime}"
                )
            )
        db.execute(
            text(f"GRANT SELECT ON classsync_scheduling.restriction_audit TO {connection.runtime}")
        )
        db.execute(
            text(
                "GRANT USAGE,SELECT ON SEQUENCE "
                "classsync_scheduling.published_versions_sequence_seq "
                f"TO {connection.runtime}"
            )
        )
        db.execute(
            text(
                "GRANT EXECUTE ON FUNCTION classsync_scheduling.lock_publication_authority() "
                f"TO {connection.runtime}"
            )
        )
        db.execute(
            text(
                "INSERT INTO classsync_identity.students VALUES "
                "('tenant-a','SYN-001','browser-student')"
            )
        )
        db.execute(
            text(
                "INSERT INTO classsync_identity.faculty VALUES "
                "('tenant-a','SYN-CONTROL-FACULTY','browser-faculty')"
            )
        )
    principal = VerifiedPrincipal(uid=uid)
    academic = PostgresAcademicRepository(
        runtime, tenant_id="tenant-a", firebase_project_id=project, principal=principal
    )
    calendar = AcademicCalendar(
        academic_year="2026-2027",
        semester="first",
        effective_start="2026-10-01",
        effective_end="2026-12-31",
        instructional_days=[0],
    )
    snapshot = academic.create_period(
        PeriodCreate(
            title="Disposable scanner qualification control",
            include_cdm_catalog=False,
            calendar=calendar,
        )
    )
    data = catalog()
    version = next(
        item
        for item in data["versions"]
        if item["program"] == "BSIT" and int(item["entry_cohort"]) == 2026
    )
    rows = [
        row
        for row in data["courses"]
        if row["curriculum_version_id"] == version["id"]
        and row["year_level"] == "1"
        and row["semester"] == "1"
    ][:2]
    require(len(rows) == 2, "Expected two public exact-code control courses")
    subjects = []
    reference = "Disposable contract control only; not an institutional verification"
    for row in rows:
        subject = subject_from_course(row["id"]).model_dump(mode="json")
        subject.update(
            required_weekly_minutes=60,
            patterns=[{"id": "test-sixty", "durations": [60]}],
            curriculum_review_verified=True,
            contact_minutes_verified=True,
            curriculum_review_reference=reference,
            contact_minutes_reference=reference,
        )
        subjects.append(subject)
    window = [{"day": 0, "start": 480, "end": 720}]
    records = [
        {
            "kind": "programs",
            "id": "bsit",
            "acronym": "BSIT",
            "name": "Disposable program control",
            "institute": "Disposable test scope",
        },
        *subjects,
        {
            "kind": "sections",
            "id": "SYN-CONTROL-SECTION",
            "period_id": snapshot.period.id,
            "program_id": "bsit",
            "year_level": 1,
            "section_letter": "A",
            "population": 1,
            "population_verified": True,
            "entry_cohort_year": 2026,
            "curriculum_version_id": version["id"],
            "cohort_assignment_verified": True,
            "identity_verified": True,
            "verification_reference": reference,
        },
        {
            "kind": "faculty",
            "id": "SYN-CONTROL-FACULTY",
            "institutional_id": "SYN-CONTROL-FACULTY",
            "name": "Disposable contract control faculty",
            "subject_ids": [s["id"] for s in subjects],
            "availability": window,
            "max_weekly_minutes": 240,
            "eligibility_verified": True,
            "availability_verified": True,
            "workload_verified": True,
            "verification_reference": reference,
        },
        {
            "kind": "resources",
            "id": "SYN-CONTROL-ROOM",
            "name": "Disposable contract control room",
            "building": "Disposable qualification scope",
            "source": "administrator-supplied",
            "schedulable": True,
            "condition": "operational",
            "capacity": 20,
            "capacity_verified": True,
            "availability": window,
            "availability_verified": True,
            "verification_note": reference,
        },
        *[
            {
                "kind": "offerings",
                "id": f"SYN-CONTROL-OFFERING-{index}",
                "subject_id": s["id"],
                "section_id": "SYN-CONTROL-SECTION",
                "teacher_ids": ["SYN-CONTROL-FACULTY"],
                "room_ids": ["SYN-CONTROL-ROOM"],
                "term_offering_verified": True,
                "verification_reference": reference,
            }
            for index, s in enumerate(subjects)
        ],
        {
            "kind": "constraints",
            "id": "rules",
            "operating_windows": window,
            "all_intended_offerings_supplied": True,
            "operating_windows_verified": True,
            "shared_scope_verified": True,
            "shared_scope_reference": reference,
            "verification_reference": reference,
            "enrollments": [
                {
                    "student_id": "SYN-001",
                    "entry_cohort_year": 2026,
                    "curriculum_version_id": version["id"],
                    "offering_ids": [f"SYN-CONTROL-OFFERING-{i}" for i in range(2)],
                }
            ],
        },
    ]
    if requests:
        index = next(i for i, record in enumerate(records) if record["kind"] == "resources")
        alternate = {
            **records[index],
            "id": "SYN-CONTROL-ALT-ROOM",
            "name": "Disposable alternate control room",
        }
        records.insert(index + 1, alternate)
        for record in records:
            if record["kind"] == "offerings":
                record["room_ids"].append(alternate["id"])
    for record in records:
        previous = next(
            (
                item
                for item in snapshot.records
                if item.record.kind == record["kind"] and item.record.id == record["id"]
            ),
            None,
        )
        body = RecordWrite.model_validate(
            {"expected_revision": previous.revision if previous else 0, "record": record}
        )
        snapshot = academic.save(snapshot.period.id, body.record.kind, body.record.id, body)
    ready = academic_readiness(snapshot)
    require(ready.ready, "Disposable controls blocked: " + str([i.code for i in ready.issues]))
    result = generate_week(ready.inputs)
    verified_result(ready.inputs, result)
    drafts = PostgresDraftRepository(
        runtime, tenant_id="tenant-a", firebase_project_id=project, principal=principal
    )
    drafts.remember_run(ready.inputs, result)
    draft, _ = drafts.save(
        SaveDraftRequest(
            run_id=result.run_id,
            input_hash=result.input_hash,
            title="Disposable scanner publication control",
            idempotency_key="scanner-" + uuid4().hex,
        )
    )
    publication = PostgresPublicationRepository(
        runtime, tenant_id="tenant-a", firebase_project_id=project, principal=principal
    )
    command = PublicationCommand(
        draft_id=draft.id,
        dataset="institutional",
        source="administrator",
        expected_version=0,
        expected_academic_revision=snapshot.period.revision,
        calendar=calendar,
        idempotency_key="scanner-publish-" + uuid4().hex,
    )
    receipt = publication.publish(command, commit=True)
    require(receipt["status"] == "published", "Disposable control was not published")
    return {
        "period": snapshot.period.id,
        "codes": [s["code"] for s in subjects],
        "student": "SYN-001",
        "program": "BSIT",
        "year_level": 1,
        "draft": draft.id,
        "faculty": "SYN-CONTROL-FACULTY",
        "production_acceptance": False,
    }
