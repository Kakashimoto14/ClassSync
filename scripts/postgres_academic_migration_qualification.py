"""Deterministic synthetic academic migration rehearsal; never accepts original paths."""

import argparse
import hashlib
import tempfile
from pathlib import Path

from classync_contracts.academic import CalendarWrite, RecordWrite
from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.database import transaction
from sqlalchemy import text

from scripts.postgres_disposable import checked_root, qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from scripts.postgres_web_session_qualification import write_new_evidence
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.academic.app.record_rules import (
    AcademicError,
    checksum,
    encode,
    references,
    unique_label,
    validate_calendar,
    validate_record,
)
from services.academic.app.repository import AcademicRepository
from services.academic.tests.test_academic import complete
from services.scheduling.tests.test_calendar import configuration

SCOPE, SOURCE_OWNER = "sandbox", "development-academic-sandbox"


def import_generated_snapshot(connection, repository, source, period_id, *, fail_after=None):
    root = checked_root(connection.root, Path(tempfile.gettempdir()))
    path = source.path.resolve()
    require(
        path.parent == root and path.name == "synthetic-source.sqlite3" and path.is_file(),
        "Only this cluster's generated synthetic source is accepted",
    )
    snapshot = source.snapshot(SCOPE, SOURCE_OWNER, period_id)
    validate_calendar(snapshot.period.calendar)
    typed = {(entry.record.kind, entry.record.id): entry.record for entry in snapshot.records}
    for entry in snapshot.records:
        validate_record(entry.record, period_id, lambda kind, identity: typed.get((kind, identity)))
    with source.connection() as db:
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM academic_records WHERE scope=? AND owner=? AND period_id=? "
                "ORDER BY kind,id",
                (SCOPE, SOURCE_OWNER, period_id),
            ).fetchall()
        ]
        stored_refs = {
            tuple(row)
            for row in db.execute(
                "SELECT source_kind,source_id,target_kind,target_id FROM academic_references "
                "WHERE scope=? AND owner=? AND period_id=?",
                (SCOPE, SOURCE_OWNER, period_id),
            ).fetchall()
        }
    expected_refs = {
        (record.kind, record.id, kind, identity)
        for record in typed.values()
        for kind, identity in references(record)
    }
    require(stored_refs == expected_refs, "Source references differ from validated records")
    for row in rows:
        record = typed[(row["kind"], row["id"])]
        require(
            row["unique_label"] == unique_label(record)
            and checksum(row["payload"]) == row["checksum"],
            "Source content integrity failed",
        )
    with repository.session(write=True) as db:
        db.execute(
            text("""
            INSERT INTO classsync_academic.period_metadata
                (tenant_id,owner_uid,id,title,revision,created_at)
            VALUES (:tenant,:owner,:period,:title,:revision,:created)
        """),
            repository.params(
                period_id,
                title=snapshot.period.title,
                revision=snapshot.period.revision,
                created=snapshot.period.created_at,
            ),
        )
        for index, row in enumerate(rows, 1):
            db.execute(
                text("""
                INSERT INTO classsync_academic.records
                  (tenant_id,owner_uid,period_id,kind,id,revision,unique_label,
                   updated_at,updated_by,payload,checksum)
                VALUES (:tenant,:owner,:period,:kind,:id,:revision,:unique_label,
                        :updated_at,:owner,:payload,:checksum)
            """),
                {**row, **repository.params(period_id)},
            )
            if fail_after == index:
                raise RuntimeError("synthetic interrupted import")
        for source_kind, source_id, target_kind, target_id in sorted(stored_refs):
            db.execute(
                text("""
                INSERT INTO classsync_academic.record_references VALUES
                    (:tenant,:owner,:period,:source_kind,:source_id,:target_kind,:target_id)
            """),
                repository.params(
                    period_id,
                    source_kind=source_kind,
                    source_id=source_id,
                    target_kind=target_kind,
                    target_id=target_id,
                ),
            )
        if snapshot.period.calendar:
            repository.calendar_in(db, period_id, snapshot.period.calendar)
    return snapshot, rows


def exercise(connection):
    foundation = identity_exercise(connection)
    root = checked_root(connection.root, Path(tempfile.gettempdir()))
    source_path = root / "synthetic-source.sqlite3"
    require(not source_path.exists(), "Generated source must be new")
    source = AcademicRepository(source_path)
    source.migrate()
    entered = complete(source)
    subject = next(entry for entry in entered.records if entry.record.id == "subject-a")
    changed = subject.record.model_copy(update={"name": "Synthetic edited migration source"})
    source.save(
        SCOPE,
        SOURCE_OWNER,
        entered.period.id,
        "subjects",
        changed.id,
        RecordWrite(expected_revision=subject.revision, record=changed),
    )
    latest = source.snapshot(SCOPE, SOURCE_OWNER, entered.period.id)
    source.save_calendar(
        SCOPE,
        SOURCE_OWNER,
        entered.period.id,
        CalendarWrite(expected_revision=latest.period.revision, calendar=configuration().calendar),
    )
    before_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    repository = PostgresAcademicRepository(
        runtime,
        tenant_id="tenant-a",
        firebase_project_id="synthetic-project",
        principal=VerifiedPrincipal(uid="uid-admin"),
    )
    pid = entered.period.id
    try:
        with transaction(owner) as db:
            db.execute(text(f"GRANT USAGE ON SCHEMA classsync_academic TO {connection.runtime}"))
            for table in ("period_metadata", "records", "record_references", "calendars"):
                db.execute(
                    text(
                        f"GRANT SELECT,INSERT ON classsync_academic.{table} TO {connection.runtime}"
                    )
                )
            db.execute(
                text(f"GRANT UPDATE ON classsync_academic.calendars TO {connection.runtime}")
            )
        try:
            import_generated_snapshot(connection, repository, source, pid, fail_after=3)
        except RuntimeError as error:
            require(str(error) == "synthetic interrupted import", "Unexpected migration failure")
        else:
            raise RuntimeError("Interrupted import did not fail")
        with transaction(owner) as db:
            for table, column in (
                ("period_metadata", "id"),
                ("records", "period_id"),
                ("record_references", "period_id"),
                ("calendars", "period_id"),
            ):
                require(
                    db.scalar(
                        text(
                            f"SELECT count(*) FROM classsync_academic.{table} "
                            f"WHERE {column}=:period"
                        ),
                        {"period": pid},
                    )
                    == 0,
                    "Interrupted import left partial data",
                )
        original, rows = import_generated_snapshot(connection, repository, source, pid)
        actual = repository.snapshot(pid)
        expected = original.model_copy(deep=True)
        expected.period.source = "institutional"
        for entry in expected.records:
            entry.updated_by = "uid-admin"
        require(actual == expected, "Mapped complete snapshots differ after migration")
        with repository.session() as db:
            transferred = (
                db.execute(
                    text("""
                SELECT kind,id,revision,payload,checksum FROM classsync_academic.records
                WHERE tenant_id=:tenant AND owner_uid=:owner AND period_id=:period ORDER BY kind,id
            """),
                    repository.params(pid),
                )
                .mappings()
                .all()
            )
        original_rows = [
            {key: row[key] for key in ("kind", "id", "revision", "payload", "checksum")}
            for row in rows
        ]
        require(
            [dict(row) for row in transferred] == original_rows,
            "Canonical payload/checksum/revision rows differ",
        )
        canonical_hash = checksum(encode(original_rows))
        try:
            import_generated_snapshot(connection, repository, source, pid)
        except AcademicError as error:
            require(error.code == "academic_integrity", "Replay returned wrong conflict")
        else:
            raise RuntimeError("Repeated import overwrote destination")
        runtime.dispose()
        require(repository.snapshot(pid) == actual, "Replay/reconnect changed imported state")
        require(
            hashlib.sha256(source_path.read_bytes()).hexdigest() == before_hash,
            "Read-only source extraction changed generated SQLite bytes",
        )
        return {
            "foundation": foundation,
            "generated_source_only": True,
            "source_sqlite_sha256_unchanged": before_hash,
            "mapped_snapshot_equal": True,
            "record_count": len(rows),
            "canonical_rows_sha256": canonical_hash,
            "payload_checksums_and_revisions_equal": True,
            "interrupted_import_atomic_rollback": True,
            "replay_conflict_preserves_data": True,
            "reconnect_preserves_import": True,
            "explicit_synthetic_mapping": {
                "source_scope": SCOPE,
                "source_owner": SOURCE_OWNER,
                "target_tenant": "tenant-a",
                "target_owner": "uid-admin",
            },
            "original_data_migration": False,
            "production_acceptance": False,
        }
    finally:
        runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and args.output.parent.is_dir(), "New output required")
    evidence = qualify(args.bin, exercise)
    write_new_evidence(args.output, evidence)
    print("Synthetic academic migration rehearsal passed; owned PostgreSQL stopped")


if __name__ == "__main__":
    main()
