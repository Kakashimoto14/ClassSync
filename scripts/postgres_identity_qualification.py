"""Real identity migration/isolation checks on a new disposable cluster only."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from classync_contracts.identity import (
    MembershipAuthorizationError,
    VerifiedPrincipal,
    current_membership,
)
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import PostgresMembershipLookup, identity_context
from classync_persistence.schema import migrate
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import denied, engine_for, require

TABLES = ("tenants", "people", "students", "faculty", "memberships", "membership_audit")


def seed(session):
    session.execute(text("""
        INSERT INTO classsync_identity.tenants VALUES
            ('tenant-a', 'synthetic-project'), ('tenant-b', 'synthetic-project');
        INSERT INTO classsync_identity.people VALUES
            ('tenant-a', 'person-a'), ('tenant-a', 'person-other'), ('tenant-b', 'person-b');
        INSERT INTO classsync_identity.students VALUES
            ('tenant-a', 'student-a', 'person-a'), ('tenant-b', 'student-b', 'person-b');
        INSERT INTO classsync_identity.faculty VALUES
            ('tenant-a', 'faculty-a', 'person-a'), ('tenant-b', 'faculty-b', 'person-b')
    """))
    for tenant, uid, person, student, faculty, roles in (
        ("tenant-a", "uid-a", "person-a", "student-a", "faculty-a", ["student", "teacher"]),
        ("tenant-b", "uid-a", "person-b", "student-b", None, ["student"]),
        ("tenant-a", "uid-admin", "person-other", None, None, ["administrator"]),
    ):
        identity_context(session, tenant_id=tenant, uid=uid)
        audit_actor(session, VerifiedPrincipal(uid="synthetic-operator"))
        session.execute(text("""
            INSERT INTO classsync_identity.memberships VALUES
                (:tenant, :uid, :person, :student, :faculty, CAST(:roles AS text[]), 'active', 1)
        """), {"tenant": tenant, "uid": uid, "person": person, "student": student,
                "faculty": faculty, "roles": roles})


def constraint_cases(owner):
    base = dict(tenant="tenant-a", uid="invalid", person="person-a", student="student-a",
                faculty=None, roles=["student"], state="active", revision=1)
    cases = [
        ("duplicate identity", {"uid": "uid-a"}, "23505"),
        ("missing person", {"person": "absent", "student": None,
                            "roles": ["administrator"]}, "23503"),
        ("cross tenant student", {"student": "student-b"}, "23503"),
        ("mismatched person", {"person": "person-other"}, "23503"),
        ("unknown grant", {"roles": ["superadmin"]}, "23514"),
        ("empty grants", {"roles": []}, "23514"),
        ("duplicate grants", {"roles": ["student", "student"]}, "23514"),
        ("null grant", {"roles": [None]}, "23514"),
        ("invalid state", {"state": "approved"}, "23514"),
        ("nonpositive revision", {"revision": 0}, "23514"),
        ("missing student binding", {"student": None}, "23514"),
        ("missing faculty binding", {"roles": ["teacher"]}, "23514"),
        ("blank uid", {"uid": " "}, "23514"),
    ]
    for name, overrides, sqlstate in cases:
        try:
            with transaction(owner) as session:
                session.execute(text("""
                    INSERT INTO classsync_identity.memberships
                        (tenant_id, uid, person_id, student_id, faculty_id, roles, state, revision)
                    VALUES (:tenant, :uid, :person, :student, :faculty,
                            CAST(:roles AS text[]), :state, :revision)
                """), base | overrides)
        except DBAPIError as error:
            require(error.orig.sqlstate == sqlstate, f"Wrong constraint failure: {name}")
        else:
            raise RuntimeError(f"Invalid membership accepted: {name}")
    return [name for name, _, _ in cases]


def exercise(connection, *, target="head"):
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    migration_owner = "classsync_migrator_" + uuid4().hex
    try:
        # Verify bootstrap driver binding before any DDL, independently of psql.
        with transaction(owner) as session:
            observed = session.execute(text(
                "SELECT current_setting('data_directory'), current_user, inet_server_port()"
            )).one()
            require(Path(observed[0]).resolve() == (connection.root / "data").resolve()
                    and tuple(observed[1:]) == (connection.owner, connection.port),
                    "Identity exercise driver target mismatch")
            session.execute(text(
                f"CREATE ROLE {migration_owner} NOLOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ))
            session.execute(text(f"GRANT CREATE ON DATABASE postgres TO {migration_owner}"))
            session.execute(text(f"GRANT USAGE, CREATE ON SCHEMA public TO {migration_owner}"))
        # A failed caller transaction must roll back the entire Alembic upgrade.
        try:
            with transaction(owner) as session:
                session.execute(text(f"SET LOCAL ROLE {migration_owner}"))
                migrate(session, target=target)
                raise ValueError("synthetic migration rollback")
        except ValueError:
            pass
        with transaction(owner) as session:
            require(session.scalar(text("SELECT to_regnamespace('classsync_identity')")) is None,
                    "Failed migration transaction left schema behind")
            session.execute(text(f"SET LOCAL ROLE {migration_owner}"))
            migrate(session, target=target)
        with transaction(owner) as session:
            seed(session)
        with transaction(owner) as session:
            session.execute(text(f"SET LOCAL ROLE {migration_owner}"))
            migrate(session, target="base", downgrade=True)
            require(session.scalar(text("SELECT to_regnamespace('classsync_identity')")) is None,
                    "Downgrade did not remove only the identity schema")
            migrate(session, target=target)
        with transaction(owner) as session:
            seed(session)
            session.execute(text(
                f"GRANT USAGE ON SCHEMA classsync_identity TO {connection.runtime}"
            ))
            session.execute(text(
                "GRANT SELECT ON classsync_identity.memberships, classsync_identity.tenants "
                f"TO {connection.runtime}"
            ))
            policies = session.execute(text("""
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'classsync_identity' AND c.relkind = 'r'
            """)).all()
            require(len(policies) == len(TABLES) and all(row[1] and row[2] for row in policies),
                    "Missing enabled/FORCE RLS")
        rejected = constraint_cases(owner)
        # Non-superuser table owner is also subject to FORCE RLS on every table.
        with transaction(owner) as session:
            session.execute(text(f"SET LOCAL ROLE {migration_owner}"))
            for table in TABLES:
                require(session.scalar(text(f"SELECT count(*) FROM classsync_identity.{table}"))
                        == 0, f"No-context owner bypassed FORCE RLS: {table}")
            identity_context(session, tenant_id="tenant-a", uid="uid-a")
            for table in TABLES:
                key = "id" if table == "tenants" else "tenant_id"
                require(session.scalar(text(
                    f"SELECT count(*) FROM classsync_identity.{table} WHERE {key} = 'tenant-b'"
                )) == 0, f"Cross-tenant read leaked: {table}")
            require(session.scalar(text("SELECT count(*) FROM classsync_identity.memberships"))
                    == 1, "Scoped owner cannot read own membership")
            identity_context(session, tenant_id="tenant-a", uid="unrelated-uid")
            require(session.scalar(text("SELECT count(*) FROM classsync_identity.memberships"))
                    == 0, "Unrelated UID read membership")
        with transaction(runtime) as session:
            require(session.scalar(text("SELECT count(*) FROM classsync_identity.memberships"))
                    == 0, "Runtime inherited identity context")
        repository = PostgresMembershipLookup(runtime, firebase_project_id="synthetic-project")
        first = repository.lookup_current(tenant_id="tenant-a", uid="uid-a")
        require(first is not None and first.student_id == "student-a"
                and first.faculty_id == "faculty-a" and len(first.roles) == 2,
                "Current membership binding differs from committed records")
        other = repository.lookup_current(tenant_id="tenant-b", uid="uid-a")
        require(other is not None and other.student_id == "student-b", "Tenant aliasing")
        administrator = current_membership(
            VerifiedPrincipal(uid="uid-admin"), "tenant-a", repository
        )
        require({role.value for role in administrator.roles} == {"administrator"}
                and administrator.person_id == "person-other", "Administrator UID binding failed")
        require(repository.lookup_current(tenant_id="tenant-a", uid="unrelated") is None,
                "Unrelated UID got authority")
        require(repository.lookup_current(tenant_id="' OR TRUE--", uid="uid-a") is None,
                "Tenant parameter was not safely bound")
        wrong_project = PostgresMembershipLookup(runtime, firebase_project_id="other-project")
        require(wrong_project.lookup_current(tenant_id="tenant-a", uid="uid-a") is None,
                "Wrong verifier project got authority")
        with transaction(owner) as session:
            identity_context(session, tenant_id="tenant-a", uid="uid-a")
            audit_actor(session, VerifiedPrincipal(uid="synthetic-operator"))
            session.execute(text("""
                UPDATE classsync_identity.memberships SET state='revoked', revision=2
                WHERE tenant_id='tenant-a' AND uid='uid-a'
            """))
        changed = repository.lookup_current(tenant_id="tenant-a", uid="uid-a")
        require(changed is not None and changed.state == "revoked" and changed.revision == 2,
                "Repository cached stale membership")
        try:
            current_membership(VerifiedPrincipal(uid="uid-a"), "tenant-a", repository)
        except MembershipAuthorizationError as error:
            require(error.code == "membership_denied", "Revocation returned wrong state")
        else:
            raise RuntimeError("Revoked database membership authorized a request")
        with transaction(owner) as session:
            session.execute(text(
                f"REVOKE SELECT ON classsync_identity.tenants FROM {connection.runtime}"
            ))
        try:
            try:
                current_membership(VerifiedPrincipal(uid="uid-a"), "tenant-a", repository)
            except MembershipAuthorizationError as error:
                require(error.code == "membership_unavailable", "DB failure concealed as denial")
            else:
                raise RuntimeError("Database read failure fell back to authority")
        finally:
            with transaction(owner) as session:
                session.execute(text(
                    f"GRANT SELECT ON classsync_identity.tenants TO {connection.runtime}"
                ))
        for statement in (
            "UPDATE classsync_identity.memberships SET roles=ARRAY['administrator']",
            "DELETE FROM classsync_identity.memberships",
            "INSERT INTO classsync_identity.tenants VALUES ('forbidden','forbidden')",
        ):
            denied(runtime, statement)
        with transaction(runtime) as session:
            require(not session.scalar(text("SELECT current_setting('classsync.tenant_id', true)"))
                    and not session.scalar(text("SELECT current_setting('classsync.uid', true)")),
                    "Membership lookup context leaked after pooled transaction")
        return {
            "transactional_migration_rollback": True, "upgrade_downgrade_upgrade": True,
            "constraint_cases": rejected, "force_rls_all_tables": True,
            "tenant_uid_project_isolation": True, "record_binding": True,
            "fresh_revocation": True, "runtime_authority_writes_denied": True,
            "database_failure_unavailable": True,
            "second_uid_administrator": True,
            "pooled_context_reset": True,
        }
    finally:
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
