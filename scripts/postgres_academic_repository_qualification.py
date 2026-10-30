"""Full academic adapter qualification on new, synthetic disposable PostgreSQL only."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from classync_contracts.academic import CalendarWrite, PeriodCreate, RecordWrite
from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipState,
    VerifiedPrincipal,
)
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor, change_membership_state
from classync_persistence.memberships import identity_context
from classync_persistence.schema import migrate
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from scripts.postgres_web_session_qualification import write_new_evidence
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.academic.app.record_rules import AcademicError, checksum
from services.academic.tests.test_academic import complete
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.tests.test_calendar import configuration


class FixtureCalls:
    """Reuse existing synthetic fixture construction, not a product SQL/API shim."""

    def __init__(self, repository):
        self.repository = repository

    def create_period(self, body, scope, owner):
        require(
            (scope, owner) == ("sandbox", "development-academic-sandbox"),
            "Only existing synthetic fixture calls accepted",
        )
        return self.repository.create_period(body)

    def save(self, scope, owner, period, kind, identity, body):
        require(
            (scope, owner) == ("sandbox", "development-academic-sandbox"),
            "Only existing synthetic fixture calls accepted",
        )
        return self.repository.save(period, kind, identity, body)


def must_fail(operation, code):
    try:
        operation()
    except (AcademicError, MembershipAuthorizationError) as error:
        require(error.code == code, f"Wrong academic negative-path result: {error.code}")
    else:
        raise RuntimeError("Academic negative path unexpectedly succeeded")


def exercise(connection):
    foundation = identity_exercise(connection)
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    principal = VerifiedPrincipal(uid="uid-admin")

    def store(uid="uid-admin", tenant="tenant-a", project="synthetic-project"):
        return PostgresAcademicRepository(
            runtime,
            tenant_id=tenant,
            firebase_project_id=project,
            principal=VerifiedPrincipal(uid=uid),
        )

    repository = store()
    try:
        with transaction(owner) as db:
            db.execute(text(f"GRANT USAGE ON SCHEMA classsync_academic TO {connection.runtime}"))
            db.execute(
                text(
                    "GRANT SELECT,INSERT ON classsync_academic.period_metadata "
                    f"TO {connection.runtime}"
                )
            )
            db.execute(
                text(
                    "GRANT UPDATE(revision) ON classsync_academic.period_metadata "
                    f"TO {connection.runtime}"
                )
            )
            for table in ("records", "record_references", "calendars"):
                db.execute(
                    text(
                        f"GRANT SELECT,INSERT,UPDATE ON classsync_academic.{table} "
                        f"TO {connection.runtime}"
                    )
                )
            db.execute(
                text(
                    f"GRANT DELETE ON classsync_academic.record_references TO {connection.runtime}"
                )
            )
            identity_context(db, tenant_id="tenant-a", uid="uid-a")
            change_membership_state(
                db,
                tenant_id="tenant-a",
                uid="uid-a",
                expected_revision=2,
                state=MembershipState.ACTIVE,
                actor=principal,
            )
            identity_context(db, tenant_id="tenant-a", uid="uid-admin-other")
            audit_actor(db, principal)
            db.execute(
                text("""
                INSERT INTO classsync_identity.memberships VALUES
                  ('tenant-a','uid-admin-other','person-other',NULL,NULL,
                   ARRAY['administrator'],'active',1)
            """)
            )
        original = complete(FixtureCalls(repository))
        pid = original.period.id
        require(
            {entry.record.kind for entry in original.records}
            == {
                "programs",
                "subjects",
                "sections",
                "faculty",
                "resources",
                "offerings",
                "constraints",
            },
            "Not all academic record kinds persisted",
        )
        ready = academic_readiness(original)
        require(
            ready.ready and len(ready.inputs.offerings) == 4,
            "Persisted academic snapshot no longer satisfies existing readiness contract",
        )
        runtime.dispose()
        require(
            store().snapshot(pid) == original, "Snapshot/revision lost across physical reconnect"
        )
        other = store("uid-admin-other")
        private = other.create_period(
            PeriodCreate(
                title="Other synthetic owner",
                include_cdm_catalog=False,
                calendar=configuration().calendar,
            )
        )
        require(
            len(private.records) == 1
            and private.records[0].record.kind == "constraints"
            and private.period.revision == 2
            and private.period.calendar == configuration().calendar,
            "Empty catalog/initial calendar/default constraints parity failed",
        )
        provisional = [
            entry.record
            for entry in original.records
            if entry.record.kind == "resources" and entry.record.id.startswith("cdm-")
        ]
        require(
            len(provisional) == 59 and all(room.capacity is None for room in provisional),
            "Provisional catalog was omitted or given invented capacity",
        )
        require(
            len(other.periods()) == 1 and len(repository.periods()) == 1,
            "Two active administrators leaked period lists",
        )
        must_fail(lambda: other.snapshot(pid), "period_not_found")
        must_fail(lambda: repository.snapshot(private.period.id), "period_not_found")
        for denied in (
            store("uid-a"),
            store("missing"),
            store(tenant="tenant-b"),
            store(project="wrong-project"),
        ):
            must_fail(denied.periods, "membership_denied")
            must_fail(
                lambda denied=denied: denied.create_period(PeriodCreate(title="Denied")),
                "membership_denied",
            )
        bad = RecordWrite.model_validate(
            {
                "expected_revision": 0,
                "record": {
                    "kind": "subjects",
                    "id": "bad",
                    "code": "BAD",
                    "name": "Synthetic bad reference",
                    "program_ids": ["missing"],
                },
            }
        )
        must_fail(lambda: repository.save(pid, "subjects", "bad", bad), "missing_reference")
        require(repository.snapshot(pid) == original, "Failed reference write changed snapshot")
        subject = next(entry for entry in original.records if entry.record.id == "subject-a")
        duplicate = RecordWrite(
            expected_revision=0, record=subject.record.model_copy(update={"id": "dup"})
        )
        must_fail(lambda: repository.save(pid, "subjects", "dup", duplicate), "academic_integrity")
        stale = RecordWrite(expected_revision=0, record=subject.record)
        must_fail(
            lambda: repository.save(pid, "subjects", "subject-a", stale),
            "academic_version_conflict",
        )
        must_fail(lambda: repository.save(pid, "subjects", "wrong", stale), "record_identity")
        cdm = next(entry for entry in original.records if entry.record.id.startswith("cdm-"))
        changed_cdm = RecordWrite(
            expected_revision=cdm.revision,
            record=cdm.record.model_copy(update={"name": "Invented rename"}),
        )
        must_fail(
            lambda: repository.save(pid, "resources", cdm.record.id, changed_cdm), "cdm_identity"
        )
        calendar = configuration().calendar
        dated = repository.save_calendar(
            pid, CalendarWrite(expected_revision=original.period.revision, calendar=calendar)
        )
        require(
            dated.records == original.records
            and dated.period.revision == original.period.revision + 1,
            "Calendar edit overwrote records or revision",
        )
        must_fail(
            lambda: repository.save_calendar(
                pid, CalendarWrite(expected_revision=original.period.revision, calendar=calendar)
            ),
            "calendar_version_conflict",
        )
        forged = calendar.model_copy(update={"published_version": "forged"})
        must_fail(
            lambda: repository.create_period(PeriodCreate(title="Forged", calendar=forged)),
            "publication_version",
        )
        faculty = RecordWrite.model_validate(
            {
                "expected_revision": 0,
                "record": {
                    "kind": "faculty",
                    "id": "identity-a",
                    "name": "Synthetic",
                    "institutional_id": "SYN-1",
                },
            }
        )
        repository.save(pid, "faculty", "identity-a", faculty)
        duplicate_faculty = faculty.model_copy(
            update={
                "record": faculty.record.model_copy(
                    update={"id": "identity-b", "institutional_id": " syn-1 "}
                )
            }
        )
        must_fail(
            lambda: repository.save(pid, "faculty", "identity-b", duplicate_faculty),
            "faculty_identity_duplicate",
        )
        # Observe two actual lock waiters, then release the period lock. One CAS wins.
        before_competition = repository.snapshot(pid)
        barrier = Barrier(3)

        def edit(label):
            barrier.wait(timeout=5)
            body = RecordWrite(
                expected_revision=subject.revision,
                record=subject.record.model_copy(update={"name": label}),
            )
            try:
                return store().save(pid, "subjects", "subject-a", body).period.revision
            except AcademicError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as workers:
            with transaction(runtime) as held:
                repository.context.context(held, principal)
                held.execute(
                    text("""
                    SELECT id FROM classsync_academic.period_metadata
                    WHERE tenant_id='tenant-a' AND owner_uid='uid-admin' AND id=:id FOR UPDATE
                """),
                    {"id": pid},
                )
                futures = [workers.submit(edit, value) for value in ("Synthetic A", "Synthetic B")]
                barrier.wait(timeout=5)
                deadline = time.monotonic() + 5
                waiting = 0
                while time.monotonic() < deadline:
                    with transaction(owner) as observed:
                        waiting = observed.scalar(
                            text("""
                            SELECT count(*) FROM pg_stat_activity
                            WHERE usename=:role AND wait_event_type='Lock'
                        """),
                            {"role": connection.runtime},
                        )
                    if waiting >= 2:
                        break
                    time.sleep(0.05)
                require(waiting >= 2, "Did not observe competing period lock waiters")
            results = [future.result(timeout=10) for future in futures]
        require(
            sum(isinstance(value, int) for value in results) == 1
            and results.count("academic_version_conflict") == 1,
            "Competing academic edits silently overwrote each other",
        )
        committed = repository.snapshot(pid)
        winner = next(entry for entry in committed.records if entry.record.id == "subject-a")
        require(
            committed.period.revision == before_competition.period.revision + 1
            and winner.revision == subject.revision + 1
            and winner.record.name in {"Synthetic A", "Synthetic B"},
            "Competing writes incremented incorrectly or stored a non-winner",
        )
        # Corrupt but checksum-consistent stored values must surface integrity errors,
        # never model defaults, partial success or substituted fixtures.
        for table, payload, code in (
            (
                "records",
                json.dumps({"id": "subject-a", "kind": "subjects"}),
                "academic_snapshot_integrity",
            ),
            ("calendars", "{}", "academic_snapshot_integrity"),
        ):
            where = "tenant_id='tenant-a' AND owner_uid='uid-admin' AND period_id=:period"
            if table == "records":
                where += " AND kind='subjects' AND id='subject-a'"
            with transaction(owner) as db:
                stored = (
                    db.execute(
                        text(
                            f"SELECT payload,checksum FROM classsync_academic.{table} WHERE {where}"
                        ),
                        {"period": pid},
                    )
                    .mappings()
                    .one()
                )
                db.execute(
                    text(
                        f"UPDATE classsync_academic.{table} "
                        f"SET payload=:payload,checksum=:checksum WHERE {where}"
                    ),
                    {"period": pid, "payload": payload, "checksum": checksum(payload)},
                )
            try:
                must_fail(lambda: repository.snapshot(pid), code)
            finally:
                with transaction(owner) as db:
                    db.execute(
                        text(
                            f"UPDATE classsync_academic.{table} "
                            f"SET payload=:payload,checksum=:checksum WHERE {where}"
                        ),
                        {"period": pid, **stored},
                    )
        constraint_cases = []
        current = winner.record.model_dump(mode="json")
        for label, payload, digest in (
            ("checksum", json.dumps(current), "0" * 64),
            ("payload-id", json.dumps({**current, "id": "wrong"}), None),
            (
                "missing-payload-id",
                json.dumps({key: value for key, value in current.items() if key != "id"}),
                None,
            ),
        ):
            try:
                with transaction(owner) as db:
                    db.execute(
                        text("""
                        UPDATE classsync_academic.records SET payload=:payload,checksum=:checksum
                        WHERE tenant_id='tenant-a' AND owner_uid='uid-admin' AND period_id=:period
                            AND kind='subjects' AND id='subject-a'
                    """),
                        {
                            "period": pid,
                            "payload": payload,
                            "checksum": digest or checksum(payload),
                        },
                    )
            except DBAPIError as error:
                require(error.orig.sqlstate == "23514", "Unexpected new-table CHECK result")
            else:
                raise RuntimeError("Invalid academic payload/checksum accepted")
            constraint_cases.append(label)
        try:
            with transaction(owner) as db:
                db.execute(
                    text("""
                    INSERT INTO classsync_academic.record_references VALUES
                        ('tenant-a','uid-admin',:period,'subjects','subject-a','programs','absent')
                """),
                    {"period": pid},
                )
        except DBAPIError as error:
            require(error.orig.sqlstate == "23503", "Reference FK not enforced")
        else:
            raise RuntimeError("Missing academic target accepted")
        require(repository.snapshot(pid) == committed, "Integrity exercises changed committed data")
        for state, revision in ((MembershipState.REVOKED, 1), (MembershipState.ACTIVE, 2)):
            with transaction(owner) as db:
                identity_context(db, tenant_id="tenant-a", uid=principal.uid)
                change_membership_state(
                    db,
                    tenant_id="tenant-a",
                    uid=principal.uid,
                    expected_revision=revision,
                    state=state,
                    actor=principal,
                )
            if state == MembershipState.REVOKED:
                must_fail(lambda: repository.snapshot(pid), "membership_denied")
        require(
            repository.snapshot(pid) == committed, "Revocation/reactivation changed academic data"
        )
        with transaction(owner) as db:
            db.execute(
                text(f"REVOKE SELECT ON classsync_academic.records FROM {connection.runtime}")
            )
        try:
            must_fail(lambda: repository.snapshot(pid), "academic_storage_unavailable")
        finally:
            with transaction(owner) as db:
                db.execute(
                    text(f"GRANT SELECT ON classsync_academic.records TO {connection.runtime}")
                )
        require(repository.snapshot(pid) == committed, "Outage recovery substituted or lost data")
        with transaction(runtime) as db:
            for table in ("records", "record_references", "calendars", "period_metadata"):
                require(
                    db.scalar(text(f"SELECT count(*) FROM classsync_academic.{table}")) == 0,
                    "Pooled context leaked private academic data",
                )
        with transaction(owner) as db:
            before = db.scalar(text("SELECT count(*) FROM classsync_identity.memberships"))
            migrate(db, target="0004_academic_period_metadata", downgrade=True)
            require(
                db.scalar(text("SELECT count(*) FROM classsync_identity.memberships")) == before,
                "Academic schema downgrade changed identity",
            )
            migrate(db)
        return {
            "foundation": foundation,
            "all_seven_record_kinds": True,
            "ready_offerings": 4,
            "snapshot_reconnect": True,
            "two_active_owner_isolation": True,
            "negative_validation_rollback": True,
            "malformed_record_calendar_integrity": True,
            "new_table_constraint_cases": constraint_cases + ["reference-fk"],
            "cdm_provenance_preserved": True,
            "calendar_cas_and_publication_guard": True,
            "faculty_identity_unique": True,
            "observed_competing_lock_waiters": waiting,
            "one_revision_winner_one_conflict": True,
            "current_revocation": True,
            "actual_outage_recovery": True,
            "pooled_context_reset": True,
            "upgrade_downgrade_upgrade": True,
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
    print("Full academic repository qualification passed; owned PostgreSQL stopped")


if __name__ == "__main__":
    main()
