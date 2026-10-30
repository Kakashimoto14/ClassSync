"""Dump and restore only synthetic data inside a newly marked disposable cluster."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

from classync_persistence.database import postgres_engine, transaction
from classync_persistence.memberships import PostgresMembershipLookup
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import denied, engine_for, require
from scripts.postgres_identity_qualification import TABLES
from scripts.postgres_identity_qualification import exercise as identity_exercise


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def restore_name(value):
    if not re.fullmatch(r"classsync_restore_[a-f0-9]{32}", value):
        raise ValueError("Only a new generated disposable restore database is permitted")
    return value


def restored_engine(connection, database, *, bootstrap=False):
    database = restore_name(database)
    parameters = connection.parameters(bootstrap=bootstrap) | {"dbname": database}
    url = URL.create("postgresql+psycopg", username=parameters["user"], host="127.0.0.1",
                     port=connection.port, database=database)
    return postgres_engine(url, connect_args=parameters)


def fingerprint(engine, diagnostics=None):
    with transaction(engine) as session:
        data = {}
        for table in TABLES:
            # All keys are from the fixed internal schema list.
            data[table] = session.scalar(text(
                f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), '[]') "
                f"FROM classsync_identity.{table} t"
            ))
        definitions = {}
        queries = {
            "migration_revision": "SELECT version_num FROM public.alembic_version",
            "schema": """
                SELECT nspname, pg_get_userbyid(nspowner)
                FROM pg_namespace WHERE nspname='classsync_identity'
            """,
            "schema_acl": """
                SELECT n.nspname, pg_get_userbyid(a.grantor),
                    CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                    a.privilege_type,a.is_grantable
                FROM pg_namespace n
                CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
                WHERE n.nspname='classsync_identity' ORDER BY 1,2,3,4,5
            """,
            "columns": """
                SELECT table_name, column_name, ordinal_position, data_type, is_nullable,
                    column_default FROM information_schema.columns
                WHERE table_schema='classsync_identity' ORDER BY table_name, ordinal_position
            """,
            "constraints": """
                SELECT c.relname, k.conname, pg_get_constraintdef(k.oid)
                FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='classsync_identity' ORDER BY c.relname,k.conname
            """,
            "tables": """
                SELECT c.relname, pg_get_userbyid(c.relowner), c.relrowsecurity,
                    c.relforcerowsecurity
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='classsync_identity' AND c.relkind='r' ORDER BY c.relname
            """,
            "indexes": """
                SELECT tablename,indexname,indexdef FROM pg_indexes
                WHERE schemaname='classsync_identity' ORDER BY tablename,indexname
            """,
            "table_acl": """
                SELECT c.relname, pg_get_userbyid(a.grantor),
                    CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                    a.privilege_type,a.is_grantable
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
                WHERE n.nspname='classsync_identity' AND c.relkind='r' ORDER BY 1,2,3,4,5
            """,
            "functions": """
                SELECT p.proname,pg_get_functiondef(p.oid),pg_get_userbyid(p.proowner),
                    p.prosecdef,p.proconfig::text FROM pg_proc p
                JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='classsync_identity' ORDER BY p.proname
            """,
            "function_acl": """
                SELECT p.proname,pg_get_userbyid(a.grantor),
                    CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                    a.privilege_type,a.is_grantable
                FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
                WHERE n.nspname='classsync_identity' ORDER BY 1,2,3,4,5
            """,
            "triggers": """
                SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled
                FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='classsync_identity' AND NOT t.tgisinternal
                ORDER BY c.relname,t.tgname
            """,
            "policies": """
                SELECT tablename,policyname,permissive,roles::text,cmd,qual,with_check
                FROM pg_policies WHERE schemaname='classsync_identity'
                ORDER BY tablename,policyname
            """,
            "grants": """
                SELECT table_name,grantee,privilege_type,is_grantable
                FROM information_schema.table_privileges
                WHERE table_schema='classsync_identity'
                ORDER BY table_name,grantee,privilege_type,is_grantable
            """,
        }
        for name, query in queries.items():
            definitions[name] = [list(row) for row in session.execute(text(query))]
        if diagnostics is not None:
            diagnostics.update(data=data, catalog=definitions)
        return {"data": digest(data), "catalog": digest(definitions),
                "catalog_parts": {name: digest(rows) for name, rows in definitions.items()},
                "rows": {name: len(rows) for name, rows in data.items()}}


def exercise(connection):
    identity = identity_exercise(connection)
    require(connection.run_tool is not None, "Harness tool runner required")
    owner = engine_for(connection, bootstrap=True)
    restored_owner = restored_runtime = None
    target = restore_name("classsync_restore_" + uuid4().hex)
    archive = connection.root / ("identity-" + uuid4().hex + ".dump")
    require(not archive.exists(), "New archive path required")
    common = ["--host=127.0.0.1", f"--port={connection.port}", f"--username={connection.owner}",
              "--no-password"]
    try:
        source_details, restored_details = {}, {}
        before = fingerprint(owner, source_details)
        connection.run_tool("pg_dump.exe", *common, "--dbname=postgres", "--format=custom",
                            f"--file={archive}")
        archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
        # CREATE DATABASE without IF NOT EXISTS fails instead of reusing a target.
        # This one DDL requires autocommit and is restricted to a generated name.
        with owner.connect().execution_options(isolation_level="AUTOCOMMIT") as session:
            session.execute(text(f"CREATE DATABASE {target} TEMPLATE template0"))
        restored_owner = restored_engine(connection, target, bootstrap=True)
        with transaction(restored_owner) as session:
            require(session.scalar(text("SELECT current_database()")) == target,
                    "Restore target identity mismatch")
            # Standard dumps expect the empty template's public schema to exist;
            # pg_restore restores its ACL plus the Alembic version table.
            require(session.scalar(text("SELECT to_regnamespace('classsync_identity')")) is None,
                    "Restore target unexpectedly contains the source schema")
        connection.run_tool("pg_restore.exe", *common, f"--dbname={target}",
                            "--exit-on-error", "--single-transaction", archive)
        after = fingerprint(restored_owner, restored_details)
        if before != after:
            with (connection.root / "restore-comparison.json").open("x") as output:
                output.write(json.dumps({"source": source_details, "restored": restored_details},
                                        indent=2) + "\n")
        require(before == after, "Restored data/catalog/authority fingerprint mismatch")
        # Prove ACL canonicalization still detects a real extra runtime privilege.
        with transaction(restored_owner) as session:
            session.execute(text(
                f"GRANT INSERT ON classsync_identity.memberships TO {connection.runtime}"
            ))
        try:
            require(fingerprint(restored_owner) != after, "Privilege drift escaped fingerprint")
        finally:
            with transaction(restored_owner) as session:
                session.execute(text(
                    f"REVOKE INSERT ON classsync_identity.memberships FROM {connection.runtime}"
                ))
        require(fingerprint(restored_owner) == after, "Restored ACL did not return to baseline")
        try:
            with transaction(restored_owner) as session:
                session.execute(text("UPDATE classsync_identity.memberships SET state='active' "
                                     "WHERE tenant_id='tenant-a' AND uid='uid-a'"))
        except DBAPIError as error:
            require(error.orig.sqlstate == "23514",
                    "Restored revision guard returned wrong failure")
        else:
            raise RuntimeError("Restored database lost revision enforcement")
        for statement in (
            "UPDATE classsync_identity.membership_audit SET actor_uid='forged'",
            "DELETE FROM classsync_identity.membership_audit",
            "TRUNCATE classsync_identity.membership_audit",
        ):
            denied(restored_owner, statement)
        with transaction(restored_owner) as session:
            session.execute(text(f"REVOKE ALL ON DATABASE {target} FROM PUBLIC"))
            session.execute(text(f"GRANT CONNECT ON DATABASE {target} TO {connection.runtime}"))
        restored_runtime = restored_engine(connection, target)
        with transaction(restored_runtime) as session:
            require(session.scalar(text("SELECT count(*) FROM classsync_identity.memberships"))
                    == 0, "Restored runtime bypasses no-context RLS")
        repository = PostgresMembershipLookup(restored_runtime,
                                              firebase_project_id="synthetic-project")
        membership = repository.lookup_current(tenant_id="tenant-a", uid="uid-a")
        require(membership is not None and membership.state == "revoked"
                and membership.revision == 2 and membership.student_id == "student-a",
                "Restored membership authority differs")
        require(fingerprint(owner) == before, "Backup/restore modified source data/catalog")
        return {"identity": identity, "archive": str(archive), "archive_sha256": archive_hash,
                "source_database": "postgres", "restored_database": target,
                "source_fingerprint": before, "restored_fingerprint": after,
                "restored_rls_and_membership": True, "privilege_drift_detected": True,
                "restored_revision_guard": True,
                "restored_audit_immutable": True,
                "source_unchanged": True}
    finally:
        if restored_runtime is not None:
            restored_runtime.dispose()
        if restored_owner is not None:
            restored_owner.dispose()
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
