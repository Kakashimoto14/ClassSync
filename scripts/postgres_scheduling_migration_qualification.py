"""Generated-only Scheduling SQLite-to-PG rehearsal; no original source/target arguments."""

import argparse
import hashlib
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from classync_contracts.identity import MembershipAuthorizationError, VerifiedPrincipal
from classync_contracts.scheduling import GenerationInput, GenerationResult, SaveDraftRequest
from classync_persistence.academic_periods import utc_timestamp
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from sqlalchemy import text

from scripts.postgres_disposable import checked_root, qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.app.draft_repository import DraftRepository
from services.scheduling.app.draft_rules import (
    DraftError,
    DraftSnapshot,
    encode,
    verified_result,
)
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.tests.test_engine import tiny

SOURCE_NAME = "synthetic-scheduling-source.sqlite3"
SCOPE, OWNER, TENANT, PROJECT = "administrator", "uid-admin", "tenant-a", "synthetic-project"
COLUMNS = {
    "solver_runs": ("id", "scope", "owner", "created_at", "schema_version", "payload", "checksum"),
    "scheduling_drafts": (
        "id",
        "run_id",
        "scope",
        "owner",
        "title",
        "created_at",
        "schema_version",
        "status",
        "idempotency_key",
        "payload",
        "checksum",
    ),
}


def canonical_utc(value):
    try:
        parsed = datetime.fromisoformat(value)
        require(
            parsed.tzinfo is not None and parsed.astimezone(UTC).isoformat() == value,
            "Generated source timestamp must be canonical UTC",
        )
    except (TypeError, ValueError) as error:
        raise RuntimeError("Generated source timestamp must be canonical UTC") from error
    return value


def source_path(connection, source):
    root = checked_root(connection.root, Path(tempfile.gettempdir()))
    source = Path(source)
    require(
        source.name == SOURCE_NAME
        and not source.is_symlink()
        and source.is_file()
        and source.resolve().parent == root,
        "Only this cluster's generated Scheduling source is accepted",
    )
    return source.resolve()


def read_generated_source(connection, source):
    path = source_path(connection, source)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    # The generated fixture is closed and immutable during this read. No source migration,
    # writable connection, WAL recovery, or sidecar creation is permitted by this reader.
    db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        require(
            db.execute("PRAGMA user_version").fetchone()[0] == 2,
            "Generated Scheduling source version must be2",
        )
        require(
            [row[0] for row in db.execute("PRAGMA integrity_check")] == ["ok"]
            and not db.execute("PRAGMA foreign_key_check").fetchall(),
            "Generated Scheduling source integrity failed",
        )
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(tables == set(COLUMNS), "Unexpected generated Scheduling source tables")
        rows = {}
        for table, columns in COLUMNS.items():
            require(
                tuple(row[1] for row in db.execute(f"PRAGMA table_info({table})")) == columns,
                "Unexpected generated Scheduling source columns",
            )
            rows[table] = [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY id")]
        require(
            rows["solver_runs"] and rows["scheduling_drafts"], "Generated source must be nonempty"
        )
    finally:
        db.close()
    require(hashlib.sha256(path.read_bytes()).hexdigest() == before, "Generated source changed")
    decoder = DraftSnapshot()
    runs = {}
    for table_rows in rows.values():
        for row in table_rows:
            require(
                row["scope"] == SCOPE and row["owner"] == OWNER,
                "Only the explicitly mapped synthetic Administrator source is accepted",
            )
            canonical_utc(row["created_at"])
    for row in rows["solver_runs"]:
        payload = decoder.unpack(row)
        inputs = GenerationInput.model_validate(payload["inputs"])
        result = GenerationResult.model_validate(payload["result"])
        require(
            inputs.synthetic and all(room.source == "synthetic" for room in inputs.rooms),
            "Only generated synthetic Scheduling records are accepted",
        )
        verified_result(inputs, result)
        require(
            row["id"] == result.run_id and row["id"] not in runs,
            "Source run identity differs or repeats",
        )
        runs[row["id"]] = (inputs, result)
    details, keys, draft_ids, saved_runs = {}, set(), set(), set()
    for row in rows["scheduling_drafts"]:
        require(
            row["status"] == "draft"
            and isinstance(row["idempotency_key"], str)
            and 8 <= len(row["idempotency_key"]) <= 100,
            "Source draft status/key is incompatible",
        )
        draft = decoder.detail(row)
        require(
            row["id"] not in draft_ids
            and row["run_id"] not in saved_runs
            and row["idempotency_key"] not in keys,
            "Source draft identity/key repeats",
        )
        require(row["run_id"] in runs, "Source draft has no server-held run")
        inputs, result = runs[row["run_id"]]
        require(
            draft.input_snapshot == inputs and draft.generation_result == result,
            "Source draft differs from its server-held run",
        )
        draft_ids.add(row["id"])
        saved_runs.add(row["run_id"])
        keys.add(row["idempotency_key"])
        details[row["id"]] = draft
    return {"rows": rows, "details": details, "sha256": before, "path": path}


def import_generated_schedule(connection, repository, source, *, fail_after=None):
    bundle = read_generated_source(connection, source)
    require(
        repository.keys == {"tenant": TENANT, "owner": OWNER}
        and repository.context.project_id == PROJECT,
        "Only the explicitly mapped synthetic PG owner/tenant/project is accepted",
    )
    with repository.session(write=True) as db:
        observed = db.execute(
            text(
                "SELECT current_database(),current_user,inet_server_port(),host(inet_server_addr())"
            )
        ).one()
        require(
            tuple(observed) == ("postgres", connection.runtime, connection.port, "127.0.0.1"),
            "Scheduling migration target binding differs from owned cluster",
        )
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": encode(["classsync-draft-save", TENANT, OWNER])},
        )
        run_ids = [row["id"] for row in bundle["rows"]["solver_runs"]]
        if db.scalar(
            text("""
            SELECT count(*) FROM classsync_scheduling.solver_runs
            WHERE tenant_id=:tenant AND owner_uid=:owner AND id=ANY(CAST(:ids AS text[]))
        """),
            {"tenant": TENANT, "owner": OWNER, "ids": run_ids},
        ):
            raise DraftError(
                409, "migration_replay", "Generated import already exists; no rows changed"
            )
        inserted = 0
        for row in bundle["rows"]["solver_runs"]:
            db.execute(
                text("""
                INSERT INTO classsync_scheduling.solver_runs
                (tenant_id,owner_uid,id,created_at,schema_version,payload,checksum)
                VALUES (:tenant,:owner,:id,:created_at,:schema_version,:payload,:checksum)
            """),
                {**row, "tenant": TENANT},
            )
            inserted += 1
            if inserted == fail_after:
                raise RuntimeError("synthetic interrupted Scheduling import")
        for row in bundle["rows"]["scheduling_drafts"]:
            db.execute(
                text("""
                INSERT INTO classsync_scheduling.drafts
                (tenant_id,owner_uid,id,run_id,title,created_at,schema_version,status,
                    idempotency_key,payload,checksum)
                VALUES (:tenant,:owner,:id,:run_id,:title,:created_at,:schema_version,:status,
                    :idempotency_key,:payload,:checksum)
            """),
                {**row, "tenant": TENANT},
            )
            inserted += 1
            if inserted == fail_after:
                raise RuntimeError("synthetic interrupted Scheduling import")
        require(
            hashlib.sha256(bundle["path"].read_bytes()).hexdigest() == bundle["sha256"],
            "Generated source changed before import commit",
        )
    return bundle


def must_fail(operation, code):
    try:
        operation()
    except (DraftError, MembershipAuthorizationError) as error:
        require(error.code == code, f"Wrong generated migration negative result: {error.code}")
    else:
        raise RuntimeError(f"Generated migration negative path succeeded: {code}")


def raw_target(owner):
    with transaction(owner) as db:
        return {
            table: [
                dict(row)
                for row in db.execute(
                    text(
                        f"SELECT * FROM classsync_scheduling.{table} "
                        "ORDER BY tenant_id,owner_uid,id"
                    )
                ).mappings()
            ]
            for table in ("solver_runs", "drafts")
        }


def exercise(connection, *, key_conflict=False):
    foundation = identity_exercise(connection)
    root = checked_root(connection.root, Path(tempfile.gettempdir()))
    path = root / SOURCE_NAME
    require(not path.exists(), "Generated source must be new")
    source = DraftRepository(path)
    source.migrate()
    inputs = tiny()
    generated = generate_week(inputs)
    verified_result(inputs, generated)
    source.remember_run(inputs, generated, SCOPE, OWNER)
    body = SaveDraftRequest(
        run_id=generated.run_id,
        input_hash=generated.input_hash,
        title="Synthetic migration draft",
        idempotency_key="migrated-save-key",
    )
    original, _ = source.save(body, SCOPE, OWNER)
    pending = generated.model_copy(update={"run_id": str(uuid4())})
    source.remember_run(inputs, pending, SCOPE, OWNER)
    expired = generated.model_copy(update={"run_id": str(uuid4())})
    source.remember_run(inputs, expired, SCOPE, OWNER)
    expired_at = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    with source.connection(write=True) as db:
        db.execute("UPDATE solver_runs SET created_at=? WHERE id=?", (expired_at, expired.run_id))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    repository = PostgresDraftRepository(
        runtime,
        tenant_id=TENANT,
        firebase_project_id=PROJECT,
        principal=VerifiedPrincipal(uid=OWNER),
    )
    try:
        with transaction(owner) as db:
            db.execute(text(f"GRANT USAGE ON SCHEMA classsync_scheduling TO {connection.runtime}"))
            db.execute(
                text(
                    "GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA classsync_scheduling "
                    f"TO {connection.runtime}"
                )
            )
            identity_context(db, tenant_id=TENANT, uid="uid-admin-other")
            audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
            db.execute(
                text(
                    "INSERT INTO classsync_identity.people VALUES ('tenant-a','person-admin-other')"
                )
            )
            db.execute(
                text(
                    "INSERT INTO classsync_identity.memberships VALUES "
                    "('tenant-a','uid-admin-other','person-admin-other',NULL,NULL,"
                    "ARRAY['administrator'],'active',1)"
                )
            )
        other = PostgresDraftRepository(
            runtime,
            tenant_id=TENANT,
            firebase_project_id=PROJECT,
            principal=VerifiedPrincipal(uid="uid-admin-other"),
        )
        other.remember_run(inputs, generated)
        other_draft, _ = other.save(body)
        if key_conflict:
            unrelated = generated.model_copy(update={"run_id": str(uuid4())})
            repository.remember_run(inputs, unrelated)
            unrelated_draft, _ = repository.save(
                body.model_copy(update={"run_id": unrelated.run_id})
            )
            baseline = raw_target(owner)
            must_fail(
                lambda: import_generated_schedule(connection, repository, path),
                "idempotency_conflict",
            )
            require(raw_target(owner) == baseline, "Conflict changed unrelated target rows")
            require(
                repository.get(unrelated_draft.id) == unrelated_draft
                and other.get(other_draft.id) == other_draft,
                "Conflict changed existing owner snapshots",
            )
            require(
                hashlib.sha256(path.read_bytes()).hexdigest() == before,
                "Conflict changed generated source",
            )
            return {
                "source": str(path),
                "source_sha256": before,
                "source_unchanged": True,
                "existing_key_batch_rollback": True,
                "all_existing_rows_unchanged": True,
                "production_acceptance": False,
            }
        baseline = raw_target(owner)
        for stop in (1, 4):
            try:
                import_generated_schedule(connection, repository, path, fail_after=stop)
            except RuntimeError as error:
                require(
                    str(error) == "synthetic interrupted Scheduling import",
                    "Unexpected interrupted import error",
                )
            else:
                raise RuntimeError("Interrupted generated import succeeded")
            require(raw_target(owner) == baseline, "Interrupted import changed target rows")
        for uid, tenant, project in (
            ("uid-a", TENANT, PROJECT),
            (OWNER, "tenant-b", PROJECT),
            (OWNER, TENANT, "wrong-project"),
        ):
            denied = PostgresDraftRepository(
                runtime,
                tenant_id=tenant,
                firebase_project_id=project,
                principal=VerifiedPrincipal(uid=uid),
            )
            must_fail(lambda denied=denied: denied.list(), "membership_denied")
        bundle = import_generated_schedule(connection, repository, path)
        require(repository.get(original.id) == original, "Imported full draft snapshot differs")
        with runtime.connect() as db:
            old_pid = db.scalar(text("SELECT pg_backend_pid()"))
        runtime.dispose()
        with runtime.connect() as db:
            require(
                db.scalar(text("SELECT pg_backend_pid()")) != old_pid,
                "Reconnect reused physical PostgreSQL session",
            )
        require(
            repository.get(original.id) == original, "Physical reconnect lost imported snapshot"
        )
        require(repository.save(body) == (original, False), "Imported save key did not replay")
        must_fail(
            lambda: repository.save(body.model_copy(update={"idempotency_key": "changed-key"})),
            "idempotency_conflict",
        )
        must_fail(
            lambda: import_generated_schedule(connection, repository, path), "migration_replay"
        )
        with transaction(owner) as db:
            for source_table, target in (
                ("solver_runs", "solver_runs"),
                ("scheduling_drafts", "drafts"),
            ):
                actual = []
                for row in db.execute(
                    text(f"""
                    SELECT * FROM classsync_scheduling.{target}
                    WHERE tenant_id=:tenant AND owner_uid=:owner ORDER BY id
                """),
                    {"tenant": TENANT, "owner": OWNER},
                ).mappings():
                    actual.append(
                        {
                            key: utc_timestamp(row[key])
                            if key == "created_at"
                            else OWNER
                            if key == "owner"
                            else SCOPE
                            if key == "scope"
                            else row[key]
                            for key in COLUMNS[source_table]
                        }
                    )
                require(actual == bundle["rows"][source_table], "Imported raw row/checksum differs")
        expired_body = body.model_copy(
            update={"run_id": expired.run_id, "idempotency_key": "expired-migration-key"}
        )
        must_fail(lambda: repository.save(expired_body), "run_expired")
        pending_body = body.model_copy(
            update={"run_id": pending.run_id, "idempotency_key": "pending-migration-key"}
        )
        pending_draft, created = repository.save(pending_body)
        require(
            created and pending_draft.generation_result == pending,
            "Unexpired migrated unsaved run cannot be saved",
        )
        require(repository.get(original.id) == original, "Post-migration commands changed original")
        with transaction(owner) as db:
            identity_context(db, tenant_id=TENANT, uid=OWNER)
            audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
            db.execute(
                text(
                    "UPDATE classsync_identity.memberships SET state='revoked',revision=2 "
                    "WHERE tenant_id=:tenant AND uid=:owner"
                ),
                repository.keys,
            )
        must_fail(
            lambda: import_generated_schedule(connection, repository, path), "membership_denied"
        )
        with transaction(owner) as db:
            identity_context(db, tenant_id=TENANT, uid=OWNER)
            audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
            db.execute(
                text(
                    "UPDATE classsync_identity.memberships SET state='active',revision=3 "
                    "WHERE tenant_id=:tenant AND uid=:owner"
                ),
                repository.keys,
            )
        require(
            repository.get(original.id) == original and other.get(other_draft.id) == other_draft,
            "Current membership checks changed owner snapshots",
        )
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == before == bundle["sha256"],
            "Generated Scheduling source bytes changed",
        )
        return {
            "foundation": foundation,
            "migration": "0006_scheduling_drafts",
            "source": str(path),
            "source_sha256": before,
            "source_unchanged": True,
            "imported_runs": 3,
            "imported_drafts": 1,
            "full_snapshot_exact": True,
            "raw_payload_checksum_metadata_exact": True,
            "physical_reconnect": True,
            "interrupted_run_and_draft_insert_rollback": True,
            "replay_conflict": True,
            "original_save_key_replays": True,
            "alternate_key_conflict": True,
            "expired_run_stays_expired": True,
            "pending_run_saveable": True,
            "unrelated_owner_preserved": True,
            "current_role_tenant_project_denied": True,
            "revoked_import_denied": True,
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
    positive = qualify(args.bin, exercise)
    conflict = qualify(args.bin, lambda connection: exercise(connection, key_conflict=True))
    write_new_evidence(args.output, {"migration": positive, "existing_key_conflict": conflict})
    print("Generated Scheduling migration qualification passed; owned PG stopped")


if __name__ == "__main__":
    main()
