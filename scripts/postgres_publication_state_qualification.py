"""Generated-only publication schema probes in a new marked SSPI PostgreSQL cluster.

No application publication adapter, approval, institutional policy or cutover is proved.
The tiny solver fixture is generated only during explicitly coordinated actual qualification.
"""

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence.academic_periods import PostgresAcademicPeriods
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from classync_persistence.schema import migrate
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_disposable import checked_root, qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.app.draft_rules import digest, encode, verified_result
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.tests.test_calendar import configuration
from services.scheduling.tests.test_engine import tiny

MIGRATION = "0007_publication_state"
TABLES = ("published_versions", "publication_heads")
VERSION_COLUMNS = (
    "tenant_id", "dataset", "period_id", "owner_uid", "actor_uid", "draft_id", "id",
    "revision", "academic_revision", "created_at", "idempotency_key", "command",
    "request_hash", "payload", "checksum",
)
INSERT_VERSION = text(
    "INSERT INTO classsync_scheduling.published_versions (" + ",".join(VERSION_COLUMNS)
    + ") VALUES (" + ",".join(":" + key for key in VERSION_COLUMNS) + ") RETURNING *"
)
INSERT_HEAD = text("""
    INSERT INTO classsync_scheduling.publication_heads
        (tenant_id,dataset,period_id,owner_uid,revision)
    VALUES (:tenant_id,:dataset,:period_id,:owner_uid,:revision)
""")


def context(db, *, uid="uid-admin", tenant="tenant-a", project="synthetic-project"):
    identity_context(db, tenant_id=tenant, uid=uid)
    db.execute(text("SELECT set_config('classsync.project_id', :project, true)"),
               {"project": project})


def checked_connection(connection):
    """Reject original/unmarked targets before even constructing an engine or identity DDL."""
    return checked_root(connection.root, Path(tempfile.gettempdir()))


def check_binding(db, connection, root):
    observed = db.execute(text(
        "SELECT current_setting('data_directory'),current_user,inet_server_port(),"
        "host(inet_server_addr())"
    )).one()
    require(Path(observed[0]).resolve() == root / "data"
            and tuple(observed[1:]) == (connection.owner, connection.port, "127.0.0.1"),
            "Publication qualification target binding mismatch")
    require(db.scalar(text("SELECT version_num FROM public.alembic_version")) == MIGRATION,
            "Publication qualification migration scope drift")


def expect_sqlstate(engine, operation, expected, *, uid="uid-admin", role=None,
                    tenant="tenant-a", project="synthetic-project"):
    """Always roll unexpected success back; never leave a failed probe in the fixture."""
    try:
        with transaction(engine) as db:
            if role:
                db.execute(text(f"SET LOCAL ROLE {role}"))
            context(db, uid=uid, tenant=tenant, project=project)
            operation(db)
            raise RuntimeError("Publication database negative probe unexpectedly succeeded")
    except DBAPIError as error:
        require(error.orig.sqlstate == expected,
                f"Publication probe SQLSTATE {error.orig.sqlstate}, expected {expected}")


def version_parameters(draft, *, revision=1, academic_revision=1, key=None):
    """Exact canonical command and complete immutable draft envelope, generated fixture only."""
    key = key or ("publication-fixture-" + uuid4().hex)
    command = PublicationCommand(
        draft_id=draft.id, dataset="synthetic", source="administrator",
        expected_version=revision - 1, expected_academic_revision=academic_revision,
        idempotency_key=key, calendar=configuration().calendar,
    )
    command_text = encode(command.model_dump(mode="json"))
    payload = encode({"draft": draft.model_dump(mode="json"),
                      "calendar": command.calendar.model_dump(mode="json"),
                      "review": {"status": "schema-fixture-only"}})
    return {"tenant_id": "tenant-a", "dataset": "synthetic", "period_id": draft.period_id,
            "owner_uid": draft.creator, "actor_uid": draft.creator, "draft_id": draft.id,
            "id": str(uuid4()), "revision": revision,
            "academic_revision": academic_revision, "created_at": datetime.now(UTC),
            "idempotency_key": key, "command": command_text, "request_hash": digest(command_text),
            "payload": payload, "checksum": digest(payload)}


def check_saved(row, expected):
    require(set(row) == {*VERSION_COLUMNS, "sequence"}
            and all(row[column] == expected[column] for column in VERSION_COLUMNS)
            and isinstance(row["sequence"], int) and row["sequence"] > 0,
            "Persisted publication envelope or generated sequence changed")


def force_orphan_constraint(db, parameters):
    """Force deferred commit checks before the probe's intentional rollback."""
    db.execute(INSERT_VERSION, parameters)
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def seed_fixtures(connection, owner, runtime):
    with transaction(owner) as db:
        db.execute(text(f"GRANT USAGE ON SCHEMA classsync_academic,classsync_scheduling "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT SELECT,INSERT ON classsync_academic.period_metadata "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA classsync_scheduling "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT UPDATE ON classsync_scheduling.publication_heads "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT USAGE,SELECT ON SEQUENCE "
                        "classsync_scheduling.published_versions_sequence_seq "
                        f"TO {connection.runtime}"))
        db.execute(text("INSERT INTO classsync_identity.people VALUES "
                        "('tenant-a','person-publication-other')"))
        identity_context(db, tenant_id="tenant-a", uid="uid-admin-other")
        audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
        db.execute(text("INSERT INTO classsync_identity.memberships VALUES "
                        "('tenant-a','uid-admin-other','person-publication-other',"
                        "NULL,NULL,ARRAY['administrator'],'active',1)"))
        for uid, role, student, faculty in (
            ("uid-student", "student", "student-a", None),
            ("uid-teacher", "teacher", None, "faculty-a"),
        ):
            identity_context(db, tenant_id="tenant-a", uid=uid)
            db.execute(text("INSERT INTO classsync_identity.memberships VALUES "
                            "('tenant-a',:uid,'person-a',:student,:faculty,"
                            "ARRAY[CAST(:role AS text)],'active',1)"),
                       {"uid": uid, "role": role, "student": student, "faculty": faculty})
    periods = PostgresAcademicPeriods(runtime, tenant_id="tenant-a",
                                     firebase_project_id="synthetic-project")
    drafts, statuses = [], []
    for uid, shared in (("uid-admin", False), ("uid-admin-other", False),
                        ("uid-admin-other", True)):
        if shared:
            period_id = drafts[0].period_id
            with transaction(runtime) as db:
                context(db, uid=uid)
                db.execute(text("INSERT INTO classsync_academic.period_metadata "
                                "(tenant_id,owner_uid,id,title) VALUES "
                                "('tenant-a',:uid,:period,'Owned same-ID collision fixture')"),
                           {"uid": uid, "period": period_id})
        else:
            period = periods.create_for(VerifiedPrincipal(uid=uid),
                                        title="Generated publication probe")
            require(period.revision == 1, "New fixture academic metadata is not revision one")
            period_id = period.id
        inputs = tiny()
        inputs.period_id, inputs.data_version = period_id, "1"
        result = generate_week(inputs)
        verified_result(inputs, result)
        statuses.append(result.solver_status)
        repository = PostgresDraftRepository(
            runtime, tenant_id="tenant-a", firebase_project_id="synthetic-project",
            principal=VerifiedPrincipal(uid=uid),
        )
        repository.remember_run(inputs, result)
        draft, created = repository.save(SaveDraftRequest(
            run_id=result.run_id, input_hash=result.input_hash,
            title="Disposable publication schema fixture",
            idempotency_key="schema-fixture-save-" + str(len(drafts)),
        ))
        require(created and repository.get(draft.id) == draft, "Owned generated draft changed")
        drafts.append(draft)
    return drafts, statuses


def read_state(engine, *, uid="uid-admin", tenant="tenant-a", project="synthetic-project",
               role=None):
    with transaction(engine) as db:
        if role:
            db.execute(text(f"SET LOCAL ROLE {role}"))
        context(db, uid=uid, tenant=tenant, project=project)
        return {table: [dict(row) for row in db.execute(text(
            f"SELECT * FROM classsync_scheduling.{table} "
            "ORDER BY tenant_id,dataset,period_id,revision"
        )).mappings()] for table in TABLES}


def catalog_guards(owner):
    with transaction(owner) as db:
        rows = db.execute(text("""
            SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,pg_get_userbyid(c.relowner)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='classsync_scheduling'
                AND c.relname IN ('published_versions','publication_heads') ORDER BY c.relname
        """)).all()
        require(len(rows) == 2 and all(row[1] and row[2] for row in rows),
                "Publication tables lack ENABLE/FORCE RLS")
        require(len({row[3] for row in rows}) == 1, "Publication table owners differ")
        migrator = rows[0][3]
        role = db.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=:role"),
                          {"role": migrator}).one()
        require(tuple(role) == (False, False), "Publication table owner bypasses RLS")
        public_grants = db.scalar(text("""
            SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault(
                CASE WHEN c.relkind='S' THEN 'S'::"char" ELSE 'r'::"char" END,c.relowner))) a
            WHERE n.nspname='classsync_scheduling' AND a.grantee=0
        """))
        public_functions = db.scalar(text("""
            SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
            WHERE n.nspname='classsync_scheduling' AND a.grantee=0
        """))
        require(public_grants == public_functions == 0, "PUBLIC has scheduling privileges")
        return migrator


def constraint_probes(owner, runtime, drafts, first, second, migrator):
    tested = []
    base = version_parameters(drafts[0], revision=3)
    cases = [
        ("checksum", {"checksum": "bad"}, "23514"),
        ("request-hash", {"request_hash": "bad"}, "23514"),
        ("actor-binding", {"actor_uid": "uid-admin-other"}, "23514"),
        ("invalid-dataset", {"dataset": "private"}, "23514"),
        ("zero-revision", {"revision": 0}, "23514"),
        ("zero-academic-revision", {"academic_revision": 0}, "23514"),
        ("foreign-draft", {"draft_id": drafts[1].id}, "23514"),
        ("foreign-period", {"period_id": drafts[1].period_id}, "23514"),
        ("duplicate-revision", version_parameters(drafts[0], revision=1), "23505"),
        ("duplicate-key", version_parameters(drafts[0], revision=3,
                                              key=first["idempotency_key"]), "23505"),
    ]
    for name, changes, sqlstate in cases:
        parameters = base | changes
        expect_sqlstate(owner, lambda db, p=parameters: db.execute(INSERT_VERSION, p), sqlstate)
        tested.append(name)
    for field, value in (("draft_id", "missing"), ("dataset", "institutional"),
                         ("source", "academic-sandbox"), ("expected_version", 100),
                         ("expected_academic_revision", 100), ("idempotency_key", "changed-key")):
        parameters = dict(base)
        command = json.loads(parameters["command"]) | {field: value}
        parameters["command"] = encode(command)
        parameters["request_hash"] = digest(parameters["command"])
        expect_sqlstate(owner, lambda db, p=parameters: db.execute(INSERT_VERSION, p), "23514")
        tested.append("command-" + field)
    parameters = dict(base)
    payload = json.loads(parameters["payload"])
    payload["calendar"]["effective_start"] = "2026-10-02"
    parameters.update(payload=encode(payload), checksum=digest(encode(payload)))
    expect_sqlstate(owner, lambda db: db.execute(INSERT_VERSION, parameters), "23514")
    tested.append("calendar-mismatch")
    # Check relational FKs independently of JSON-envelope checks.
    for name, changes in (("owned-draft-fk", {"draft_id": "absent-draft"}),
                          ("owned-period-fk", {"period_id": "absent-period"})):
        p = dict(base) | changes
        payload, command = json.loads(p["payload"]), json.loads(p["command"])
        payload["draft"].update({"id" if key == "draft_id" else key: value
                                 for key, value in changes.items()})
        if "draft_id" in changes:
            command["draft_id"] = changes["draft_id"]
        p.update(payload=encode(payload), command=encode(command), checksum=digest(encode(payload)),
                 request_hash=digest(encode(command)))
        expect_sqlstate(owner, lambda db, p=p: db.execute(INSERT_VERSION, p), "23503")
        tested.append(name)
    for table, operations in (("published_versions", ("UPDATE", "DELETE")),
                              ("publication_heads", ("DELETE",))):
        for operation in operations:
            statement = (f"UPDATE classsync_scheduling.{table} SET checksum=checksum"
                         if operation == "UPDATE" else f"DELETE FROM classsync_scheduling.{table}")
            expect_sqlstate(owner, lambda db, s=statement: db.execute(text(s)), "42501")
            tested.append(table + "-" + operation.lower())
    expect_sqlstate(owner, lambda db: db.execute(text(
        "TRUNCATE classsync_scheduling.publication_heads,classsync_scheduling.published_versions"
    )), "42501")
    tested.append("both-tables-truncate")
    for revision in (1, 4):
        expect_sqlstate(runtime, lambda db, r=revision: db.execute(text(
            "UPDATE classsync_scheduling.publication_heads SET revision=:revision "
            "WHERE period_id=:period"
        ), {"revision": r, "period": first["period_id"]}), "23514")
    expect_sqlstate(runtime, lambda db: db.execute(text(
        "UPDATE classsync_scheduling.publication_heads SET revision=3 WHERE period_id=:period"
    ), {"period": first["period_id"]}), "42501")  # No owned version at revision3.
    expect_sqlstate(runtime, lambda db: db.execute(INSERT_HEAD, second | {"revision": 2}), "23514")
    expect_sqlstate(runtime, lambda db: db.execute(INSERT_HEAD, second), "42501")
    expect_sqlstate(runtime, lambda db: db.execute(INSERT_VERSION, base), "42501",
                    uid="uid-admin-other")
    # FORCE RLS still denies a scoped table owner writing another Administrator's version.
    expect_sqlstate(owner, lambda db: db.execute(INSERT_VERSION, base), "42501",
                    uid="uid-admin-other", role=migrator)
    # Admin B independently owns academic metadata/draft with the SAME period ID.
    collision = version_parameters(drafts[2], revision=3)
    require(collision["period_id"] == first["period_id"]
            and collision["owner_uid"] != first["owner_uid"], "Same-period fixture missing")
    expect_sqlstate(runtime, lambda db: db.execute(INSERT_VERSION, collision), "42501",
                    uid="uid-admin-other")
    with transaction(runtime) as db:
        context(db, uid="uid-admin-other")
        for changes in ("revision=revision+1", "owner_uid='uid-admin-other',revision=revision+1"):
            affected = db.execute(text("UPDATE classsync_scheduling.publication_heads SET "
                                       + changes + " WHERE period_id=:period"),
                                  {"period": first["period_id"]}).rowcount
            require(affected == 0, "Other Admin mutated another owner's same-period head")
    for field, value in (("owner_uid", "uid-admin-other"), ("dataset", "institutional"),
                         ("period_id", second["period_id"]), ("tenant_id", "tenant-b")):
        expect_sqlstate(owner, lambda db, f=field, v=value: db.execute(text(
            f"UPDATE classsync_scheduling.publication_heads SET {f}=:value,revision=revision+1 "
            "WHERE period_id=:period"
        ), {"value": v, "period": first["period_id"]}), "23514")
    expect_sqlstate(runtime, lambda db: db.execute(INSERT_VERSION,
                    version_parameters(drafts[0], revision=5)), "42501")
    expect_sqlstate(runtime, lambda db: force_orphan_constraint(db, base), "23514")
    return tested + ["head-stale-gap-missing-owned-version", "head-initial-one",
                     "head-foreign-owner", "version-foreign-owner", "force-rls-owner-write",
                     "same-period-two-admin-owner-isolation", "immutable-head-owner-scope",
                     "version-sequence-rls", "deferred-orphan-version"]


def exercise(connection):
    root = checked_connection(connection)
    foundation = identity_exercise(connection, target=MIGRATION)
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    try:
        with transaction(owner) as db:
            check_binding(db, connection, root)
        migrator = catalog_guards(owner)
        drafts, statuses = seed_fixtures(connection, owner, runtime)
        first, second = (version_parameters(draft) for draft in drafts[:2])
        with transaction(runtime) as db:
            context(db)
            saved = dict(db.execute(INSERT_VERSION, first).mappings().one())
            check_saved(saved, first)
            db.execute(INSERT_HEAD, first)
        with transaction(runtime) as db:
            context(db, uid="uid-admin-other")
            other = dict(db.execute(INSERT_VERSION, second).mappings().one())
            check_saved(other, second)
            db.execute(INSERT_HEAD, second)
        next_version = version_parameters(drafts[0], revision=2)
        with transaction(runtime) as db:
            context(db)
            advanced = dict(db.execute(INSERT_VERSION, next_version).mappings().one())
            check_saved(advanced, next_version)
            db.execute(text("UPDATE classsync_scheduling.publication_heads SET revision=2 "
                            "WHERE period_id=:period"), {"period": first["period_id"]})
        require(saved["sequence"] < other["sequence"] < advanced["sequence"],
                "Server sequence did not increase")
        baseline = read_state(runtime)
        require(len(baseline["published_versions"]) == 3
                and len(baseline["publication_heads"]) == 2
                and next(h for h in baseline["publication_heads"]
                         if h["period_id"] == first["period_id"])["revision"] == 2,
                "Committed version/head state differs")
        require(read_state(runtime, uid="uid-admin-other") == baseline,
                "Same-tenant current Admin cannot read published state")
        negatives = constraint_probes(owner, runtime, drafts, first, second, migrator)
        require(read_state(runtime) == baseline, "Negative probe changed publication state")
        # A valid inserted version/head pair must roll back together after application failure.
        try:
            with transaction(runtime) as db:
                context(db)
                pending = version_parameters(drafts[0], revision=3)
                db.execute(INSERT_VERSION, pending)
                db.execute(text("UPDATE classsync_scheduling.publication_heads SET revision=3 "
                                "WHERE period_id=:period"), {"period": first["period_id"]})
                with transaction(owner) as observer:
                    require(observer.scalar(text("SELECT count(*) FROM "
                        "classsync_scheduling.published_versions")) == 3,
                        "Uncommitted publication version leaked")
                raise ValueError("synthetic transaction rollback")
        except ValueError:
            pass
        require(read_state(runtime) == baseline, "Failed transaction left a partial head/version")
        denied_contexts = [dict(uid="uid-student"), dict(uid="uid-teacher"), dict(uid="missing"),
                           dict(tenant="tenant-b"), dict(project="wrong-project")]
        for denied in denied_contexts:
            require(all(not rows for rows in read_state(runtime, **denied).values()),
                    "Wrong role/UID/tenant/project read published state")
        for denied in denied_contexts:
            expect_sqlstate(runtime, lambda db: db.execute(INSERT_VERSION,
                            version_parameters(drafts[0], revision=3)), "42501", **denied)
        with transaction(owner) as db:
            db.execute(text(f"SET LOCAL ROLE {migrator}"))
            require(all(db.scalar(text(f"SELECT count(*) FROM classsync_scheduling.{table}")) == 0
                        for table in TABLES), "No-context table owner bypassed FORCE RLS")
        require(read_state(owner, role=migrator) == baseline,
                "Scoped non-superuser owner cannot read published state")
        for state, revision in (("revoked", 2), ("active", 3)):
            with transaction(owner) as db:
                identity_context(db, tenant_id="tenant-a", uid="uid-admin")
                audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                db.execute(text("UPDATE classsync_identity.memberships SET state=:state,"
                                "revision=:revision WHERE tenant_id='tenant-a' "
                                "AND uid='uid-admin'"),
                           {"state": state, "revision": revision})
            if state == "revoked":
                require(all(not rows for rows in read_state(runtime).values()),
                        "Revoked Admin retained publication access")
                expect_sqlstate(runtime, lambda db: db.execute(INSERT_VERSION,
                                version_parameters(drafts[0], revision=3)), "42501")
        require(read_state(runtime) == baseline, "Membership recovery changed exact publication")
        with transaction(owner) as db:
            db.execute(text("REVOKE SELECT ON classsync_scheduling.published_versions "
                            f"FROM {connection.runtime}"))
        try:
            try:
                read_state(runtime)
            except DBAPIError as error:
                require(error.orig.sqlstate == "42501", "Read outage returned wrong SQLSTATE")
            else:
                raise RuntimeError("Publication read outage silently returned data")
        finally:
            with transaction(owner) as db:
                db.execute(text("GRANT SELECT ON classsync_scheduling.published_versions "
                                f"TO {connection.runtime}"))
        require(read_state(runtime) == baseline, "Read outage recovery changed exact state")
        with runtime.connect() as db:
            old_backend = db.scalar(text("SELECT pg_backend_pid()"))
        runtime.dispose()
        with runtime.connect() as db:
            require(db.scalar(text("SELECT pg_backend_pid()")) != old_backend,
                    "Reconnect reused old physical backend")
        require(read_state(runtime) == baseline, "Physical reconnect changed exact state")
        with transaction(runtime) as db:
            require(all(db.scalar(text(f"SELECT count(*) FROM classsync_scheduling.{table}")) == 0
                        for table in TABLES), "Pooled context leaked publication data")
        with transaction(owner) as db:
            draft_snapshot = text("SELECT * FROM classsync_scheduling.drafts "
                                  "ORDER BY tenant_id,owner_uid,id")
            before = db.execute(draft_snapshot).all()
            db.execute(text(f"SET LOCAL ROLE {migrator}"))
            migrate(db, target="0006_scheduling_drafts", downgrade=True)
            db.execute(text("RESET ROLE"))
            require(db.execute(draft_snapshot).all() == before,
                    "Publication downgrade changed immutable draft data")
            db.execute(text(f"SET LOCAL ROLE {migrator}"))
            migrate(db, target=MIGRATION)
        with transaction(owner) as db:
            for table in TABLES:
                db.execute(text(f"GRANT SELECT ON classsync_scheduling.{table} "
                                f"TO {connection.runtime}"))
        require(all(not rows for rows in read_state(runtime).values()),
                "Disposable downgrade/upgrade did not create empty publication state")
        return {"foundation": foundation, "solver_statuses": statuses,
                "three_owned_drafts_two_admins_same_period_collision": True,
                "database_negatives": negatives,
                "exact_snapshot_reconnect": True, "server_sequence": True,
                "same_tenant_admin_published_read": True, "force_rls_non_super_owner": True,
                "current_revocation_recovery": True, "wrong_role_uid_tenant_project_denied": True,
                "atomic_failure_rollback": True, "pooled_context_reset": True,
                "read_outage_recovery": True,
                "upgrade_downgrade_upgrade": True, "downgrade_preserves_publication_data": False,
                "application_adapter": False, "approval_acceptance": False,
                "publication_acceptance": False, "production_acceptance": False}
    finally:
        runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and not args.output.is_symlink()
            and args.output.parent.is_dir(), "New output required")
    write_new_evidence(args.output, qualify(args.bin, exercise))
    print("Publication state foundation qualification passed; owned cluster stopped")


if __name__ == "__main__":
    main()
