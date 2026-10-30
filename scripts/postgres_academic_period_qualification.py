"""Actual academic metadata checks on a new marked PostgreSQL cluster only."""

import argparse
from functools import partial
from pathlib import Path

from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipState,
    VerifiedPrincipal,
)
from classync_persistence.academic_periods import PostgresAcademicPeriods
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


def exercise(connection):
    foundation = identity_exercise(connection)
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    admin = VerifiedPrincipal(uid="uid-admin")
    other_admin = VerifiedPrincipal(uid="uid-admin-other")
    try:
        with transaction(owner) as session:
            # This historical slice intentionally qualifies revision0004's metadata-only API.
            # Later revisions implement writes needed by the complete academic repository.
            migrate(session, target="0004_academic_period_metadata", downgrade=True)
            session.execute(text(
                f"GRANT USAGE ON SCHEMA classsync_academic TO {connection.runtime}"
            ))
            session.execute(text("GRANT SELECT, INSERT ON classsync_academic.period_metadata "
                                 f"TO {connection.runtime}"))
            identity_context(session, tenant_id="tenant-a", uid=other_admin.uid)
            audit_actor(session, VerifiedPrincipal(uid="synthetic-operator"))
            session.execute(text("""
                INSERT INTO classsync_identity.memberships VALUES
                    ('tenant-a','uid-admin-other','person-other',NULL,NULL,
                     ARRAY['administrator'],'active',1)
            """))
            original_memberships = session.scalar(text(
                "SELECT count(*) FROM classsync_identity.memberships"
            ))
        store = PostgresAcademicPeriods(runtime, tenant_id="tenant-a",
                                       firebase_project_id="synthetic-project")
        require(store.list_for(admin) == [], "Authorized empty metadata must be distinguishable")
        title = "Synthetic period '); DROP TABLE imaginary; --"
        created = store.create_for(admin, title=title)
        other_created = store.create_for(other_admin, title="Other owner's synthetic period")
        require(store.list_for(other_admin) == [other_created],
                "Other admin read first owner's data")
        require(created.title == title and created.revision == 1 and created.calendar is None,
                "Committed metadata contract mismatch")
        runtime.dispose()  # Fresh physical connections and adapter; persisted, not cached.
        require(store.list_for(admin) == [created], "Metadata lost after connection restart")
        with transaction(owner) as session:
            table_owner = session.scalar(text("""
                SELECT pg_get_userbyid(relowner) FROM pg_class
                WHERE oid='classsync_academic.period_metadata'::regclass
            """))
            session.execute(text("SELECT set_config('role', :role, true)"), {"role": table_owner})
            require(session.scalar(text("SELECT count(*) FROM classsync_academic.period_metadata"))
                    == 0, "Table owner bypassed FORCE RLS without context")
            store.context(session, admin)
            require(session.scalar(text("SELECT count(*) FROM classsync_academic.period_metadata"))
                    == 1, "Scoped table owner cannot read metadata")
            result = session.execute(text(
                "UPDATE classsync_academic.period_metadata SET title='Forbidden mutation'"
            ))
            require(result.rowcount == 0, "Unimplemented update authorized by RLS")
        denied_cases = []
        for name, repository, principal in (
            ("student-teacher", store, VerifiedPrincipal(uid="uid-a")),
            ("missing-uid", store, VerifiedPrincipal(uid="missing")),
            ("wrong-tenant", PostgresAcademicPeriods(runtime, tenant_id="tenant-b",
                firebase_project_id="synthetic-project"), admin),
            ("wrong-project", PostgresAcademicPeriods(runtime, tenant_id="tenant-a",
                firebase_project_id="wrong-project"), admin),
        ):
            for operation in (partial(repository.list_for, principal),
                              partial(repository.create_for, principal, title="Forbidden")):
                try:
                    operation()
                except MembershipAuthorizationError as error:
                    require(error.code == "membership_denied", "Wrong typed denial")
                else:
                    raise RuntimeError("Unauthorized metadata operation succeeded")
            denied_cases.append(name)
        with transaction(runtime) as session:
            require(session.scalar(text("SELECT count(*) FROM classsync_academic.period_metadata"))
                    == 0, "No-context direct query leaked metadata")
            store.context(session, admin)
            require(session.scalar(text("SELECT count(*) FROM classsync_academic.period_metadata"))
                    == 1, "Current administrator cannot read owned metadata")
            require(session.scalar(text("SELECT current_setting('classsync.project_id', true)"))
                    == "synthetic-project", "Project context absent")
        with transaction(runtime) as session:
            require(not session.scalar(text(
                "SELECT current_setting('classsync.project_id', true)"
            )),
                    "Project context leaked across pooled transactions")
        # Direct SQL cannot bypass owner/role predicates even with an otherwise valid admin context.
        try:
            with transaction(runtime) as session:
                store.context(session, admin)
                session.execute(text("""
                    INSERT INTO classsync_academic.period_metadata (tenant_id,owner_uid,id,title)
                    VALUES ('tenant-a','uid-admin-other','forbidden','Forbidden')
                """))
        except DBAPIError as error:
            require(error.orig.sqlstate == "42501", "Expected RLS denial")
        else:
            raise RuntimeError("Cross-owner direct insertion succeeded")
        # Failed caller transaction never commits, including a successful INSERT before the error.
        try:
            with transaction(runtime) as session:
                store.context(session, admin)
                session.execute(text("""
                    INSERT INTO classsync_academic.period_metadata (tenant_id,owner_uid,id,title)
                    VALUES ('tenant-a','uid-admin','rolled-back','Rollback')
                """))
                raise RuntimeError("synthetic rollback")
        except RuntimeError as error:
            require(str(error) == "synthetic rollback", "Unexpected rollback failure")
        require(store.list_for(admin) == [created], "Failed transaction left metadata")
        constraints = []
        for name, values, expected in (
            ("duplicate", {"id": created.id, "title": "Duplicate", "revision": 1}, "23505"),
            ("blank-title", {"id": "blank", "title": " ", "revision": 1}, "23514"),
            ("long-title", {"id": "long", "title": "x" * 161, "revision": 1}, "23514"),
            ("bad-revision", {"id": "revision", "title": "Revision", "revision": 0}, "23514"),
            ("blank-id", {"id": " ", "title": "Blank ID", "revision": 1}, "23514"),
            ("missing-owner", {"id": "missing-owner", "title": "Missing owner", "revision": 1,
                               "owner": "missing-member"}, "23503"),
        ):
            try:
                with transaction(owner) as session:
                    session.execute(text("""
                        INSERT INTO classsync_academic.period_metadata
                            (tenant_id,owner_uid,id,title,revision)
                        VALUES ('tenant-a',:owner,:id,:title,:revision)
                    """), {"owner": "uid-admin", **values})
            except DBAPIError as error:
                require(error.orig.sqlstate == expected, "Unexpected constraint result")
            else:
                raise RuntimeError("Invalid academic metadata accepted")
            constraints.append(name)
        for state, revision in ((MembershipState.REVOKED, 1), (MembershipState.ACTIVE, 2)):
            with transaction(owner) as session:
                identity_context(session, tenant_id="tenant-a", uid=admin.uid)
                change_membership_state(session, tenant_id="tenant-a", uid=admin.uid,
                                        expected_revision=revision, state=state,
                                        actor=VerifiedPrincipal(uid="synthetic-operator"))
            if state == MembershipState.REVOKED:
                try:
                    store.list_for(admin)
                except MembershipAuthorizationError:
                    pass
                else:
                    raise RuntimeError("Revoked administrator read metadata")
        require(store.list_for(admin) == [created], "Reactivation lost metadata")
        with transaction(owner) as session:
            session.execute(text("REVOKE SELECT ON classsync_academic.period_metadata "
                                 f"FROM {connection.runtime}"))
        try:
            store.list_for(admin)
        except DBAPIError as error:
            require(error.orig.sqlstate == "42501", "Unexpected permission outage")
        else:
            raise RuntimeError("Database outage silently returned sample or empty data")
        finally:
            with transaction(owner) as session:
                session.execute(text("GRANT SELECT ON classsync_academic.period_metadata "
                                     f"TO {connection.runtime}"))
        require(store.list_for(admin) == [created], "Database recovery failed")
        with transaction(owner) as session:
            migrate(session, target="0003_membership_audit", downgrade=True)
            require(session.scalar(text("SELECT to_regnamespace('classsync_academic')")) is None,
                    "Academic downgrade left schema")
            require(session.scalar(text("SELECT count(*) FROM classsync_identity.memberships"))
                    == original_memberships, "Academic downgrade altered identity rows")
            migrate(session)
        return {"foundation": foundation, "create_list_connection_restart": True,
                "typed_denied_cases": denied_cases, "direct_sql_rls": True,
                "rollback_and_constraints": constraints, "revocation_reactivation": True,
                "database_outage_recovery": True, "upgrade_downgrade_upgrade": True,
                "complete_academic_repository": False, "production_acceptance": False}
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
    print("Academic metadata qualification passed; owned PostgreSQL stopped")


if __name__ == "__main__":
    main()
