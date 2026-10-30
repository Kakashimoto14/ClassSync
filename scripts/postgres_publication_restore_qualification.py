"""Generated-only publication/archive restore on a new marked SSPI PostgreSQL cluster."""

import argparse
import re
from datetime import date
from pathlib import Path
from uuid import uuid4

from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import RoomRestriction
from classync_persistence.database import transaction
from classync_persistence.legacy_publication_archive import (
    LegacyPublicationError,
    import_legacy_publications,
)
from classync_persistence.memberships import identity_context
from sqlalchemy import text

from scripts.postgres_academic_restore_qualification import (
    check_connection,
    check_empty_target,
    create_target,
    owned_root,
    restore_toc,
)
from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_publication_repository_qualification import (
    MIGRATION,
    academic_store,
    authorize_grants,
    enrolled_projection_fixture,
    legacy_archive_probe,
    must_fail,
    prepare_source,
    projection_membership_fixture,
    publication_read_context_denials,
    publish_command,
    repository,
    saved_draft,
)
from scripts.postgres_restore_qualification import digest, restore_name, restored_engine
from scripts.postgres_scheduling_restore_qualification import (
    DATA_TABLES as FOUNDATION_TABLES,
)
from scripts.postgres_scheduling_restore_qualification import (
    SCHEMA_NAMES,
    catalog_queries,
    check_source_scope,
    expect_sqlstate,
    owned_file_hash,
)
from scripts.postgres_web_session_qualification import write_new_evidence

PUBLICATION_TABLES = tuple("classsync_scheduling." + name for name in (
    "published_versions", "publication_heads", "room_restrictions", "restriction_audit",
    "legacy_publication_archive",
))
TABLES = (*FOUNDATION_TABLES, *PUBLICATION_TABLES)
ARCHIVE = "classsync_scheduling.legacy_publication_archive"


def checked_toc(listing):
    for descriptor in ("TABLE", "TABLE DATA"):
        tables = [f"{match[1]}.{match[2]}" for line in listing.splitlines()
                  if (match := re.fullmatch(r"\d+; \d+ \d+ " + descriptor
                                            + r" (\S+) (\S+) \S+", line))]
        require(len(tables) == len(TABLES) + 1
                and set(tables) == {*TABLES, "public.alembic_version"},
                "Publication archive table/data manifest mismatch")
    schemas = [match[1] for line in listing.splitlines() if (match := re.fullmatch(
        r"\d+; \d+ \d+ SCHEMA - (\S+) \S+", line))]
    require(len(schemas) == 4 and set(schemas) == {"public", *SCHEMA_NAMES},
            "Publication archive namespace manifest mismatch")
    return restore_toc(listing)


def fingerprint(engine):
    queries = catalog_queries() | {
        "version_capacity": "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='alembic_version' "
            "AND column_name='version_num'",
        "sequences": "SELECT n.nspname,c.relname,pg_get_userbyid(c.relowner),s.seqstart,"
            "s.seqincrement,s.seqmax,s.seqmin,s.seqcache,s.seqcycle FROM pg_sequence s "
            "JOIN pg_class c ON c.oid=s.seqrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='classsync_scheduling' ORDER BY 1,2",
        "sequence_acl": "SELECT c.relname,pg_get_userbyid(a.grantor),a.grantee,"
            "a.privilege_type,a.is_grantable FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL "
            "aclexplode(coalesce(c.relacl,acldefault('S',c.relowner))) a "
            "WHERE n.nspname='classsync_scheduling' AND c.relkind='S' ORDER BY 1,2,3,4,5",
    }
    with transaction(engine) as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        data = {table: db.scalar(text("SELECT coalesce(jsonb_agg(to_jsonb(t) "
                    f"ORDER BY to_jsonb(t)::text),'[]') FROM {table} t")) for table in TABLES}
        sequence = list(db.execute(text("SELECT last_value,is_called FROM "
            "classsync_scheduling.published_versions_sequence_seq")).one())
        catalog = {key: [list(row) for row in db.execute(text(sql))]
                   for key, sql in queries.items()}
    require(catalog["migration"] == [[MIGRATION]] and catalog["version_capacity"] == [[128]],
            "Publication restore migration/capacity mismatch")
    require({f"{row[0]}.{row[1]}" for row in catalog["tables"]} == set(TABLES)
            and all(row[3] and row[4] for row in catalog["tables"]),
            "Publication restore table/FORCE RLS mismatch")
    return {"data": data, "sequence": sequence, "catalog": catalog}


def summary(value):
    return {"data_sha256": digest(value["data"]), "sequence": value["sequence"],
            "catalog_parts": {key: digest(rows) for key, rows in value["catalog"].items()},
            "rows": {key: len(rows) for key, rows in value["data"].items()}}


def exercise(connection):
    root = owned_root(connection)
    require(connection.run_tool is not None, "Owned PostgreSQL tools required")
    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    restored_owner = restored_runtime = None
    archive = root / ("scheduling-" + uuid4().hex + ".dump")
    target = restore_name("classsync_restore_" + uuid4().hex)
    try:
        check_connection(connection, owner, "postgres")
        first, _other, migrator = prepare_source(connection, owner, runtime)
        authorize_grants(connection, owner, migrator)
        first = enrolled_projection_fixture(academic_store(runtime), first)
        draft = saved_draft(runtime, first)
        teacher = draft.generation_result.assignments[0].teacher_id
        projection_membership_fixture(owner, teacher)
        repo = repository(runtime)
        command = publish_command(draft, first)
        receipt = repo.publish(command, commit=True)
        repo.publish(publish_command(draft, first, version=1, start="2026-11-16"), commit=True)
        repo.put_restriction(RoomRestriction(
            id="restore-reservation", room_id=draft.input_snapshot.rooms[0].id,
            dataset=command.dataset, starts_at="2027-12-01T08:00:00+08:00",
            ends_at="2027-12-01T09:00:00+08:00", kind="reservation",
            reason="Generated restore fixture", expected_revision=0,
        ))
        legacy = legacy_archive_probe(connection, owner, runtime, migrator, command)
        history = repo.history(command.dataset, first.period.id)
        before = fingerprint(owner)
        require(all(before["data"][table] for table in PUBLICATION_TABLES),
                "Publication restore requires nonempty generated publication/archive/audit")
        with transaction(owner) as db:
            check_source_scope(list(db.scalars(text("SELECT nspname FROM pg_namespace "
                "WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema'"))),
                list(db.scalars(text("SELECT c.relname FROM pg_class c JOIN pg_namespace n "
                "ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' "
                "ORDER BY c.relname"))))
        common = ["--host=127.0.0.1", f"--port={connection.port}",
                  f"--username={connection.owner}", "--no-password"]
        connection.run_tool("pg_dump.exe", *common, "--dbname=postgres", "--format=custom",
            "--schema=classsync_identity", "--schema=classsync_academic",
            "--schema=classsync_scheduling", "--schema=public", f"--file={archive}")
        archive_sha = owned_file_hash(connection, archive, "dump")
        toc = root / ("scheduling-" + uuid4().hex + ".toc")
        with toc.open("x", encoding="utf-8") as output:
            output.write(checked_toc(connection.run_tool("pg_restore.exe", "--list", archive)))
        toc_sha = owned_file_hash(connection, toc, "toc")
        create_target(owner, target)
        restored_owner = restored_engine(connection, target, bootstrap=True)
        check_connection(connection, restored_owner, target)
        with transaction(restored_owner) as db:
            check_empty_target(list(db.scalars(text("SELECT nspname FROM pg_namespace "
                "WHERE nspname NOT LIKE 'pg_%' "
                "AND nspname NOT IN ('public','information_schema')"))),
                db.scalar(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n "
                "ON n.oid=c.relnamespace WHERE n.nspname='public'")))
        connection.run_tool("pg_restore.exe", *common, f"--dbname={target}", "--exit-on-error",
                            "--single-transaction", f"--use-list={toc}", archive)
        after = fingerprint(restored_owner)
        require(before == after, "Restored publication content/sequence/catalog differs")
        with transaction(restored_owner) as db:
            db.execute(text(f"REVOKE ALL ON DATABASE {target} FROM PUBLIC"))
            db.execute(text(f"GRANT CONNECT ON DATABASE {target} TO {connection.runtime}"))
        restored_runtime = restored_engine(connection, target)
        restored = repository(restored_runtime)
        require(restored.history(command.dataset, first.period.id) == history,
                "Restored history differs")
        require(restored.publish(command, commit=True) == receipt,
                "Restored exact replay receipt differs")
        require(restored.drafts.get(draft.id) == draft, "Restored owned immutable draft differs")
        for role, uid, field, record in (("administrator", "uid-admin", "uid", "uid-admin"),
                ("student", "uid-student", "student_id", "student-a"),
                ("teacher", "uid-teacher", "faculty_id", teacher)):
            view = {"role": role, "uid": uid, field: record}
            expected = repository(runtime, uid=uid).calendar("tenant-a", command.dataset,
                first.period.id, date(2026, 10, 1), date(2026, 10, 31), view)
            require(repository(restored_runtime, uid=uid).calendar("tenant-a", command.dataset,
                first.period.id, date(2026, 10, 1), date(2026, 10, 31), view) == expected,
                "Restored role calendar differs")
        publication_read_context_denials(restored_runtime)
        must_fail(lambda: repository(restored_runtime, uid="uid-admin-other").drafts.get(draft.id),
                  "draft_not_found", 404)
        archived = after["data"][ARCHIVE][0]
        legacy_row = {"sequence": archived["source_sequence"], "id": archived["legacy_id"],
            "tenant": archived["source_tenant"], "actor": archived["source_actor"],
            **{key: archived[key] for key in ("dataset", "period_id", "revision", "draft_id",
                "created_at", "idempotency_key", "request_hash", "payload", "checksum")}}
        args = dict(tenant_id="tenant-a", firebase_project_id="synthetic-project",
            principal=VerifiedPrincipal(uid="uid-admin"),
            source_fingerprint=archived["source_fingerprint"], rows=[legacy_row],
            owner_map={(archived["source_tenant"], archived["source_actor"]):
                       (archived["tenant_id"], archived["owner_uid"])})
        require(import_legacy_publications(restored_runtime, **args) == 0,
                "Restored archive exact retry inserted data")
        try:
            import_legacy_publications(restored_runtime, **(args | {
                "rows": [legacy_row | {"request_hash": "0" * 64}],
            }))
        except LegacyPublicationError:
            pass
        else:
            raise RuntimeError("Restored archive accepted changed historical evidence")
        for tenant, uid, project in (("tenant-a", "uid-student", "synthetic-project"),
                ("tenant-a", "uid-teacher", "synthetic-project"),
                ("tenant-a", "missing", "synthetic-project"),
                ("tenant-b", "uid-admin", "synthetic-project"),
                ("tenant-a", "uid-admin", "wrong-project")):
            with transaction(restored_runtime) as db:
                identity_context(db, tenant_id=tenant, uid=uid)
                db.execute(text("SELECT set_config('classsync.project_id',:project,true)"),
                           {"project": project})
                require(db.scalar(text(f"SELECT count(*) FROM {ARCHIVE}")) == 0,
                        "Restored archive exposed private evidence")
        for table in ("published_versions", "legacy_publication_archive", "restriction_audit"):
            expect_sqlstate(restored_owner,
                f"UPDATE classsync_scheduling.{table} SET revision=revision", {}, "42501")
        with transaction(restored_runtime) as db:
            for table in ("published_versions", "legacy_publication_archive"):
                require(not db.scalar(text(
                    "SELECT has_table_privilege(current_user,:table,'UPDATE')"),
                    {"table": "classsync_scheduling." + table}), "Restored runtime mutation grant")
        restored_runtime.dispose()
        require(restored.history(command.dataset, first.period.id) == history,
                "Restored reconnect changed history")
        require(fingerprint(restored_owner) == after and fingerprint(owner) == before,
                "Restore behavior changed generated source or restored immutable state")
        owned_file_hash(connection, archive, "dump", archive_sha)
        owned_file_hash(connection, toc, "toc", toc_sha)
        return {"migration": MIGRATION, "archive_sha256": archive_sha, "toc_sha256": toc_sha,
            "source_fingerprint": summary(before), "restored_fingerprint": summary(after),
            "legacy_source_evidence": legacy, "legacy_current": False, "legacy_replayable": False,
            "complete_content_catalog_sequence_equal": True, "exact_history_and_receipt": True,
            "role_calendars_context_denials_private_draft": True,
            "archive_hash_payload_mapping_and_exact_retry": True,
            "restored_immutability_acl_and_reconnect": True, "source_and_restore_unchanged": True,
            "restored_database": target, "same_cluster_generated_only": True,
            "cross_host_disaster_recovery": False, "production_acceptance": False}
    finally:
        for engine in (restored_runtime, restored_owner, runtime, owner):
            if engine is not None:
                engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and not args.output.is_symlink()
            and args.output.parent.is_dir(), "New evidence output required")
    write_new_evidence(args.output, qualify(args.bin, exercise))
    print("Publication/archive backup and restore passed; owned cluster stopped")


if __name__ == "__main__":
    main()
