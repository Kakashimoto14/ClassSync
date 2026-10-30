"""Qualify Alembic capacity and archive schema on a fresh SSPI-only disposable cluster."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from classync_contracts.identity import MembershipAuthorizationError, VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.legacy_publication_archive import import_legacy_publications
from classync_persistence.memberships import identity_context
from classync_persistence.schema import migrate
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import seed
from scripts.postgres_web_session_qualification import write_new_evidence

PRIOR = "0008_publication_transactions"
FIRST_LONG = "0009_publication_record_projection"
HEAD = "0011_publication_policy_cycle"
ARCHIVE = "classsync_scheduling.legacy_publication_archive"


def sql_failure(db, sql, params, expected):
    try:
        with db.begin_nested():
            db.execute(text(sql), params)
    except DBAPIError as error:
        require(error.orig.sqlstate == expected, f"Expected SQLSTATE {expected}")
    else:
        raise RuntimeError(f"Expected SQLSTATE {expected} but statement succeeded")


def archive_gate(connection, owner, role):
    """Verify generated archive data, ownership, ACLs, RLS and retained evidence."""
    runtime = engine_for(connection)
    payload = json.dumps({"draft": {"id": "draft-a", "period_id": "term-a",
                                    "creator": "source-admin"}, "calendar": {}})
    row = dict(sequence=1, id="archive-a", tenant="source-tenant", dataset="synthetic",
               period_id="term-a", revision=1, draft_id="draft-a", actor="source-admin",
               created_at="2026-10-29T00:00:00+08:00", idempotency_key="archive-command-a",
               request_hash="a" * 64, payload=payload,
               checksum=hashlib.sha256(payload.encode()).hexdigest())
    arguments = dict(tenant_id="tenant-a", firebase_project_id="synthetic-project",
                     principal=VerifiedPrincipal(uid="uid-admin"), source_fingerprint="b" * 64,
                     rows=[row], owner_map={("source-tenant", "source-admin"):
                                           ("tenant-a", "uid-admin")})
    try:
        with transaction(owner) as db:
            seed(db)
            for namespace in ("classsync_identity", "classsync_academic", "classsync_scheduling"):
                require(db.scalar(text("SELECT pg_get_userbyid(nspowner) FROM pg_namespace "
                                       "WHERE nspname=:namespace"), {"namespace": namespace})
                        == role, "Schema migration ownership mismatch")
                require(not db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_namespace n, "
                    "LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a "
                    "WHERE n.nspname=:namespace AND a.grantee=0)"), {"namespace": namespace}),
                    "PUBLIC schema privileges found")
                require(not db.scalar(text("SELECT has_schema_privilege(:runtime,:ns,'CREATE')"),
                        {"runtime": connection.runtime, "ns": namespace}),
                        "Runtime has schema CREATE")
            catalog = db.execute(text("SELECT pg_get_userbyid(relowner),relrowsecurity,"
                                      "relforcerowsecurity FROM pg_class "
                                      "WHERE oid=CAST(:t AS regclass)"),
                                 {"t": ARCHIVE}).one()
            require(tuple(catalog) == (role, True, True), "Archive ownership/RLS mismatch")
            require(db.scalar(text("SELECT count(*) FROM pg_constraint WHERE "
                "conrelid=CAST(:t AS regclass) AND contype='f' AND convalidated"), {"t": ARCHIVE})
                == 2, "Archive cross-schema foreign keys missing")
            require(not db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace, LATERAL "
                "aclexplode(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' "
                "THEN 'S'::\"char\" ELSE 'r'::\"char\" END,c.relowner))) a "
                "WHERE n.nspname LIKE 'classsync_%' AND c.relkind IN ('r','S') "
                "AND a.grantee=0)")), "PUBLIC table or sequence privileges found")
            require(not db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_class c "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE "
                "n.nspname LIKE 'classsync_%' AND c.relkind IN ('r','S') "
                "AND pg_get_userbyid(c.relowner)<>:role)"), {"role": role}),
                "Table/sequence migration ownership mismatch")
            require(not db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid=p.pronamespace WHERE "
                "n.nspname LIKE 'classsync_%' AND (pg_get_userbyid(p.proowner)<>:role "
                "OR (p.prosecdef AND NOT (coalesce(p.proconfig,ARRAY[]::text[]) "
                "@> ARRAY['search_path=pg_catalog']))))"), {"role": role}),
                "Function owner or SECURITY DEFINER search path mismatch")
            require(not db.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_proc p "
                "JOIN pg_namespace n ON n.oid=p.pronamespace, LATERAL "
                "aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a "
                "WHERE n.nspname LIKE 'classsync_%' AND a.grantee=0)")),
                "PUBLIC function execution privileges found")
            for namespace in ("classsync_identity", "classsync_scheduling"):
                db.execute(text(f"GRANT USAGE ON SCHEMA {namespace} TO {connection.runtime}"))
            db.execute(text("GRANT SELECT ON classsync_identity.tenants,"
                            f"classsync_identity.memberships TO {connection.runtime}"))
            db.execute(text(f"GRANT SELECT,INSERT ON {ARCHIVE} TO {connection.runtime}"))
            db.execute(text("GRANT EXECUTE ON FUNCTION classsync_scheduling."
                            f"lock_publication_authority() TO {connection.runtime}"))
        require(import_legacy_publications(runtime, **arguments) == 1, "Archive insert failed")
        require(import_legacy_publications(runtime, **arguments) == 0, "Exact retry changed data")
        for overrides in ({"tenant_id": "tenant-b", "owner_map": {
                ("source-tenant", "source-admin"): ("tenant-b", "uid-admin")}},
                {"principal": VerifiedPrincipal(uid="missing")},
                {"principal": VerifiedPrincipal(uid="uid-a")},
                {"firebase_project_id": "wrong-project"}):
            try:
                import_legacy_publications(runtime, **(arguments | overrides))
            except MembershipAuthorizationError:
                pass
            else:
                raise RuntimeError("Invalid archive identity was authorized")
        with transaction(owner) as db:
            stored = dict(db.execute(text(f"SELECT * FROM {ARCHIVE}")).mappings().one())
        with transaction(runtime) as db:
            require(db.scalar(text(f"SELECT count(*) FROM {ARCHIVE}")) == 0,
                    "Missing identity exposed archive")
            names = list(stored)
            sql_failure(db, f"INSERT INTO {ARCHIVE} ({','.join(names)}) VALUES "
                        f"({','.join(':'+name for name in names)})", stored, "42501")
            sql_failure(db, f"UPDATE {ARCHIVE} SET owner_uid=owner_uid", {}, "42501")
            sql_failure(db, "CREATE TABLE classsync_scheduling.runtime_probe(id int)",
                        {}, "42501")
            for tenant, uid, project in (("tenant-b", "uid-admin", "synthetic-project"),
                                          ("tenant-a", "missing", "synthetic-project"),
                                          ("tenant-a", "uid-a", "synthetic-project"),
                                          ("tenant-a", "uid-admin", "wrong-project")):
                identity_context(db, tenant_id=tenant, uid=uid)
                db.execute(text("SELECT set_config('classsync.project_id',:project,true)"),
                           {"project": project})
                require(db.scalar(text(f"SELECT count(*) FROM {ARCHIVE}")) == 0,
                        "Wrong tenant/UID/project exposed archive")
                sql_failure(db, f"INSERT INTO {ARCHIVE} ({','.join(names)}) VALUES "
                            f"({','.join(':'+name for name in names)})", stored, "42501")
        with transaction(owner) as db:
            # Copy generated archive rows only; invalid targets/checksum must fail.
            columns = "source_fingerprint,source_tenant,source_actor,legacy_id,source_sequence,"
            columns += "tenant_id,owner_uid,dataset,period_id,revision,draft_id,created_at,"
            columns += "idempotency_key,request_hash,payload,checksum"
            selection = columns.replace("legacy_id", "legacy_id||'-invalid'").replace(
                "source_sequence", "source_sequence+1").replace(
                "idempotency_key", "idempotency_key||'-invalid'")
            for field, invalid, state in (("owner_uid", "'missing'", "23503"),
                                          ("checksum", "repeat('0',64)", "23514")):
                sql_failure(db, f"INSERT INTO {ARCHIVE} ({columns}) SELECT "
                            f"{selection.replace(field, invalid)} FROM {ARCHIVE}", {}, state)
            for calendar in ("missing", None, "scalar", []):
                malformed = json.loads(payload)
                if calendar == "missing":
                    del malformed["calendar"]
                else:
                    malformed["calendar"] = calendar
                invalid_payload = json.dumps(malformed)
                values = selection.replace("payload", ":invalid_payload").replace(
                    "checksum", ":invalid_checksum")
                params = {"invalid_payload": invalid_payload,
                          "invalid_checksum": hashlib.sha256(invalid_payload.encode()).hexdigest()}
                sql_failure(db, f"INSERT INTO {ARCHIVE} ({columns}) SELECT {values} "
                            f"FROM {ARCHIVE}", params, "23514")
            sql_failure(db, f"UPDATE {ARCHIVE} SET revision=revision+1", {}, "42501")
            sql_failure(db, f"TRUNCATE {ARCHIVE}", {}, "42501")
        try:
            with transaction(owner) as db:
                db.execute(text(f"SET LOCAL ROLE {role}"))
                migrate(db, target=FIRST_LONG, downgrade=True)
        except DBAPIError as error:
            require(error.orig.sqlstate == "55000", "Wrong retained-archive downgrade error")
        else:
            raise RuntimeError("Downgrade discarded retained evidence")
        with transaction(owner) as db:
            version(db, HEAD, 128)
            require(db.scalar(text(f"SELECT count(*) FROM {ARCHIVE}")) == 1,
                    "Denied operations changed archive")
        return {"canonical_schema_ownership_acl_rls": True, "cross_schema_fk_checks": True,
                "current_admin_import_and_replay": True, "denied_identity_contexts": True,
                "runtime_create_update_denied": True, "immutability": True,
                "nonempty_downgrade_preserves_data_and_revision": True}
    finally:
        runtime.dispose()


def version(db, expected, capacity):
    require(db.scalar(text("SELECT version_num FROM public.alembic_version")) == expected,
            "Unexpected Alembic revision")
    require(db.scalar(text("SELECT character_maximum_length FROM information_schema.columns "
                          "WHERE table_schema='public' AND table_name='alembic_version' "
                          "AND column_name='version_num'")) == capacity,
            "Unexpected version column capacity")


def exercise(connection):
    owner = engine_for(connection, bootstrap=True)
    role = "classsync_migrator_" + uuid4().hex
    try:
        with transaction(owner) as db:
            db.execute(text(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS"))
            db.execute(text(f"GRANT CREATE ON DATABASE postgres TO {role}"))
            db.execute(text(f"GRANT USAGE,CREATE ON SCHEMA public TO {role}"))
            db.execute(text(f"SET LOCAL ROLE {role}"))
            migrate(db, target=PRIOR)
            version(db, PRIOR, 32)
            # Reproduce Alembic's failed stamp in a SAVEPOINT, preserving 0008.
            try:
                with db.begin_nested():
                    db.execute(text("UPDATE public.alembic_version SET version_num=:revision "
                                    "WHERE version_num=:prior"),
                               {"revision": FIRST_LONG, "prior": PRIOR})
            except DBAPIError as error:
                require(error.orig.sqlstate == "22001", "Wrong truncation SQLSTATE")
            else:
                raise RuntimeError("32-character version column unexpectedly accepted 0009")
            version(db, PRIOR, 32)
        # Widening, policy DDL and version stamp must all roll back together.
        try:
            with transaction(owner) as db:
                db.execute(text(f"SET LOCAL ROLE {role}"))
                migrate(db, target=FIRST_LONG)
                version(db, FIRST_LONG, 128)
                raise ValueError("generated migration rollback")
        except ValueError as error:
            require(str(error) == "generated migration rollback", "Unexpected rollback error")
        with transaction(owner) as db:
            db.execute(text(f"SET LOCAL ROLE {role}"))
            version(db, PRIOR, 32)
            migrate(db, target=FIRST_LONG)
            version(db, FIRST_LONG, 128)
            sql_failure(db, "CREATE TABLE classync_scheduling.regression_probe(id int)",
                        {}, "3F000")
            try:
                with db.begin_nested():
                    migrate(db, target=HEAD)
                    raise ValueError("generated archive rollback")
            except ValueError as error:
                require(str(error) == "generated archive rollback", "Wrong rollback error")
            version(db, FIRST_LONG, 128)
            require(db.scalar(text("SELECT to_regclass(:t)"), {"t": ARCHIVE}) is None,
                    "Failed archive migration left a table behind")
            migrate(db, target=HEAD)
            version(db, HEAD, 128)
        with transaction(owner) as db:
            db.execute(text(f"SET LOCAL ROLE {role}"))
            migrate(db, target=PRIOR, downgrade=True)
            version(db, PRIOR, 128)
            migrate(db, target=HEAD)
            version(db, HEAD, 128)
            migrate(db, target="base", downgrade=True)
            require(db.scalar(text("SELECT count(*) FROM public.alembic_version")) == 0,
                    "Base downgrade retained a revision")
            # Remove only the empty generated version table to exercise creation
            # with Alembic's default width on the clean base-to-head path.
            db.execute(text("DROP TABLE public.alembic_version"))
            migrate(db, target=HEAD)
            version(db, HEAD, 128)
        archive = archive_gate(connection, owner, role)
        return {"exact_22001_reproduced": True, "exact_3F000_reproduced": True,
                "archive_migration_injected_failure_rollback": True,
                "archive": archive, "incremental_0008_0009_head": True,
                "widening_and_stamp_transactional_rollback": True,
                "downgrade_retains_capacity_and_reupgrade": True,
                "clean_base_to_head": True, "nonprivileged_migration_owner": True}
    finally:
        owner.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink()
            and args.output.parent.is_dir(), "New evidence output required")
    write_new_evidence(args.output, qualify(args.bin, exercise))
    print("Migration-chain qualification passed; owned cluster stopped")


if __name__ == "__main__":
    main()
