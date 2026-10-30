"""Synthetic atomic grant/audit and failure acceptance in a new owned PG cluster."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipState,
    VerifiedPrincipal,
    current_membership,
)
from classync_contracts.models import UserRole
from classync_persistence.database import postgres_engine, transaction
from classync_persistence.membership_changes import (
    MembershipRevisionConflict,
    audit_actor,
    change_membership_grants,
    change_membership_state,
)
from classync_persistence.memberships import PostgresMembershipLookup, identity_context
from sqlalchemy import event, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError, OperationalError

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import denied, engine_for, require
from scripts.postgres_revision_qualification import exercise as revision_exercise

ACTOR = VerifiedPrincipal(uid="uid-admin")  # Synthetic fixture, not an institutional identity.


def expect_unavailable(repository):
    try:
        current_membership(VerifiedPrincipal(uid="uid-a"), "tenant-a", repository)
    except MembershipAuthorizationError as error:
        require(error.code == "membership_unavailable"
                and isinstance(error.__cause__, OperationalError),
                "Connection failure did not propagate as typed unavailable")
    else:
        raise RuntimeError("Connection failure silently supplied membership authority")


def exercise(connection):
    revision = revision_exercise(connection)
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    absent_engine = None
    maintenance = "classsync_maintenance_" + uuid4().hex
    try:
        with transaction(owner) as session:
            session.execute(text(f"CREATE ROLE {maintenance} NOLOGIN NOSUPERUSER NOCREATEDB "
                                 "NOCREATEROLE NOREPLICATION NOBYPASSRLS"))
            session.execute(text(f"GRANT USAGE ON SCHEMA classsync_identity TO {maintenance}"))
            session.execute(text("GRANT SELECT, UPDATE ON classsync_identity.memberships "
                                 f"TO {maintenance}"))
            for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                require(not session.scalar(text(
                    "SELECT has_table_privilege(:role, "
                    "'classsync_identity.membership_audit', :priv)"
                ), {"role": maintenance, "priv": privilege}),
                        "Maintenance can write audit directly")

        def scope(session):
            session.execute(text(f"SET LOCAL ROLE {maintenance}"))
            identity_context(session, tenant_id="tenant-a", uid="uid-a")

        def state(session, expected, value, actor=ACTOR):
            return change_membership_state(session, tenant_id="tenant-a", uid="uid-a",
                                           expected_revision=expected, state=value, actor=actor)

        def grants(session, expected, roles):
            return change_membership_grants(session, tenant_id="tenant-a", uid="uid-a",
                                            expected_revision=expected, roles=frozenset(roles),
                                            actor=ACTOR)

        def audit_rows():
            with transaction(owner) as session:
                return session.execute(text("""
                    SELECT revision,actor_uid,database_session_user,old_snapshot,new_snapshot
                    FROM classsync_identity.membership_audit
                    WHERE tenant_id='tenant-a' AND subject_uid='uid-a' ORDER BY revision
                """)).all()

        require([row.revision for row in audit_rows()] == [1, 2, 3],
                "Concurrent loser or rollback produced an audit event")
        repository = PostgresMembershipLookup(runtime, firebase_project_id="synthetic-project")
        try:
            current_membership(VerifiedPrincipal(uid="uid-a"), "tenant-a", repository)
        except MembershipAuthorizationError as error:
            require(error.code == "membership_denied", "Inactive member returned wrong state")
        else:
            raise RuntimeError("Inactive database membership authorized a request")
        with transaction(owner) as session:
            scope(session)
            require(grants(session, 3, [UserRole.TEACHER]) == 4, "Grant removal failed")
        with transaction(owner) as session:
            scope(session)
            require(grants(session, 4, [UserRole.TEACHER, UserRole.STUDENT]) == 5,
                    "Grant restoration failed")
        before = audit_rows()
        require([row.revision for row in before] == list(range(1, 6)), "Audit revision gap")
        require(before[0].old_snapshot is None and before[3].actor_uid == ACTOR.uid
                and before[3].database_session_user == connection.owner
                and before[3].old_snapshot["roles"] == ["student", "teacher"]
                and before[3].new_snapshot["roles"] == ["teacher"],
                "Audit lost initial grant/actor/old-new grant provenance")
        try:
            with transaction(owner) as session:
                scope(session)
                grants(session, 4, [UserRole.ADMINISTRATOR])
        except MembershipRevisionConflict:
            pass
        else:
            raise RuntimeError("Stale grant writer succeeded")
        try:
            with transaction(owner) as session:
                scope(session)
                require(state(session, 5, MembershipState.ACTIVE) == 6, "Rollback candidate failed")
                raise ValueError("synthetic post-mutation failure")
        except ValueError:
            pass
        require(audit_rows() == before, "Rollback or stale grant changed audit history")
        # Force a genuine audit-insert failure after the membership UPDATE, then
        # prove PostgreSQL rolls the whole statement/transaction back.
        with transaction(owner) as session:
            session.execute(text("ALTER TABLE classsync_identity.membership_audit "
                                 "ADD CONSTRAINT synthetic_audit_fault "
                                 "CHECK (actor_uid <> 'synthetic-fault')"))
        try:
            try:
                with transaction(owner) as session:
                    scope(session)
                    state(session, 5, MembershipState.ACTIVE,
                          VerifiedPrincipal(uid="synthetic-fault"))
            except DBAPIError as error:
                require(error.orig.sqlstate == "23514", "Wrong audit-insert failure")
            else:
                raise RuntimeError("Failed audit insert still committed membership")
        finally:
            with transaction(owner) as session:
                session.execute(text("ALTER TABLE classsync_identity.membership_audit "
                                     "DROP CONSTRAINT synthetic_audit_fault"))
        require(audit_rows() == before, "Failed audit insertion changed history")
        unchanged = repository.lookup_current(tenant_id="tenant-a", uid="uid-a")
        require(unchanged is not None and unchanged.state == "inactive" and unchanged.revision == 5,
                "Failed audit insertion changed current authority")
        # Even a superuser's membership UPDATE cannot make the non-superuser
        # definer bypass FORCE RLS on audit when trusted target context is absent.
        try:
            with transaction(owner) as session:
                audit_actor(session, ACTOR)
                session.execute(text("UPDATE classsync_identity.memberships "
                                     "SET state='active',revision=revision+1 "
                                     "WHERE tenant_id='tenant-a' AND uid='uid-a'"))
        except DBAPIError as error:
            require(error.orig.sqlstate == "42501" and "row-level security" in str(error.orig),
                    "Missing target context did not enforce definer audit RLS")
        else:
            raise RuntimeError("Audit definer wrote without trusted tenant/subject context")
        try:
            with transaction(owner) as session:
                scope(session)
                session.execute(text("UPDATE classsync_identity.memberships "
                                     "SET state='active',revision=revision+1 "
                                     "WHERE tenant_id='tenant-a' AND uid='uid-a'"))
        except DBAPIError as error:
            require(error.orig.sqlstate == "42501", "Missing actor returned wrong failure")
        else:
            raise RuntimeError("Mutation without actor succeeded")
        with transaction(owner) as session:
            scope(session)
            require(state(session, 5, MembershipState.REVOKED) == 6, "Audited revocation failed")
        final = audit_rows()
        require([row.revision for row in final] == list(range(1, 7))
                and final[-1].new_snapshot["state"] == "revoked"
                and final[-1].old_snapshot["state"] == "inactive", "Revocation not atomic/audited")
        for statement in (
            "UPDATE classsync_identity.membership_audit SET actor_uid='forged'",
            "DELETE FROM classsync_identity.membership_audit",
            "TRUNCATE classsync_identity.membership_audit",
        ):
            denied(owner, statement)  # Even owner/superuser DML triggers must reject.
        for statement in (
            "SELECT * FROM classsync_identity.membership_audit",
            "SELECT classsync_identity.append_membership_audit()",
        ):
            denied(runtime, statement)
        for statement in (
            "INSERT INTO classsync_identity.membership_audit "
            "SELECT * FROM classsync_identity.membership_audit",
            "UPDATE classsync_identity.membership_audit SET actor_uid='forged'",
            "DELETE FROM classsync_identity.membership_audit",
            "TRUNCATE classsync_identity.membership_audit",
        ):
            try:
                with transaction(owner) as session:
                    scope(session)
                    session.execute(text(statement))
            except DBAPIError as error:
                require(error.orig.sqlstate == "42501", "Maintenance audit access failure differs")
            else:
                raise RuntimeError("Maintenance role could forge/edit/remove audit history")
        require(audit_rows() == final, "Audit tamper changed history")
        with transaction(owner) as session:
            require(not session.scalar(text("SELECT current_setting('classsync.actor_uid',true)")),
                    "Audit actor leaked across pooled transactions")

        parameters = connection.parameters() | {"dbname": "classsync_missing_" + uuid4().hex}
        url = URL.create("postgresql+psycopg", username=connection.runtime, host="127.0.0.1",
                         port=connection.port, database=parameters["dbname"])
        absent_engine = postgres_engine(url, connect_args=parameters)
        expect_unavailable(PostgresMembershipLookup(absent_engine,
                                                     firebase_project_id="synthetic-project"))

        killed = []

        def interrupt_lookup(sql_connection, cursor, statement, parameters, context, executemany):
            if killed or "FROM classsync_identity.memberships m" not in statement:
                return
            pid = sql_connection.connection.driver_connection.info.backend_pid
            with transaction(owner) as monitor:
                target = monitor.execute(text("SELECT usename,datname FROM pg_stat_activity "
                                              "WHERE pid=:pid"), {"pid": pid}).one()
                require(tuple(target) == (connection.runtime, "postgres"),
                        "Connection-loss target differs from owned runtime backend")
                require(monitor.scalar(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}),
                        "Synthetic connection loss did not terminate owned backend")
            killed.append(pid)

        event.listen(runtime, "before_cursor_execute", interrupt_lookup)
        try:
            expect_unavailable(repository)
        finally:
            event.remove(runtime, "before_cursor_execute", interrupt_lookup)
        require(len(killed) == 1, "Actual connection loss was not exercised")
        recovered = repository.lookup_current(tenant_id="tenant-a", uid="uid-a")
        require(recovered is not None and recovered.state == "revoked" and recovered.revision == 6,
                "Recovery did not read current authoritative revoked revision")
        return {"revision": revision, "atomic_grant_revocation_audit": True,
                "audit_failure_rolls_back_membership": True, "immutable_history": True,
                "definer_force_rls_without_context": True,
                "maintenance_cannot_forge_audit": True, "actor_pool_reset": True,
                "second_uid_administrator": True, "inactive_denied": True,
                "missing_database_unavailable": True, "connection_loss_unavailable": True,
                "recovered_current_revocation": True, "audit_revisions": list(range(1, 7))}
    finally:
        if absent_engine is not None:
            absent_engine.dispose()
        runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("Output must be a new file in an existing directory")
    evidence = qualify(args.bin, exercise)
    with args.output.open("x") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
