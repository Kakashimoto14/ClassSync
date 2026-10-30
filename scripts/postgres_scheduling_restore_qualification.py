"""Same-cluster synthetic Scheduling/academic/identity restore; never original data."""

import argparse
import hashlib
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from classync_contracts.academic import CalendarWrite
from classync_contracts.identity import MembershipErrorCode, MembershipState, VerifiedPrincipal
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence.database import transaction
from classync_persistence.membership_changes import change_membership_state
from classync_persistence.memberships import identity_context
from classync_persistence.schema import migrate
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_academic_repository_qualification import FixtureCalls
from scripts.postgres_academic_restore_qualification import (
    check_connection,
    check_empty_target,
    create_target,
    owned_root,
    restore_toc,
)
from scripts.postgres_academic_restore_qualification import (
    check_restored_behavior as check_academic_behavior,
)
from scripts.postgres_academic_restore_qualification import (
    prepare_source as prepare_academic_source,
)
from scripts.postgres_academic_restore_qualification import store as academic_store
from scripts.postgres_disposable import qualify
from scripts.postgres_draft_qualification import must_fail
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_restore_qualification import digest, restore_name, restored_engine
from scripts.postgres_web_session_qualification import write_new_evidence
from services.academic.tests.test_academic import complete
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_rules import digest as payload_digest
from services.scheduling.app.draft_rules import encode, verified_result
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.tests.test_calendar import configuration

MIGRATION = "0006_scheduling_drafts"
SCHEMA_NAMES = ("classsync_identity", "classsync_academic", "classsync_scheduling")
SCHEMAS = "('classsync_identity','classsync_academic','classsync_scheduling')"
DATA_TABLES = (
    "classsync_identity.tenants", "classsync_identity.people", "classsync_identity.students",
    "classsync_identity.faculty", "classsync_identity.memberships",
    "classsync_identity.membership_audit", "classsync_academic.period_metadata",
    "classsync_academic.records", "classsync_academic.record_references",
    "classsync_academic.calendars", "classsync_scheduling.solver_runs",
    "classsync_scheduling.drafts",
)


def check_source_scope(namespaces, public_tables):
    require(set(namespaces) == {"public", *SCHEMA_NAMES}
            and list(public_tables) == ["alembic_version"],
            "Scheduling backup source contains unexpected namespaces or public tables")


def owned_file_hash(connection, path, suffix, expected=None):
    root = owned_root(connection)
    require(suffix in {"dump", "toc"} and path.parent.resolve() == root
            and not path.is_symlink()
            and re.fullmatch(r"scheduling-[a-f0-9]{32}\." + suffix, path.name)
            and path.is_file() and path.stat().st_size > 0 and path.resolve().parent == root,
            "Only a generated owned Scheduling archive or TOC is accepted")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    require(expected is None or actual == expected, "Scheduling backup archive or TOC changed")
    return actual


def checked_toc(listing):
    """Keep every object/ACL; remove only template0's existing public CREATE entry."""
    lines = listing.splitlines()
    schemas = [match[1] for line in lines if (match := re.fullmatch(
        r"\d+; \d+ \d+ SCHEMA - (\S+) \S+", line
    ))]
    expected_tables = {*DATA_TABLES, "public.alembic_version"}
    require(len(schemas) == 4 and set(schemas) == {"public", *SCHEMA_NAMES},
            "Scheduling archive has missing, duplicate or unexpected schemas")
    for descriptor in ("TABLE", "TABLE DATA"):
        tables = [f"{match[1]}.{match[2]}" for line in lines if (match := re.fullmatch(
            r"\d+; \d+ \d+ " + descriptor + r" (\S+) (\S+) \S+", line
        ))]
        require(len(tables) == len(expected_tables) and set(tables) == expected_tables,
                "Scheduling archive has missing, duplicate or unexpected table/data entries")
    return restore_toc(listing)


def catalog_queries():
    """Explicit three-schema catalog queries; no SQL adaptation/translation layer."""
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
    require(set(data) == set(DATA_TABLES), "Incomplete three-schema raw data fingerprint")
    require(set(catalog) == set(catalog_queries()), "Incomplete three-schema authority fingerprint")
    require(catalog["migration"] == [[MIGRATION]], "Scheduling restore migration target drift")
    require({f"{row[0]}.{row[1]}" for row in catalog["tables"]} == set(DATA_TABLES)
            and all(row[3] and row[4] for row in catalog["tables"]),
            "Missing enabled/FORCE RLS on restored three-schema tables")
    return {"data": digest(data), "catalog": digest(catalog),
            "catalog_parts": {key: digest(value) for key, value in catalog.items()},
            "rows": {key: len(value) for key, value in data.items()}}


def fingerprint(engine, diagnostics=None):
    with transaction(engine) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        data = {table: db.scalar(text(
            "SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') "
            f"FROM {table} t"
        )) for table in DATA_TABLES}
        catalog = {key: [list(row) for row in db.execute(text(query))]
                   for key, query in catalog_queries().items()}
    if diagnostics is not None:
        diagnostics.update(data=data, catalog=catalog)
    return summarize(data, catalog)


def upgrade_scheduling(connection, owner, migration_owner):
    with transaction(owner) as db:
        db.execute(text(f"SET LOCAL ROLE {migration_owner}"))
        migrate(db, target=MIGRATION)
        db.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA classsync_scheduling "
                        f"GRANT SELECT ON TABLES TO {connection.runtime}"))
    with transaction(owner) as db:
        db.execute(text(f"GRANT USAGE ON SCHEMA classsync_scheduling TO {connection.runtime}"))
        db.execute(text("GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA classsync_scheduling "
                        f"TO {connection.runtime}"))


def draft_store(engine, *, uid="uid-admin", tenant="tenant-a", project="synthetic-project"):
    return PostgresDraftRepository(engine, tenant_id=tenant, firebase_project_id=project,
                                   principal=VerifiedPrincipal(uid=uid))


def save_request(result, key, title="Synthetic restore fixture"):
    return SaveDraftRequest(run_id=result.run_id, input_hash=result.input_hash,
                            title=title, idempotency_key=key)


def prepare_source(connection, owner, runtime):
    first, other_empty, migrator = prepare_academic_source(connection, owner, runtime)
    upgrade_scheduling(connection, owner, migrator)
    other_academic = academic_store(runtime, uid="uid-admin-other")
    second = complete(FixtureCalls(other_academic))
    second = other_academic.save_calendar(second.period.id, CalendarWrite(
        expected_revision=second.period.revision, calendar=configuration().calendar,
    ))
    drafts = []
    for uid, snapshot in (("uid-admin", first), ("uid-admin-other", second)):
        ready = academic_readiness(snapshot)
        require(ready.ready and ready.inputs is not None,
                "Generated owned academic period is not ready for the restore fixture")
        result = generate_week(ready.inputs)
        verified_result(ready.inputs, result)  # Independent validation, no changed solver options.
        repository = draft_store(runtime, uid=uid)
        repository.remember_run(ready.inputs, result)
        request = save_request(result, "restore-owned-save-key")
        draft, created = repository.save(request)
        require(created, "New restore fixture unexpectedly replayed an existing draft")
        drafts.append((draft, request, ready.inputs, result))
    expired = drafts[0][3].model_copy(update={"run_id": str(uuid4())})
    verified_result(drafts[0][2], expired)
    payload = encode({"inputs": drafts[0][2].model_dump(mode="json"),
                      "result": expired.model_dump(mode="json")})
    with transaction(owner) as db:
        db.execute(text("""
            INSERT INTO classsync_scheduling.solver_runs
                (tenant_id,owner_uid,id,created_at,payload,checksum)
            VALUES ('tenant-a','uid-admin',:id,:created,:payload,:checksum)
        """), {"id": expired.run_id, "created": datetime.now(UTC) - timedelta(hours=25),
               "payload": payload, "checksum": payload_digest(payload)})
    return {"academic": first, "other_empty": other_empty, "other_academic": second,
            "migrator": migrator, "drafts": drafts, "expired": expired}


def expect_sqlstate(engine, statement, parameters, expected):
    try:
        with transaction(engine) as db:
            db.execute(text(statement), parameters)
            # If a negative insert unexpectedly succeeds, roll it back before failing.
            raise RuntimeError("Restored Scheduling database constraint was not enforced")
    except DBAPIError as error:
        require(error.orig.sqlstate == expected,
                f"Restored Scheduling SQLSTATE {error.orig.sqlstate}, expected {expected}")


def check_scheduling_behavior(connection, owner, runtime, fixture):
    first, body, inputs, result = fixture["drafts"][0]
    second = fixture["drafts"][1][0]
    repository, other = draft_store(runtime), draft_store(runtime, uid="uid-admin-other")
    require(repository.get(first.id) == first and other.get(second.id) == second,
            "Restored typed draft/input/result differs")
    with runtime.connect() as db:
        old_backend = db.scalar(text("SELECT pg_backend_pid()"))
    runtime.dispose()
    with runtime.connect() as db:
        require(db.scalar(text("SELECT pg_backend_pid()")) != old_backend,
                "Restore reconnect reused old physical backend")
    require(repository.get(first.id) == first and other.get(second.id) == second,
            "Physical reconnect changed restored drafts")
    require([item.id for item in repository.list().drafts] == [first.id]
            and [item.id for item in other.list().drafts] == [second.id],
            "Restored draft listing crossed owners")
    must_fail(lambda: repository.get(second.id), "draft_not_found")
    must_fail(lambda: other.get(first.id), "draft_not_found")
    for candidate in (draft_store(runtime, uid="uid-student"),
                      draft_store(runtime, uid="uid-teacher"), draft_store(runtime, uid="absent"),
                      draft_store(runtime, tenant="tenant-b"),
                      draft_store(runtime, project="wrong-project")):
        must_fail(lambda candidate=candidate: candidate.get(first.id), MembershipErrorCode.DENIED)
    require(repository.save(body) == (first, False), "Restored same-key replay changed draft")
    for changes in ({"idempotency_key": "changed-restore-key"}, {"title": "Changed"},
                    {"input_hash": "0" * 64}, {"run_id": "different-run"}):
        changed = SaveDraftRequest.model_validate(body.model_dump() | changes)
        must_fail(lambda changed=changed: repository.save(changed), "idempotency_conflict")
    must_fail(lambda: repository.save(save_request(fixture["expired"], "expired-restore-key")),
              "run_expired")
    with transaction(owner) as db:
        db.execute(text(f"SET LOCAL ROLE {fixture['migrator']}"))
        for table in ("solver_runs", "drafts"):
            require(db.scalar(text(f"SELECT count(*) FROM classsync_scheduling.{table}")) == 0,
                    "Restored non-superuser table owner bypassed FORCE RLS")
        repository.context.context(db, VerifiedPrincipal(uid="uid-admin"))
        require(db.scalar(text("SELECT count(*) FROM classsync_scheduling.drafts")) == 1,
                "Scoped non-superuser table owner cannot read own restored draft")
    for table in ("solver_runs", "drafts"):
        for statement in (f"UPDATE classsync_scheduling.{table} SET checksum=checksum",
                          f"DELETE FROM classsync_scheduling.{table}"):
            expect_sqlstate(owner, statement, {}, "42501")
    # Truncate the complete FK-connected set so rejection comes from the immutable
    # trigger, rather than PostgreSQL's earlier referenced-table dependency check.
    expect_sqlstate(owner, "TRUNCATE classsync_scheduling.solver_runs, "
                    "classsync_scheduling.drafts", {}, "42501")
    checksum_result = result.model_copy(update={"run_id": str(uuid4())})
    payload = encode({"inputs": inputs.model_dump(mode="json"),
                      "result": checksum_result.model_dump(mode="json")})
    expect_sqlstate(owner, """
        INSERT INTO classsync_scheduling.solver_runs
            (tenant_id,owner_uid,id,created_at,payload,checksum)
        VALUES ('tenant-a','uid-admin',:id,now(),:payload,:checksum)
    """, {"id": checksum_result.run_id, "payload": payload,
           "checksum": payload_digest(payload) + "0"}, "23514")
    # An otherwise valid metadata envelope cannot bind another owner's server run.
    crossed = first.model_copy(update={"id": str(uuid4()), "creator": "uid-admin-other",
                                      "run_id": fixture["expired"].run_id,
                                      "generation_result": fixture["expired"]})
    payload = encode(crossed.model_dump(mode="json"))
    statement = """
        INSERT INTO classsync_scheduling.drafts
            (tenant_id,owner_uid,id,run_id,title,created_at,idempotency_key,payload,checksum)
        VALUES ('tenant-a',:owner,:id,:run,:title,:created,:key,:payload,:checksum)
    """
    params = {"owner": crossed.creator, "id": crossed.id, "run": crossed.run_id,
              "title": crossed.title, "created": crossed.created_at, "key": "cross-owner-key",
              "payload": payload, "checksum": payload_digest(payload)}
    expect_sqlstate(owner, statement, params, "23503")
    mismatch = crossed.model_copy(update={"creator": "uid-admin"})
    payload = encode(mismatch.model_dump(mode="json"))
    expect_sqlstate(owner, statement, params | {
        "owner": "uid-admin", "title": "Metadata differs", "payload": payload,
        "checksum": payload_digest(payload),
    }, "23514")
    for state, revision in ((MembershipState.REVOKED, 3), (MembershipState.ACTIVE, 4)):
        with transaction(owner) as db:
            identity_context(db, tenant_id="tenant-a", uid="uid-admin")
            change_membership_state(db, tenant_id="tenant-a", uid="uid-admin",
                                    expected_revision=revision, state=state,
                                    actor=VerifiedPrincipal(uid="synthetic-operator"))
        if state == MembershipState.REVOKED:
            must_fail(lambda: repository.get(first.id), MembershipErrorCode.DENIED)
            must_fail(lambda: repository.save(body), MembershipErrorCode.DENIED)
        else:
            require(repository.get(first.id) == first, "Restore reactivation changed saved draft")
    with transaction(owner) as db:
        db.execute(text(f"REVOKE SELECT ON classsync_scheduling.drafts FROM {connection.runtime}"))
    try:
        must_fail(lambda: repository.get(first.id), "persistence_unavailable")
    finally:
        with transaction(owner) as db:
            db.execute(text(f"GRANT SELECT ON classsync_scheduling.drafts TO {connection.runtime}"))
    require(repository.get(first.id) == first and repository.save(body) == (first, False),
            "Restored Scheduling outage recovery changed saved draft/idempotency")
    with transaction(runtime) as db:
        for table in ("solver_runs", "drafts"):
            require(db.scalar(text(f"SELECT count(*) FROM classsync_scheduling.{table}")) == 0,
                    "Restored runtime retained authority context or bypassed RLS")
        require(not db.scalar(text("SELECT current_setting('classsync.uid',true)")),
                "Restored runtime retained caller identity")
    return {"exact_draft_and_physical_reconnect": True, "two_active_owner_isolation": True,
            "role_tenant_project_denial": True, "strict_replay_conflict_expiry": True,
            "runtime_and_table_owner_force_rls": True, "immutable_dml": True,
            "checksum_metadata_cross_owner_fk": True, "current_revocation_reactivation": True,
            "actual_permission_outage_recovery": True}


def check_functional_delta(before, after, owner_name):
    """Only four known restored membership transitions may alter the original raw rows."""
    for table in DATA_TABLES:
        if table not in {"classsync_identity.memberships", "classsync_identity.membership_audit"}:
            require(before[table] == after[table],
                    "Restore checks changed academic/Scheduling data")
    old_members = {(row["tenant_id"], row["uid"]): row for row in before[
        "classsync_identity.memberships"]}
    new_members = {(row["tenant_id"], row["uid"]): row for row in after[
        "classsync_identity.memberships"]}
    expected = {key: dict(value) for key, value in old_members.items()}
    expected[("tenant-a", "uid-admin")].update(state="active", revision=5)
    require(new_members == expected, "Unexpected restored membership change")
    original_audit = before["classsync_identity.membership_audit"]
    final_audit = after["classsync_identity.membership_audit"]
    require(len(final_audit) == len(original_audit) + 4
            and all(row in final_audit for row in original_audit),
            "Restore audit growth or preserved original audit differs")
    added = [row for row in final_audit if row not in original_audit]
    require({row["revision"] for row in added} == {2, 3, 4, 5},
            "Unexpected restore audit revisions")
    for row in added:
        state = "revoked" if row["revision"] % 2 == 0 else "active"
        require(row["tenant_id"] == "tenant-a" and row["subject_uid"] == "uid-admin"
                and row["actor_uid"] == "synthetic-operator"
                and row["database_session_user"] == owner_name
                and row["new_snapshot"] == expected[("tenant-a", "uid-admin")] | {
                    "revision": row["revision"], "state": state,
                } and row["old_snapshot"] == expected[("tenant-a", "uid-admin")] | {
                    "revision": row["revision"] - 1,
                    "state": "active" if state == "revoked" else "revoked",
                }, "Restored audit did not preserve exact current authority transition")


def exercise(connection):
    root = owned_root(connection)
    require(connection.run_tool is not None, "Owned PostgreSQL tools required")
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    restored_owner = restored_runtime = None
    archive = root / ("scheduling-" + uuid4().hex + ".dump")
    target = restore_name("classsync_restore_" + uuid4().hex)
    require(not archive.exists(), "New Scheduling archive required")
    try:
        check_connection(connection, owner, "postgres")
        fixture = prepare_source(connection, owner, runtime)
        with transaction(owner) as db:
            namespaces = list(db.scalars(text("SELECT nspname FROM pg_namespace "
                                              "WHERE nspname NOT LIKE 'pg_%' "
                                              "AND nspname<>'information_schema'")))
            public_tables = list(db.scalars(text("""
                SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname
            """)))
            check_source_scope(namespaces, public_tables)
        before_details, after_details = {}, {}
        before = fingerprint(owner, before_details)
        common = ["--host=127.0.0.1", f"--port={connection.port}",
                  f"--username={connection.owner}", "--no-password"]
        connection.run_tool("pg_dump.exe", *common, "--dbname=postgres", "--format=custom",
                            "--schema=classsync_identity", "--schema=classsync_academic",
                            "--schema=classsync_scheduling", "--schema=public", f"--file={archive}")
        archive_sha = owned_file_hash(connection, archive, "dump")
        create_target(owner, target)
        restored_owner = restored_engine(connection, target, bootstrap=True)
        check_connection(connection, restored_owner, target)
        with transaction(restored_owner) as db:
            namespaces = list(db.scalars(text("SELECT nspname FROM pg_namespace "
                                              "WHERE nspname NOT LIKE 'pg_%' AND "
                                              "nspname NOT IN ('public','information_schema')")))
            public_objects = db.scalar(text("""
                SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public'
            """))
            check_empty_target(namespaces, public_objects)
        listing = connection.run_tool("pg_restore.exe", "--list", archive)
        toc = root / ("scheduling-" + uuid4().hex + ".toc")
        with toc.open("x", encoding="utf-8") as output:
            output.write(checked_toc(listing))
        toc_sha = owned_file_hash(connection, toc, "toc")
        owned_file_hash(connection, archive, "dump", archive_sha)
        owned_file_hash(connection, toc, "toc", toc_sha)
        connection.run_tool("pg_restore.exe", *common, f"--dbname={target}", "--exit-on-error",
                            "--single-transaction", f"--use-list={toc}", archive)
        after = fingerprint(restored_owner, after_details)
        if before != after:
            write_new_evidence(root / "scheduling-restore-comparison.json",
                               {"source": before_details, "restored": after_details})
        require(before == after, "Restored three-schema data/catalog/authority differs")
        with transaction(restored_owner) as db:
            db.execute(text(f"GRANT UPDATE ON classsync_scheduling.drafts TO {connection.runtime}"))
        try:
            require(fingerprint(restored_owner) != after,
                    "Scheduling ACL drift escaped fingerprint")
        finally:
            with transaction(restored_owner) as db:
                db.execute(text("REVOKE UPDATE ON classsync_scheduling.drafts "
                                f"FROM {connection.runtime}"))
        with transaction(restored_owner) as db:
            db.execute(text("ALTER TABLE classsync_scheduling.drafts NO FORCE ROW LEVEL SECURITY"))
        try:
            try:
                fingerprint(restored_owner)
            except RuntimeError as error:
                require(str(error) == "Missing enabled/FORCE RLS on restored three-schema tables",
                        "Unexpected Scheduling FORCE RLS tamper error")
            else:
                raise RuntimeError("Scheduling FORCE RLS drift escaped fingerprint")
        finally:
            with transaction(restored_owner) as db:
                db.execute(text("ALTER TABLE classsync_scheduling.drafts FORCE ROW LEVEL SECURITY"))
        period = fixture["academic"].period
        with transaction(restored_owner) as db:
            db.execute(text("UPDATE classsync_academic.period_metadata SET title=title||' changed' "
                            "WHERE id=:id"), {"id": period.id})
        try:
            require(fingerprint(restored_owner) != after, "Content drift escaped fingerprint")
        finally:
            with transaction(restored_owner) as db:
                db.execute(text("UPDATE classsync_academic.period_metadata SET title=:title "
                                "WHERE id=:id"), {"id": period.id, "title": period.title})
        require(fingerprint(restored_owner) == after, "Restore tamper recovery changed baseline")
        with transaction(restored_owner) as db:
            db.execute(text(f"REVOKE ALL ON DATABASE {target} FROM PUBLIC"))
            db.execute(text(f"GRANT CONNECT ON DATABASE {target} TO {connection.runtime}"))
        restored_runtime = restored_engine(connection, target)
        academic = check_academic_behavior(connection, restored_owner, restored_runtime,
                                           fixture["academic"], fixture["other_empty"],
                                           fixture["migrator"])
        require(academic_store(restored_runtime, uid="uid-admin-other").snapshot(
            fixture["other_academic"].period.id) == fixture["other_academic"],
            "Second owner's complete restored academic snapshot differs")
        scheduling = check_scheduling_behavior(
            connection, restored_owner, restored_runtime, fixture,
        )
        final_details = {}
        final = fingerprint(restored_owner, final_details)
        require(final["catalog"] == after["catalog"], "Restore behavior changed source authority")
        check_functional_delta(before_details["data"], final_details["data"], connection.owner)
        require(fingerprint(owner) == before, "Backup/restore changed generated source")
        owned_file_hash(connection, archive, "dump", archive_sha)
        owned_file_hash(connection, toc, "toc", toc_sha)
        return {"migration_target": MIGRATION, "source_database": "postgres",
                "restored_database": target, "source_fingerprint": before,
                "restored_fingerprint": after, "restored_after_functional_checks": final,
                "archive": str(archive), "archive_sha256": archive_sha,
                "toc_sha256": toc_sha, "only_public_schema_create_omitted": True,
                "source_archive_toc_unchanged": True, "actual_academic_ready_cp_sat_fixture": True,
                "data_acl_force_rls_drift_detected": True,
                "academic_behavior": academic, "scheduling_behavior": scheduling,
                "exact_four_current_membership_audit_transitions": True,
                "same_cluster_synthetic_restore_only": True, "production_acceptance": False,
                "cross_host_disaster_recovery": False, "publication_adaptation": False}
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
    print("Generated three-schema Scheduling backup/restore passed; owned PostgreSQL stopped")


if __name__ == "__main__":
    main()
