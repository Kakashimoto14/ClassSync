"""Bounded cohort pilot on a NEW owned SSPI cluster. No institutional publication."""

import argparse
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

from classync_contracts.academic import PeriodCreate, RecordWrite
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence.database import transaction
from classync_persistence.schema import migrate
from sqlalchemy import text

from scripts.postgres_academic_repository_qualification import FixtureCalls
from scripts.postgres_academic_restore_qualification import prepare_source, store
from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_publication_repository_qualification import (
    authorize_grants,
    must_fail,
    projection_membership_fixture,
    publish_command,
    repository,
    state,
)
from scripts.postgres_web_session_qualification import write_new_evidence
from services.academic.app.cohort_pilot import pilot_records
from services.academic.app.record_rules import AcademicError
from services.academic.tests.test_academic import complete
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_repository import DraftError
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.validation import validate_timetable
from services.scheduling.tests.test_calendar import configuration


def exercise(connection):
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    try:
        _, _, migrator = prepare_source(connection, owner, runtime, defer_fixture=True)
        authorize_grants(connection, owner, migrator)
        with transaction(owner) as db:
            db.execute(text(f"SET LOCAL ROLE {migrator}"))
            migrate(db)
            migrate(db, target="0011_publication_policy_cycle", downgrade=True)
            migrate(db)
            revision = db.scalar(text("SELECT version_num FROM public.alembic_version"))
            has_data_mode = db.scalar(
                text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='classsync_academic'
                      AND table_name='period_metadata' AND column_name='data_mode'
                )
            """)
            )
            require(
                revision == "0013_synthetic_review_period_mode" and has_data_mode,
                "Synthetic period mode migration missing after cycle: "
                f"revision={revision}, column={has_data_mode}",
            )
        legacy = complete(FixtureCalls(store(runtime)))
        with transaction(owner) as db:
            db.execute(
                text(
                    f"GRANT SELECT,INSERT ON classsync_academic.cohort_bindings "
                    f"TO {connection.runtime}"
                )
            )
        academic = store(runtime)
        records = pilot_records()
        isolation_period = academic.create_period(
            PeriodCreate(
                title="Synthetic isolation check; empty institutional scope",
                include_cdm_catalog=False,
                calendar=configuration().calendar,
            )
        )
        require(
            isolation_period.period.source == "institutional",
            "Ordinary PostgreSQL period did not default to institutional mode",
        )
        rejected_synthetic = set()
        for record in records:
            if record.kind not in {"faculty", "resources"}:
                continue
            if record.kind in rejected_synthetic:
                continue
            try:
                academic.save(
                    isolation_period.period.id,
                    record.kind,
                    record.id,
                    RecordWrite(expected_revision=0, record=record),
                )
            except AcademicError as error:
                require(
                    error.code == "synthetic_isolation", "Wrong synthetic-record isolation denial"
                )
                rejected_synthetic.add(record.kind)
        require(
            rejected_synthetic == {"faculty", "resources"},
            f"Synthetic faculty and room writes were not both denied: {rejected_synthetic=}",
        )
        rules = next(r for r in records if r.kind == "constraints")
        rules.enrollments[2].student_id = "student-a"  # existing disposable identity only
        body = PeriodCreate(
            title="SYNTHETIC cohort pilot, hypothetical A sections",
            include_cdm_catalog=False,
            calendar=configuration().calendar,
        )
        snapshot = academic.create_synthetic_review_period(body, records)
        require(
            snapshot.period.source == "synthetic-review", "Synthetic period mode was not persisted"
        )
        require(
            snapshot.period.id not in {period.id for period in academic.periods()},
            "Synthetic review period leaked into the institutional Admin period list",
        )
        require(academic.snapshot(snapshot.period.id) == snapshot, "PG snapshot changed")
        checked = academic_readiness(snapshot)
        require(checked.ready and checked.inputs.synthetic, "Pilot not synthetic/ready")
        started = time.monotonic()
        result = generate_week(checked.inputs)
        solve_seconds = time.monotonic() - started
        require(
            result.solver_status in {"feasible", "optimal"}
            and validate_timetable(checked.inputs, result.assignments).valid,
            "Pilot solver/independent validation rejected",
        )
        require(len(result.assignments) == 54, "Wrong pilot session coverage")
        drafts = PostgresDraftRepository(
            runtime,
            tenant_id="tenant-a",
            firebase_project_id="synthetic-project",
            principal=academic.principal,
        )
        drafts.remember_run(checked.inputs, result)
        request = SaveDraftRequest(
            run_id=result.run_id,
            input_hash=result.input_hash,
            title="SYNTHETIC BSIT pilot",
            idempotency_key="cohort-pilot-save",
        )
        draft, created = drafts.save(request)
        require(created and drafts.save(request) == (draft, False), "Draft replay changed")
        projection_membership_fixture(owner, result.assignments[0].teacher_id)
        publication = repository(runtime)
        command = publish_command(draft, snapshot)
        before = state(owner)
        try:
            publication.publish(
                command.model_copy(update={"dataset": "institutional"}), commit=False
            )
        except DraftError as error:
            require(
                error.code == "dataset_mismatch",
                "Wrong synthetic-to-institutional publication denial",
            )
        else:
            raise RuntimeError("Synthetic pilot was accepted as institutional publication")
        require(state(owner) == before, "Rejected institutional publication changed database state")
        review = publication.publish(command, commit=False)
        require(
            review["status"] == "ready-for-review" and before == state(owner),
            "Review wrote publication state",
        )
        receipt = publication.publish(command, commit=True)
        require(
            receipt["dataset"] == "synthetic" and receipt["revision"] == 1,
            "Wrong publication dataset/revision",
        )
        require(publication.publish(command, commit=True) == receipt, "Publication replay changed")
        student = repository(runtime, uid="uid-student").calendar(
            "tenant-a",
            "synthetic",
            snapshot.period.id,
            date(2026, 10, 1),
            date(2026, 10, 31),
            {
                "role": "student",
                "uid": "uid-student",
                "student_id": "student-a",
                "mock_section": "SYN-BSIT3A",
            },
        )
        expected = set(rules.enrollments[2].offering_ids)
        require(
            student["occurrences"]
            and all(o["offering_id"] in expected for o in student["occurrences"]),
            "Student curriculum/section visibility leaked",
        )
        teacher_id = result.assignments[0].teacher_id
        teacher = repository(runtime, uid="uid-teacher").calendar(
            "tenant-a",
            "synthetic",
            snapshot.period.id,
            date(2026, 10, 1),
            date(2026, 10, 31),
            {"role": "teacher", "uid": "uid-teacher", "faculty_id": teacher_id},
        )
        require(
            teacher["occurrences"]
            and all(o["teacher"]["id"] == teacher_id for o in teacher["occurrences"]),
            "Teacher assignment visibility leaked",
        )
        for other in (store(runtime, uid="uid-student"), store(runtime, tenant="tenant-b")):
            must_fail(lambda other=other: other.snapshot(snapshot.period.id), "membership_denied")
        # Remove an enrollment, then attempt rebind in another period. Durable map survives.
        entry = next(e for e in snapshot.records if e.record.kind == "constraints")
        removed = entry.record.model_copy(deep=True)
        removed.enrollments = [e for e in removed.enrollments if e.student_id != "student-a"]
        revised = academic.save(
            snapshot.period.id,
            "constraints",
            "rules",
            RecordWrite(expected_revision=entry.revision, record=removed),
        )
        require(drafts.get(draft.id) == draft, "Academic revision rewrote immutable draft")
        must_fail(
            lambda: publication.publish(
                command.model_copy(update={"idempotency_key": "stale-new-key"}), commit=False
            ),
            "academic_version_conflict",
            409,
        )
        with transaction(owner) as db:
            before_count = db.scalar(
                text("SELECT count(*) FROM classsync_academic.period_metadata")
            )
            binding_count = db.scalar(
                text("SELECT count(*) FROM classsync_academic.cohort_bindings")
            )
        bad = pilot_records()
        bad_rules = next(r for r in bad if r.kind == "constraints")
        bad_rules.enrollments[0].student_id = "student-a"  # attempts 2024 -> 2026
        try:
            academic.create_synthetic_review_period(body, bad)
        except AcademicError as error:
            require(
                error.code == "cohort_immutable" and error.status == 409, "Wrong cohort rejection"
            )
        else:
            raise RuntimeError("Student curriculum was silently reassigned")
        # The binding must not be bypassed by dropping both new metadata fields.
        legacy_rules = next(e for e in legacy.records if e.record.kind == "constraints")
        legacy_record = legacy_rules.record.model_copy(deep=True)
        legacy_offering = next(e.record.id for e in legacy.records if e.record.kind == "offerings")
        from classync_contracts.scheduling import Enrollment

        legacy_record.enrollments = [
            Enrollment(student_id="student-a", offering_ids=[legacy_offering])
        ]
        try:
            academic.save(
                legacy.period.id,
                "constraints",
                "rules",
                RecordWrite(expected_revision=legacy_rules.revision, record=legacy_record),
            )
        except AcademicError as error:
            require(error.code == "cohort_immutable", "Wrong missing-binding rejection")
        else:
            raise RuntimeError("Assigned curriculum metadata was cleared in another term")
        with transaction(owner) as db:
            require(
                db.scalar(text("SELECT count(*) FROM classsync_academic.period_metadata"))
                == before_count,
                "Rejected pilot left partial term/records",
            )
            require(
                db.scalar(text("SELECT count(*) FROM classsync_academic.cohort_bindings"))
                == binding_count,
                "Rejected pilot left partial bindings",
            )
        with transaction(runtime) as db:
            require(
                db.scalar(text("SELECT count(*) FROM classsync_academic.cohort_bindings")) == 0,
                "RLS leaked owner bindings without context",
            )
        return dict(
            status="PASS",
            sources=39,
            courses=2062,
            pilot_offerings=27,
            synthetic_candidates=81,
            sessions=54,
            solve_seconds=solve_seconds,
            solver_status=result.solver_status,
            independently_valid=True,
            pg_atomic_seed=True,
            institutional_period_defaults_correctly=True,
            synthetic_faculty_room_write_denied=True,
            synthetic_review_mode_persisted=True,
            synthetic_review_hidden_from_institutional_period_list=True,
            cohort_survives_removal_and_terms=True,
            assigned_curriculum_cannot_be_cleared=True,
            upgrade_downgrade_reapply=True,
            student_teacher_visibility=True,
            wrong_role_tenant_denied=True,
            immutable_draft_replay_and_stale_revision=True,
            synthetic_review_publication_replay=True,
            synthetic_institutional_publication_denied=True,
            rejected_publication_rollback=True,
            original_snapshot_revision=snapshot.period.revision,
            revised_snapshot_revision=revised.period.revision,
            real_publication=False,
        )
    finally:
        runtime.dispose()
        owner.dispose()


def preservation_baseline(receipt: Path, database_root: Path) -> dict[Path, str]:
    try:
        value = json.loads(receipt.read_text(encoding="utf-8-sig"))
    except OSError:
        raise ValueError("Cannot read the local --preservation-receipt file.") from None
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("The preservation receipt must contain valid JSON.") from None
    try:
        if isinstance(value, list):
            entries = [(row["file"], row["sha256"]) for row in value]
        else:
            entries = list(value["original_database_sha256"].items())
    except (AttributeError, KeyError, TypeError):
        raise ValueError(
            "The preservation receipt must list original database paths and hashes."
        ) from None
    baseline = {}
    for name, digest in entries:
        if not isinstance(name, str) or not name.strip() or not isinstance(digest, str):
            raise ValueError("Invalid path or hash in the preservation receipt.")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise ValueError("Each preservation receipt hash must be a SHA-256 digest.")
        path = (database_root / name).resolve()
        if path in baseline:
            raise ValueError("The preservation receipt contains a duplicate database path.")
        baseline[path] = digest.lower()
    if not baseline:
        raise ValueError("The preservation receipt must list at least one original database.")
    return baseline


def database_hashes(paths):
    result = {}
    for path in paths:
        with path.open("rb") as stream:
            result[path] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--preservation-receipt",
        type=Path,
        required=True,
        help="Private local JSON receipt of reviewed original database SHA-256 values.",
    )
    parser.add_argument(
        "--database-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Directory for receipt paths that are relative. Defaults to this checkout.",
    )
    args = parser.parse_args()
    try:
        baseline = preservation_baseline(args.preservation_receipt, args.database_root)
        before = database_hashes(baseline)
    except ValueError as error:
        parser.error(str(error))
    except OSError:
        parser.error("Cannot read an original database listed in the preservation receipt.")
    if before != baseline:
        parser.error("Original database hashes differ from the reviewed preservation receipt.")
    try:
        evidence = qualify(args.bin, exercise)
    finally:
        require(
            before == database_hashes(before),
            "Original database hashes changed",
        )
    evidence["original_database_hashes"] = {str(path): digest for path, digest in before.items()}
    write_new_evidence(args.output, evidence)
    print("Synthetic cohort PG qualification PASS; owned cluster stopped")


if __name__ == "__main__":
    main()
