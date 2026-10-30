"""Real solver/draft checks on a new marked disposable PostgreSQL cluster only."""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from classync_contracts.identity import MembershipAuthorizationError, VerifiedPrincipal
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from classync_persistence.schema import migrate
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.app.draft_rules import DraftError, digest, encode
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.tests.test_engine import tiny


def must_fail(operation, code):
    try:
        operation()
    except (DraftError, MembershipAuthorizationError) as error:
        require(error.code == code, f"Wrong draft negative result: {error.code}")
    else:
        raise RuntimeError(f"Draft negative path unexpectedly succeeded: {code}")


def exercise(connection):
    foundation = identity_exercise(connection)
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)

    def store(uid="uid-admin", tenant="tenant-a", project="synthetic-project"):
        return PostgresDraftRepository(
            runtime,
            tenant_id=tenant,
            firebase_project_id=project,
            principal=VerifiedPrincipal(uid=uid),
        )

    repository = store()
    try:
        with transaction(owner) as db:
            db.execute(text(f"GRANT USAGE ON SCHEMA classsync_scheduling TO {connection.runtime}"))
            db.execute(
                text(
                    "GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA classsync_scheduling "
                    f"TO {connection.runtime}"
                )
            )
            identity_context(db, tenant_id="tenant-a", uid="uid-a")
            audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
            db.execute(
                text("""
                UPDATE classsync_identity.memberships SET state='active', revision=3
                WHERE tenant_id='tenant-a' AND uid='uid-a'
            """)
            )
            db.execute(
                text("INSERT INTO classsync_identity.people VALUES ('tenant-a','person-admin2')")
            )
            identity_context(db, tenant_id="tenant-a", uid="uid-admin2")
            db.execute(
                text("""
                INSERT INTO classsync_identity.memberships VALUES
                ('tenant-a','uid-admin2','person-admin2',NULL,NULL,ARRAY['administrator'],'active',1)
            """)
            )
        inputs = tiny()
        result = generate_week(inputs)
        require(
            result.solver_status in {"optimal", "feasible"}, "Solver did not produce a candidate"
        )
        repository.remember_run(inputs, result)

        def request(run=result, key="draft-qualified-key", **changes):
            return SaveDraftRequest(
                run_id=run.run_id,
                input_hash=run.input_hash,
                title="Synthetic qualification",
                idempotency_key=key,
            ).model_copy(update=changes)

        body = request()
        draft, created = repository.save(body)
        require(created and repository.get(draft.id) == draft, "Draft snapshot did not round-trip")
        require(
            draft.generation_result == result and draft.input_snapshot == inputs,
            "Server-held generation changed",
        )
        require(
            repository.save(body) == (draft, False), "Identical replay did not return same draft"
        )
        must_fail(lambda: repository.save(request(key="altered-save-key")), "idempotency_conflict")
        must_fail(lambda: repository.save(request(title="Changed")), "idempotency_conflict")
        must_fail(lambda: repository.save(request(input_hash="0" * 64)), "idempotency_conflict")
        must_fail(
            lambda: repository.save(request(run_id="client-supplied-run")), "idempotency_conflict"
        )
        must_fail(
            lambda: repository.save(request(run_id="missing", key="unused-missing-key")),
            "run_not_found",
        )
        other = result.model_copy(update={"run_id": str(uuid4())})
        repository.remember_run(inputs, other)
        must_fail(lambda: repository.save(request(other)), "idempotency_conflict")
        # A rejected second key was never accepted/bound; it may now save another run.
        other_draft, other_created = repository.save(request(other, key="altered-save-key"))
        require(other_created and other_draft.id != draft.id, "Rejected key became an alias")
        require(repository.get(draft.id) == draft, "Conflicting replay altered original")
        for changes in (
            {"solver_status": "unknown"},
            {"solver_status": "infeasible"},
            {"input_hash": "0" * 64},
            {"assignments": []},
        ):
            invalid = result.model_copy(update={"run_id": str(uuid4()), **changes})
            must_fail(
                lambda invalid=invalid: repository.remember_run(inputs, invalid),
                "invalid_generated_run",
            )
        second = store("uid-admin2")
        must_fail(lambda: second.get(draft.id), "draft_not_found")
        second.remember_run(inputs, result)
        second_draft, _ = second.save(body)
        require(second_draft.id != draft.id, "Owners shared a draft")
        for denied in (store("uid-a"), store(tenant="tenant-b"), store(project="wrong-project")):
            must_fail(lambda denied=denied: denied.get(draft.id), "membership_denied")
        with runtime.connect() as db:
            old_backend = db.scalar(text("SELECT pg_backend_pid()"))
        runtime.dispose()
        with runtime.connect() as db:
            require(
                db.scalar(text("SELECT pg_backend_pid()")) != old_backend,
                "Reconnect reused the previous physical PostgreSQL session",
            )
        require(store().get(draft.id) == draft, "Reconnect lost exact snapshot")
        require(repository.list(limit=1).has_more, "Pagination did not report remaining rows")

        competing = result.model_copy(update={"run_id": str(uuid4())})
        repository.remember_run(inputs, competing)
        barrier = Barrier(3)

        def save_competing():
            barrier.wait()
            return repository.save(request(competing, key="concurrent-save-key"))

        with ThreadPoolExecutor(max_workers=2) as pool:
            with transaction(owner) as lock:
                lock.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                    {"key": encode(["classsync-draft-save", "tenant-a", "uid-admin"])},
                )
                futures = [pool.submit(save_competing) for _ in range(2)]
                barrier.wait()
                waiting = 0
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    with transaction(owner) as observer:
                        waiting = observer.scalar(
                            text("""
                            SELECT count(*) FROM pg_stat_activity
                            WHERE usename=:runtime AND wait_event_type='Lock'
                        """),
                            {"runtime": connection.runtime},
                        )
                    if waiting == 2:
                        break
                    time.sleep(0.03)
                require(waiting == 2, "Did not observe both competing save lock waiters")
            saved = [future.result(timeout=10) for future in futures]
        require(
            len({value.id for value, _ in saved}) == 1
            and sum(created for _, created in saved) == 1,
            "Concurrent save had multiple winners",
        )

        expired = result.model_copy(update={"run_id": str(uuid4())})
        payload = encode(
            {"inputs": inputs.model_dump(mode="json"), "result": expired.model_dump(mode="json")}
        )
        with transaction(owner) as db:
            db.execute(
                text("""
                INSERT INTO classsync_scheduling.solver_runs
                (tenant_id,owner_uid,id,created_at,payload,checksum)
                VALUES ('tenant-a','uid-admin',:id,:created,:payload,:checksum)
            """),
                {
                    "id": expired.run_id,
                    "created": datetime.now(UTC) - timedelta(hours=25),
                    "payload": payload,
                    "checksum": digest(payload),
                },
            )
        must_fail(lambda: repository.save(request(expired, key="expired-save-key")), "run_expired")
        malformed_run = result.model_copy(update={"run_id": str(uuid4())})
        repository.remember_run(inputs, malformed_run)
        malformed = draft.model_copy(
            update={
                "id": str(uuid4()),
                "run_id": malformed_run.run_id,
                "generation_result": malformed_run,
                "allocated_minutes": 0,
            }
        )

        def raw_draft(value, owner_uid, key):
            payload = encode(value.model_dump(mode="json"))
            with transaction(owner) as db:
                db.execute(
                    text("""
                    INSERT INTO classsync_scheduling.drafts
                    (tenant_id,owner_uid,id,run_id,title,created_at,idempotency_key,payload,checksum)
                    VALUES ('tenant-a',:owner,:id,:run,:title,:created,:key,:payload,:checksum)
                """),
                    {
                        "owner": owner_uid,
                        "id": value.id,
                        "run": value.run_id,
                        "title": value.title,
                        "created": value.created_at,
                        "key": key,
                        "payload": payload,
                        "checksum": digest(payload),
                    },
                )

        raw_draft(malformed, "uid-admin", "malformed-save-key")
        must_fail(lambda: repository.get(malformed.id), "snapshot_integrity")
        must_fail(lambda: repository.list(), "snapshot_integrity")
        crossed = draft.model_copy(
            update={
                "id": str(uuid4()),
                "run_id": competing.run_id,
                "creator": "uid-admin2",
            }
        )
        try:
            raw_draft(crossed, "uid-admin2", "cross-owner-save-key")
        except DBAPIError as error:
            require(error.orig.sqlstate == "23503", "Cross-owner run FK returned wrong result")
        else:
            raise RuntimeError("Draft accepted another owner's server run")
        checksum_run = result.model_copy(update={"run_id": str(uuid4())})
        checksum_payload = encode(
            {
                "inputs": inputs.model_dump(mode="json"),
                "result": checksum_run.model_dump(mode="json"),
            }
        )
        constraints = ["cross-owner-run-fk"]
        for label, statement, params, sqlstate in (
            (
                "checksum",
                """INSERT INTO classsync_scheduling.solver_runs
                (tenant_id,owner_uid,id,created_at,payload,checksum)
                VALUES ('tenant-a','uid-admin',:id,now(),:payload,'bad')""",
                {"id": checksum_run.run_id, "payload": checksum_payload},
                "23514",
            ),
            (
                "immutable-update",
                "UPDATE classsync_scheduling.drafts SET title='modified'",
                {},
                "42501",
            ),
            ("immutable-delete", "DELETE FROM classsync_scheduling.solver_runs", {}, "42501"),
            ("immutable-truncate", "TRUNCATE classsync_scheduling.drafts", {}, "42501"),
        ):
            try:
                with transaction(owner) as db:
                    db.execute(text(statement), params)
            except DBAPIError as error:
                require(
                    error.orig.sqlstate == sqlstate, f"Wrong draft database constraint: {label}"
                )
                constraints.append(label)
            else:
                raise RuntimeError(f"Draft database constraint absent: {label}")
        with transaction(owner) as db:
            db.execute(
                text(f"REVOKE SELECT ON classsync_scheduling.drafts FROM {connection.runtime}")
            )
        try:
            must_fail(lambda: repository.get(draft.id), "persistence_unavailable")
        finally:
            with transaction(owner) as db:
                db.execute(
                    text(f"GRANT SELECT ON classsync_scheduling.drafts TO {connection.runtime}")
                )
        require(repository.get(draft.id) == draft, "Outage recovery changed snapshot")
        for state, revision in (("revoked", 2), ("active", 3)):
            with transaction(owner) as db:
                identity_context(db, tenant_id="tenant-a", uid="uid-admin")
                audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                db.execute(
                    text("""UPDATE classsync_identity.memberships
                    SET state=:state,revision=:revision
                    WHERE tenant_id='tenant-a' AND uid='uid-admin'"""),
                    {"state": state, "revision": revision},
                )
            if state == "revoked":
                must_fail(lambda: repository.get(draft.id), "membership_denied")
        require(repository.get(draft.id) == draft, "Membership recovery changed snapshot")
        with transaction(runtime) as db:
            for table in ("solver_runs", "drafts"):
                require(
                    db.scalar(text(f"SELECT count(*) FROM classsync_scheduling.{table}")) == 0,
                    "Pooled context leaked private drafts",
                )
        with transaction(owner) as db:
            before = db.scalar(text("SELECT count(*) FROM classsync_identity.memberships"))
            migrate(db, target="0005_academic_records", downgrade=True)
            require(
                db.scalar(text("SELECT count(*) FROM classsync_identity.memberships")) == before,
                "Draft schema downgrade changed identity",
            )
            migrate(db)
        return {
            "foundation": foundation,
            "solver_status": result.solver_status,
            "exact_snapshot_reconnect": True,
            "strict_key_replay_conflicts": True,
            "server_held_run_only": True,
            "invalid_solver_runs_denied": 4,
            "two_active_owner_isolation": True,
            "active_non_admin_denied": True,
            "wrong_tenant_project_denied": True,
            "observed_lock_waiters": waiting,
            "concurrent_exactly_one_create": True,
            "expired_run_denied": True,
            "checksum_consistent_corruption_denied": True,
            "database_negative_cases": constraints,
            "current_revocation": True,
            "actual_outage_recovery": True,
            "pooled_context_reset": True,
            "upgrade_downgrade_upgrade": True,
            "downgrade_preserves_draft_data": False,
            "service_cutover": False,
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
    write_new_evidence(args.output, qualify(args.bin, exercise))
    print("PostgreSQL draft repository qualification passed; owned cluster stopped")


if __name__ == "__main__":
    main()
