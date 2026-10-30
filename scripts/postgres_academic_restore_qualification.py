"""Rehearse academic backup/restore only inside a new marked synthetic PG cluster."""

import argparse
import hashlib
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from classync_contracts.academic import CalendarWrite, PeriodCreate, RecordWrite
from classync_contracts.identity import MembershipErrorCode, MembershipState, VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor, change_membership_state
from classync_persistence.memberships import identity_context
from classync_persistence.schema import migrate
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_academic_repository_qualification import FixtureCalls, must_fail
from scripts.postgres_disposable import checked_root, qualify
from scripts.postgres_driver_qualification import denied, engine_for, require
from scripts.postgres_identity_qualification import TABLES, seed
from scripts.postgres_restore_qualification import digest, restore_name, restored_engine
from scripts.postgres_web_session_qualification import write_new_evidence
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.academic.tests.test_academic import complete
from services.scheduling.tests.test_calendar import configuration

MIGRATION = "0005_academic_records"
SCHEMAS = "('classsync_identity','classsync_academic')"
ACADEMIC_TABLES = ("period_metadata", "records", "record_references", "calendars")
DATA_TABLES = tuple(f"classsync_identity.{name}" for name in TABLES) + tuple(
    f"classsync_academic.{name}" for name in ACADEMIC_TABLES
)


def owned_root(connection):
    root = checked_root(connection.root, Path(tempfile.gettempdir()))
    require(
        re.fullmatch(r"classsync_qa_[a-f0-9]{32}", connection.owner)
        and re.fullmatch(r"classsync_runtime_[a-f0-9]{32}", connection.runtime)
        and type(connection.port) is int
        and 1024 < connection.port < 65536
        and connection.port != 5432,
        "Generated local cluster identities and nondefault port required",
    )
    return root


def check_binding(connection, observed, database):
    root = owned_root(connection)
    require(database == "postgres" or restore_name(database) == database,
            "Invalid source/restore database")
    require(
        Path(observed["data_directory"]).resolve() == (root / "data").resolve()
        and observed["database"] == database
        and observed["user"] == connection.owner
        and observed["port"] == connection.port,
        "Academic restore cluster/database binding mismatch",
    )


def check_empty_target(namespaces, public_objects):
    require(not namespaces and public_objects == 0,
            "Restore target must be newly created and empty")


def create_target(owner, target):
    target = restore_name(target)
    # Deliberately no IF NOT EXISTS: a collision is an error, never permission to reuse.
    with owner.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
        db.execute(text(f"CREATE DATABASE {target} TEMPLATE template0"))


def restore_toc(value):
    """template0 already has public; omit exactly that CREATE, not its objects/ACLs."""
    lines = value.splitlines()
    public_schema = re.compile(r"^\d+; \d+ \d+ SCHEMA - public \S+$")
    matches = [line for line in lines if public_schema.fullmatch(line)]
    require(len(matches) == 1, "Expected exactly one public schema archive entry")
    return "\n".join(line for line in lines if line != matches[0]) + "\n"


def check_source_scope(namespaces, public_tables):
    require(set(namespaces) == {"public", "classsync_identity", "classsync_academic"}
            and list(public_tables) == ["alembic_version"],
            "Academic backup source contains unexpected namespaces or public tables")


def archive_hash(connection, archive, expected=None):
    root = owned_root(connection)
    require(
        archive.parent.resolve() == root
        and not archive.is_symlink()
        and re.fullmatch(r"academic-[a-f0-9]{32}\.dump", archive.name)
        and archive.is_file()
        and archive.stat().st_size > 0
        and archive.resolve().parent == root,
        "Only the owned generated academic archive is accepted",
    )
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    require(expected is None or actual == expected, "Academic backup archive changed")
    return actual


def check_connection(connection, engine, database):
    with transaction(engine) as db:
        observed = db.execute(text("""
            SELECT current_setting('data_directory') AS data_directory,
                current_database() AS database, current_user AS user, inet_server_port() AS port
        """)).mappings().one()
        check_binding(connection, observed, database)


def catalog_queries():
    """Canonical identities exclude database-local OIDs and ACL array ordering."""
    return {
        "migration": "SELECT version_num FROM public.alembic_version ORDER BY version_num",
        "schemas": f"""
            SELECT nspname,pg_get_userbyid(nspowner) FROM pg_namespace
            WHERE nspname IN {SCHEMAS} ORDER BY 1
        """,
        "schema_acl": f"""
            SELECT n.nspname,pg_get_userbyid(a.grantor),
                CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                a.privilege_type,a.is_grantable FROM pg_namespace n
            CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a
            WHERE n.nspname IN {SCHEMAS} ORDER BY 1,2,3,4,5
        """,
        "columns": f"""
            SELECT table_schema,table_name,column_name,ordinal_position,data_type,
                udt_schema,udt_name,is_nullable,column_default,collation_name,
                is_identity,identity_generation,is_generated,generation_expression
            FROM information_schema.columns WHERE table_schema IN {SCHEMAS}
            ORDER BY 1,2,4
        """,
        "constraints": f"""
            SELECT n.nspname,c.relname,k.conname,pg_get_constraintdef(k.oid),k.convalidated
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN {SCHEMAS} ORDER BY 1,2,3
        """,
        "tables": f"""
            SELECT n.nspname,c.relname,pg_get_userbyid(c.relowner),c.relrowsecurity,
                c.relforcerowsecurity,c.reloptions::text
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN {SCHEMAS} AND c.relkind='r' ORDER BY 1,2
        """,
        "indexes": f"""
            SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes
            WHERE schemaname IN {SCHEMAS} ORDER BY 1,2,3
        """,
        "table_acl": f"""
            SELECT n.nspname,c.relname,pg_get_userbyid(a.grantor),
                CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                a.privilege_type,a.is_grantable
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
            WHERE n.nspname IN {SCHEMAS} AND c.relkind='r' ORDER BY 1,2,3,4,5,6
        """,
        "column_acl": f"""
            SELECT n.nspname,c.relname,d.attname,pg_get_userbyid(a.grantor),
                CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                a.privilege_type,a.is_grantable
            FROM pg_attribute d JOIN pg_class c ON c.oid=d.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN LATERAL aclexplode(d.attacl) a
            WHERE n.nspname IN {SCHEMAS} ORDER BY 1,2,3,4,5,6,7
        """,
        "functions": f"""
            SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),
                pg_get_functiondef(p.oid),pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig::text
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname IN {SCHEMAS} ORDER BY 1,2,3
        """,
        "function_acl": f"""
            SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),
                pg_get_userbyid(a.grantor),
                CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                a.privilege_type,a.is_grantable
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
            WHERE n.nspname IN {SCHEMAS} ORDER BY 1,2,3,4,5,6,7
        """,
        "triggers": f"""
            SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN {SCHEMAS} AND NOT t.tgisinternal ORDER BY 1,2,3
        """,
        "policies": f"""
            SELECT schemaname,tablename,policyname,permissive,roles::text,cmd,qual,with_check
            FROM pg_policies WHERE schemaname IN {SCHEMAS} ORDER BY 1,2,3
        """,
        "default_acl": f"""
            SELECT pg_get_userbyid(d.defaclrole),coalesce(n.nspname,'*'),d.defaclobjtype,
                pg_get_userbyid(a.grantor),
                CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END,
                a.privilege_type,a.is_grantable
            FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
            CROSS JOIN LATERAL aclexplode(d.defaclacl) a
            WHERE n.nspname IN {SCHEMAS} OR d.defaclnamespace=0 ORDER BY 1,2,3,4,5,6,7
        """,
    }


def summarize(data, catalog):
    require(set(data) == set(DATA_TABLES), "Incomplete academic/identity data fingerprint")
    require(set(catalog) == set(catalog_queries()), "Incomplete authority/catalog fingerprint")
    require(catalog["migration"] == [[MIGRATION]], "Academic restore migration target drift")
    require(
        {f"{row[0]}.{row[1]}" for row in catalog["tables"]} == set(DATA_TABLES)
        and all(row[3] and row[4] for row in catalog["tables"]),
        "Missing enabled/FORCE RLS on academic or identity table",
    )
    return {
        "data": digest(data), "catalog": digest(catalog),
        "catalog_parts": {key: digest(rows) for key, rows in catalog.items()},
        "rows": {key: len(rows) for key, rows in data.items()},
    }


def fingerprint(engine, diagnostics=None):
    with transaction(engine) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        data = {
            table: db.scalar(text(
                f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') "
                f"FROM {table} t"
            )) for table in DATA_TABLES
        }
        catalog = {
            key: [list(row) for row in db.execute(text(query))]
            for key, query in catalog_queries().items()
        }
    if diagnostics is not None:
        diagnostics.update(data=data, catalog=catalog)
    return summarize(data, catalog)


def prepare_source(connection, owner, runtime):
    migration_owner = "classsync_migrator_" + uuid4().hex
    with transaction(owner) as db:
        db.execute(text(f"CREATE ROLE {migration_owner} NOLOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOREPLICATION NOBYPASSRLS"))
        db.execute(text(f"GRANT CREATE ON DATABASE postgres TO {migration_owner}"))
        db.execute(text(f"GRANT USAGE,CREATE ON SCHEMA public TO {migration_owner}"))
        db.execute(text(f"SET LOCAL ROLE {migration_owner}"))
        migrate(db, target=MIGRATION)
        # Nonempty defaults ensure the backup actually exercises default ACL restoration.
        db.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA classsync_academic "
                        f"GRANT SELECT ON TABLES TO {connection.runtime}"))
    with transaction(owner) as db:
        seed(db)
        identity_context(db, tenant_id="tenant-a", uid="uid-admin-other")
        audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
        db.execute(text("""
            INSERT INTO classsync_identity.memberships VALUES
              ('tenant-a','uid-admin-other','person-other',NULL,NULL,
               ARRAY['administrator'],'active',1)
        """))
        for uid, roles, student, faculty in (
            ("uid-student", ["student"], "student-a", None),
            ("uid-teacher", ["teacher"], None, "faculty-a"),
        ):
            identity_context(db, tenant_id="tenant-a", uid=uid)
            audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
            db.execute(text("""
                INSERT INTO classsync_identity.memberships VALUES
                  ('tenant-a',:uid,'person-a',:student,:faculty,CAST(:roles AS text[]),'active',1)
            """), {"uid": uid, "student": student, "faculty": faculty, "roles": roles})
        for schema in ("classsync_identity", "classsync_academic"):
            db.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {connection.runtime}"))
        db.execute(text("GRANT SELECT ON classsync_identity.memberships,"
                        f"classsync_identity.tenants TO {connection.runtime}"))
        for table in ACADEMIC_TABLES:
            db.execute(text(f"GRANT SELECT,INSERT ON classsync_academic.{table} "
                            f"TO {connection.runtime}"))
        db.execute(text("GRANT UPDATE(revision) ON classsync_academic.period_metadata "
                        f"TO {connection.runtime}"))
        for table in ("records", "record_references", "calendars"):
            db.execute(text(f"GRANT UPDATE ON classsync_academic.{table} "
                            f"TO {connection.runtime}"))
        db.execute(text("GRANT DELETE ON classsync_academic.record_references "
                        f"TO {connection.runtime}"))
    repository = store(runtime)
    original = complete(FixtureCalls(repository))
    require({entry.record.kind for entry in original.records} == {
        "programs", "subjects", "sections", "faculty", "resources", "offerings", "constraints",
    }, "Restore fixture must include every academic record kind")
    subject = next(entry for entry in original.records if entry.record.id == "subject-a")
    edited = repository.save(original.period.id, "subjects", subject.record.id, RecordWrite(
        expected_revision=subject.revision,
        record=subject.record.model_copy(update={"name": "Synthetic backup revision"}),
    ))
    expected = repository.save_calendar(original.period.id, CalendarWrite(
        expected_revision=edited.period.revision, calendar=configuration().calendar,
    ))
    other = store(runtime, uid="uid-admin-other").create_period(
        PeriodCreate(title="Synthetic other administrator private period",
                     include_cdm_catalog=False)
    )
    return expected, other, migration_owner


def store(engine, *, uid="uid-admin", tenant="tenant-a", project="synthetic-project"):
    return PostgresAcademicRepository(engine, tenant_id=tenant, firebase_project_id=project,
                                      principal=VerifiedPrincipal(uid=uid))


def expect_sqlstate(engine, statement, expected):
    try:
        with transaction(engine) as db:
            db.execute(text(statement))
    except DBAPIError as error:
        require(error.orig.sqlstate == expected,
                f"Restored constraint returned SQLSTATE {error.orig.sqlstate}, expected {expected}")
    else:
        raise RuntimeError("Restored database lost constraint enforcement")


def check_restored_behavior(connection, owner, runtime, expected, other, migration_owner):
    repository = store(runtime)
    pid = expected.period.id
    require(repository.snapshot(pid) == expected, "Restored full academic snapshot differs")
    runtime.dispose()
    require(repository.snapshot(pid) == expected, "Restore reconnect lost academic data")
    require([p.id for p in repository.periods()] == [pid],
            "Restored administrator sees another owner's period")
    second = store(runtime, uid="uid-admin-other")
    require(second.snapshot(other.period.id) == other, "Second owner's restore differs")
    must_fail(lambda: second.snapshot(pid), "period_not_found")
    must_fail(lambda: repository.snapshot(other.period.id), "period_not_found")
    for candidate in (store(runtime, uid="uid-student"), store(runtime, uid="uid-teacher"),
                      store(runtime, uid="missing"),
                      store(runtime, tenant="tenant-b"), store(runtime, project="other-project")):
        must_fail(lambda candidate=candidate: candidate.snapshot(pid), MembershipErrorCode.DENIED)
    with transaction(runtime) as db:
        for table in ("classsync_identity.memberships", *(
            f"classsync_academic.{name}" for name in ACADEMIC_TABLES
        )):
            require(db.scalar(text(f"SELECT count(*) FROM {table}")) == 0,
                    "Restored runtime inherited pooled context or bypassed RLS")
    with transaction(owner) as db:
        db.execute(text(f"SET LOCAL ROLE {migration_owner}"))
        for table in DATA_TABLES:
            require(db.scalar(text(f"SELECT count(*) FROM {table}")) == 0,
                    "Restored table owner bypassed FORCE RLS")
    # SQL failures roll back their transaction; no fixture correction or row loss is allowed.
    expect_sqlstate(owner, "UPDATE classsync_academic.records SET checksum='tampered'", "23514")
    expect_sqlstate(owner, "UPDATE classsync_academic.calendars SET checksum='tampered'", "23514")
    expect_sqlstate(owner, "UPDATE classsync_academic.records SET revision=0", "23514")
    expect_sqlstate(owner, "UPDATE classsync_academic.record_references "
                    "SET target_id='synthetic-absent' WHERE ctid=("
                    "SELECT ctid FROM classsync_academic.record_references LIMIT 1)", "23503")
    expect_sqlstate(owner, "UPDATE classsync_identity.memberships SET state='active' "
                    "WHERE tenant_id='tenant-a' AND uid='uid-admin'", "23514")
    for statement in ("UPDATE classsync_identity.membership_audit SET actor_uid='forged'",
                      "DELETE FROM classsync_identity.membership_audit",
                      "TRUNCATE classsync_identity.membership_audit"):
        denied(owner, statement)
    subject = next(entry for entry in expected.records if entry.record.id == "subject-a")
    must_fail(lambda: repository.save(pid, "subjects", "subject-a", RecordWrite(
        expected_revision=subject.revision - 1, record=subject.record,
    )), "academic_version_conflict")
    for state, revision in ((MembershipState.REVOKED, 1), (MembershipState.ACTIVE, 2)):
        with transaction(owner) as db:
            identity_context(db, tenant_id="tenant-a", uid="uid-admin")
            change_membership_state(db, tenant_id="tenant-a", uid="uid-admin",
                                    expected_revision=revision, state=state,
                                    actor=VerifiedPrincipal(uid="synthetic-operator"))
        if state == MembershipState.REVOKED:
            must_fail(lambda: repository.snapshot(pid), MembershipErrorCode.DENIED)
        else:
            require(repository.snapshot(pid) == expected, "Restored reactivation lost data")
    with transaction(owner) as db:
        db.execute(text(f"REVOKE SELECT ON classsync_academic.records FROM {connection.runtime}"))
    try:
        must_fail(lambda: repository.snapshot(pid), "academic_storage_unavailable")
    finally:
        with transaction(owner) as db:
            db.execute(text(f"GRANT SELECT ON classsync_academic.records TO {connection.runtime}"))
    require(repository.snapshot(pid) == expected, "Restore outage recovery changed snapshot")
    with transaction(runtime) as db:
        require(db.scalar(text("SELECT count(*) FROM classsync_academic.records")) == 0,
                "Restored pooled context survived outage recovery")
    return {"full_snapshot_and_reconnect": True, "two_active_administrator_owner_isolation": True,
            "student_teacher_wrong_uid_tenant_project_denied": True,
            "runtime_and_table_owner_force_rls": True, "checksum_reference_revision_guards": True,
            "audit_immutable": True, "stale_cas_denied": True,
            "fresh_revocation_reactivation": True, "permission_outage_recovery": True}


def exercise(connection):
    root = owned_root(connection)
    require(connection.run_tool is not None, "Owned PostgreSQL tool runner required")
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    restored_owner = restored_runtime = None
    target = restore_name("classsync_restore_" + uuid4().hex)
    archive = root / ("academic-" + uuid4().hex + ".dump")
    require(not archive.exists(), "New academic archive path required")
    try:
        check_connection(connection, owner, "postgres")
        expected, other, migration_owner = prepare_source(connection, owner, runtime)
        with transaction(owner) as db:
            namespaces = list(db.scalars(text("""
                SELECT nspname FROM pg_namespace
                WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'
            """)))
            public_tables = list(db.scalars(text("""
                SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname
            """)))
            check_source_scope(namespaces, public_tables)
        source_details, restored_details = {}, {}
        before = fingerprint(owner, source_details)
        common = ["--host=127.0.0.1", f"--port={connection.port}",
                  f"--username={connection.owner}", "--no-password"]
        connection.run_tool("pg_dump.exe", *common, "--dbname=postgres", "--format=custom",
                            "--schema=classsync_identity", "--schema=classsync_academic",
                            "--schema=public",
                            f"--file={archive}")
        checksum = archive_hash(connection, archive)
        # Never reuse/replace an existing target. No --clean, --create or DROP path exists.
        create_target(owner, target)
        restored_owner = restored_engine(connection, target, bootstrap=True)
        check_connection(connection, restored_owner, target)
        with transaction(restored_owner) as db:
            namespaces = list(db.scalars(text(
                f"SELECT nspname FROM pg_namespace WHERE nspname IN {SCHEMAS}"
            )))
            public_objects = db.scalar(text("""
                SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public'
            """))
            check_empty_target(namespaces, public_objects)
        archive_hash(connection, archive, checksum)
        toc = root / ("academic-" + uuid4().hex + ".toc")
        listing = connection.run_tool("pg_restore.exe", "--list", archive)
        with toc.open("x", encoding="utf-8") as output:
            output.write(restore_toc(listing))
        connection.run_tool("pg_restore.exe", *common, f"--dbname={target}",
                            "--exit-on-error", "--single-transaction", f"--use-list={toc}", archive)
        after = fingerprint(restored_owner, restored_details)
        if before != after:
            write_new_evidence(root / "academic-restore-comparison.json",
                               {"source": source_details, "restored": restored_details})
        require(before == after, "Restored academic/identity data/catalog/ACL mismatch")
        with transaction(restored_owner) as db:
            db.execute(text(f"GRANT DELETE ON classsync_academic.records TO {connection.runtime}"))
        try:
            require(fingerprint(restored_owner) != after, "Academic ACL drift escaped fingerprint")
        finally:
            with transaction(restored_owner) as db:
                db.execute(text(
                    f"REVOKE DELETE ON classsync_academic.records FROM {connection.runtime}"
                ))
        # Data tamper remains constraint-valid, so the raw-data fingerprint must detect it.
        with transaction(restored_owner) as db:
            db.execute(text("UPDATE classsync_academic.period_metadata SET title=title||' changed' "
                            "WHERE id=:id"), {"id": expected.period.id})
        try:
            require(fingerprint(restored_owner) != after, "Academic data drift escaped fingerprint")
        finally:
            with transaction(restored_owner) as db:
                db.execute(text("UPDATE classsync_academic.period_metadata SET title=:title "
                                "WHERE id=:id"),
                           {"id": expected.period.id, "title": expected.period.title})
        with transaction(restored_owner) as db:
            db.execute(text("ALTER TABLE classsync_academic.records NO FORCE ROW LEVEL SECURITY"))
        try:
            try:
                fingerprint(restored_owner)
            except RuntimeError as error:
                require(str(error) == "Missing enabled/FORCE RLS on academic or identity table",
                        "Unexpected fingerprint error during RLS tamper")
            else:
                raise RuntimeError("Academic FORCE RLS drift escaped fingerprint")
        finally:
            with transaction(restored_owner) as db:
                db.execute(text("ALTER TABLE classsync_academic.records FORCE ROW LEVEL SECURITY"))
        require(fingerprint(restored_owner) == after, "Tamper recovery did not restore baseline")
        with transaction(restored_owner) as db:
            db.execute(text(f"REVOKE ALL ON DATABASE {target} FROM PUBLIC"))
            db.execute(text(f"GRANT CONNECT ON DATABASE {target} TO {connection.runtime}"))
        restored_runtime = restored_engine(connection, target)
        behavior = check_restored_behavior(connection, restored_owner, restored_runtime,
                                           expected, other, migration_owner)
        final_details = {}
        final = fingerprint(restored_owner, final_details)
        require(final["catalog"] == after["catalog"], "Restore functional checks changed catalog")
        require(all(final_details["data"][f"classsync_academic.{table}"]
                    == source_details["data"][f"classsync_academic.{table}"]
                    for table in ACADEMIC_TABLES), "Restore checks changed academic data")
        require(final["rows"]["classsync_identity.membership_audit"]
                == after["rows"]["classsync_identity.membership_audit"] + 2,
                "Restored revocation/reactivation audit entries missing")
        require(fingerprint(owner) == before, "Academic backup/restore changed source")
        archive_hash(connection, archive, checksum)
        return {"migration_target": MIGRATION, "source_database": "postgres",
                "restored_database": target, "archive": str(archive), "archive_sha256": checksum,
                "source_fingerprint": before, "restored_fingerprint": after,
                "restored_after_functional_checks": final,
                "archive_unchanged": True, "source_unchanged": True,
                "data_acl_rls_tamper_detected": True, "functional_restore": behavior,
                "original_data_migration": False, "production_acceptance": False}
    finally:
        for engine in (restored_runtime, restored_owner, runtime, owner):
            if engine is not None:
                engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and args.output.parent.is_dir(), "New evidence file required")
    evidence = qualify(args.bin, exercise)
    write_new_evidence(args.output, evidence)
    print("Synthetic academic backup/restore passed; owned PostgreSQL stopped")


if __name__ == "__main__":
    main()
