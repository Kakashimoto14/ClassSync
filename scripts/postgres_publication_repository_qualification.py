"""Actual generated-only PostgreSQL publication repository qualification.

New marked SSPI cluster only. No originals, HTTP/provider adoption, approval,
outbox, enrollment authority, deployment or production acceptance is represented.
"""

import argparse
import hashlib
import json
import sqlite3
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch
from uuid import UUID, uuid4

from classync_contracts.academic import CalendarWrite, RecordWrite
from classync_contracts.identity import MembershipAuthorizationError, VerifiedPrincipal
from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_contracts.scheduling import Enrollment, SaveDraftRequest
from classync_persistence.database import postgres_engine, transaction
from classync_persistence.legacy_publication_archive import (
    LegacyPublicationError,
    import_legacy_publications,
)
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from classync_persistence.schema import migrate
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from scripts.postgres_academic_repository_qualification import FixtureCalls
from scripts.postgres_academic_restore_qualification import prepare_source
from scripts.postgres_academic_restore_qualification import store as academic_store
from scripts.postgres_disposable import checked_root, qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_publication_state_qualification import INSERT_VERSION
from scripts.postgres_web_session_qualification import write_new_evidence
from services.academic.tests.test_academic import complete
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_rules import DraftError, digest, encode, verified_result
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository
from services.scheduling.tests.test_calendar import configuration

MIGRATION = "0011_publication_policy_cycle"
TABLES = ("solver_runs", "drafts", "published_versions", "publication_heads", "room_restrictions",
          "restriction_audit", "legacy_publication_archive")


def checked_connection(connection):
    return checked_root(connection.root, Path(tempfile.gettempdir()))


def bounded_runtime(connection):
    parameters = connection.parameters()
    url = URL.create("postgresql+psycopg", username=parameters["user"], host=parameters["host"],
                     port=parameters["port"], database=parameters["dbname"])
    return postgres_engine(url, connect_args=parameters, pool_size=5, max_overflow=0,
                           pool_timeout=3)


def check_pool(engine, *, exhausted=False):
    require(engine.pool.size() == 5 and engine.pool._max_overflow == 0
            and engine.pool.timeout() == 3
            and (not exhausted or engine.pool.checkedout() == 5),
            "Qualification runtime pool differs from bounded provider pool")


def validate_helper_catalog(row, migrator):
    require(row["owner"] == migrator and row["security_definer"] is True
            and row["arguments"] == 0 and row["result_type"] == "boolean"
            and row["configuration"] == ["search_path=pg_catalog"]
            and row["superuser"] is False and row["bypass_rls"] is False,
            "Authority helper catalog differs from constrained nonprivileged definer")


def identity_state(owner):
    with transaction(owner) as db:
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        return {table: db.scalar(text(
            "SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') "
            f"FROM classsync_identity.{table} t"
        )) for table in ("tenants", "memberships", "membership_audit")}


def direct_authority_helper(connection, owner, runtime, migrator):
    with transaction(owner) as db:
        row = db.execute(text("""
            SELECT pg_get_userbyid(p.proowner) AS owner,p.prosecdef AS security_definer,
                p.pronargs AS arguments,p.prorettype::regtype::text AS result_type,
                p.proconfig AS configuration,r.rolsuper AS superuser,r.rolbypassrls AS bypass_rls
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_roles r ON r.oid=p.proowner
            WHERE n.nspname='classsync_scheduling' AND p.proname='lock_publication_authority'
        """)).mappings().one()
        validate_helper_catalog(row, migrator)
        require(db.scalar(text("""
            SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
            WHERE n.nspname='classsync_scheduling' AND a.grantee=0
        """)) == 0, "PUBLIC has scheduling function privileges")
        for function, allowed in (("lock_publication_authority", True),
                                  ("audit_room_restriction", False),
                                  ("guard_room_restriction", False)):
            require(db.scalar(text("SELECT has_function_privilege(:role,:function,'EXECUTE')"),
                       {"role": connection.runtime,
                        "function": "classsync_scheduling." + function + "()"}) is allowed,
                    "Runtime authority helper or trigger execution privilege differs")
    before = identity_state(owner)
    contexts = [
        ("no_context", None, None, None),
        ("student", "tenant-a", "uid-student", "synthetic-project"),
        ("teacher", "tenant-a", "uid-teacher", "synthetic-project"),
        ("missing_uid", "tenant-a", "missing", "synthetic-project"),
        ("wrong_tenant", "tenant-b", "uid-admin", "synthetic-project"),
        ("wrong_project", "tenant-a", "uid-admin", "wrong-project"),
    ]
    for label, tenant, uid, project in contexts:
        with transaction(runtime) as denied:
            if tenant is not None:
                identity_context(denied, tenant_id=tenant, uid=uid)
                denied.execute(text("SELECT set_config('classsync.project_id',:project,true)"),
                               {"project": project})
            require(denied.scalar(text("SELECT classsync_scheduling.lock_publication_authority()"))
                    is False, f"Denied authority helper context returned a grant: {label}")
            # A false return must not leave authority rows locked. These actual
            # updates/audit inserts occur only in a transaction explicitly rolled back.
            try:
                with transaction(owner) as probe:
                    probe.execute(text("SET LOCAL lock_timeout='250ms'"))
                    probe.execute(text("UPDATE classsync_identity.tenants "
                                       "SET firebase_project_id=firebase_project_id"))
                    if uid in {"uid-student", "uid-teacher", "uid-admin"} and tenant == "tenant-a":
                        identity_context(probe, tenant_id="tenant-a", uid=uid)
                        audit_actor(probe, VerifiedPrincipal(uid="synthetic-helper-probe"))
                        probe.execute(text("UPDATE classsync_identity.memberships "
                                           "SET revision=revision+1 "
                                           "WHERE tenant_id='tenant-a' AND uid=:uid"), {"uid": uid})
                    raise ValueError("generated denied-helper lock probe rollback")
            except ValueError as error:
                require(str(error) == "generated denied-helper lock probe rollback",
                        "Unexpected denied-helper probe exception")
    with transaction(runtime) as db:
        identity_context(db, tenant_id="tenant-a", uid="uid-admin")
        db.execute(text("SELECT set_config('classsync.project_id','synthetic-project',true)"))
        require(db.scalar(text("SELECT classsync_scheduling.lock_publication_authority()")) is True,
                "Current active Administrator helper control was denied")
    require(identity_state(owner) == before,
            "Direct helper probes changed identity or immutable audit")
    return {"denied_contexts": [entry[0] for entry in contexts], "valid_admin_control": True,
            "denied_contexts_take_no_authority_row_locks": True,
            "nonprivileged_noargs_fixed_path_definer": True,
            "public_and_runtime_function_acl_checked": True, "identity_and_audit_unchanged": True}


def verify_fresh_target(db, connection, root):
    observed = db.execute(text("SELECT current_setting('data_directory'),current_user,"
                               "inet_server_port(),host(inet_server_addr())")).one()
    require(Path(observed[0]).resolve() == root / "data"
            and tuple(observed[1:]) == (connection.owner, connection.port, "127.0.0.1"),
            "Publication repository target binding mismatch")
    namespaces = db.execute(text("SELECT nspname FROM pg_namespace "
                                 "WHERE nspname !~ '^pg_' AND nspname<>'information_schema' "
                                 "ORDER BY nspname")).scalars().all()
    tables = db.scalar(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n "
                           "ON n.oid=c.relnamespace WHERE n.nspname='public' "
                           "AND c.relkind IN ('r','p','v','m','f')"))
    require(namespaces == ["public"] and tables == 0,
            "Publication repository qualification requires a new empty cluster")


def repository(engine, *, uid="uid-admin", tenant="tenant-a", project="synthetic-project"):
    return PostgresPublicationRepository(engine, tenant_id=tenant, firebase_project_id=project,
                                         principal=VerifiedPrincipal(uid=uid))


def must_fail(operation, code, status=None):
    try:
        operation()
    except (DraftError, MembershipAuthorizationError) as error:
        require(error.code == code and (status is None or error.status == status),
                f"Wrong publication negative result: {error.code}")
    else:
        raise RuntimeError(f"Publication negative path unexpectedly succeeded: {code}")


def state(owner):
    with transaction(owner) as db:
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        return {table: db.scalar(text(
            "SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') "
            f"FROM classsync_scheduling.{table} t"
        )) for table in TABLES}


def authorize_grants(connection, owner, migrator):
    # The failed bootstrap upgrade must roll back even the preceding 0006/0007 DDL.
    try:
        with transaction(owner) as db:
            migrate(db, target=MIGRATION)
            raise RuntimeError("Privileged migration owner unexpectedly accepted")
    except DBAPIError as error:
        require(error.orig.sqlstate == "42501", "Wrong privileged migration rejection SQLSTATE")
    with transaction(owner) as db:
        require(db.scalar(text("SELECT version_num FROM public.alembic_version"))
                == "0005_academic_records"
                and db.scalar(text("SELECT to_regnamespace('classsync_scheduling')")) is None,
                "Rejected privileged upgrade left partial schema or revision behind")
    with transaction(owner) as db:
        db.execute(text(f"SET LOCAL ROLE {migrator}"))
        migrate(db, target=MIGRATION)
    with transaction(owner) as db:
        require(db.scalar(text("SELECT version_num FROM public.alembic_version")) == MIGRATION,
                "Publication repository migration scope drift")
        db.execute(text(f"GRANT USAGE ON SCHEMA classsync_scheduling TO {connection.runtime}"))
        for table in ("solver_runs", "drafts", "published_versions"):
            db.execute(text(f"GRANT SELECT,INSERT ON classsync_scheduling.{table} "
                            f"TO {connection.runtime}"))
        for table in ("publication_heads", "room_restrictions"):
            db.execute(text(f"GRANT SELECT,INSERT,UPDATE ON classsync_scheduling.{table} "
                            f"TO {connection.runtime}"))
        db.execute(text("GRANT SELECT ON classsync_scheduling.restriction_audit "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT SELECT,INSERT ON classsync_scheduling.legacy_publication_archive "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT USAGE,SELECT ON SEQUENCE "
                        "classsync_scheduling.published_versions_sequence_seq "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT EXECUTE ON FUNCTION classsync_scheduling."
                        f"lock_publication_authority() TO {connection.runtime}"))
        require(not db.scalar(text("SELECT has_table_privilege(:role,"
                    "'classsync_identity.memberships','UPDATE')"), {"role": connection.runtime})
                and not db.scalar(text("SELECT has_table_privilege(:role,"
                    "'classsync_scheduling.restriction_audit','INSERT')"),
                    {"role": connection.runtime})
                and not db.scalar(text("SELECT has_table_privilege(:role,"
                    "'classsync_scheduling.legacy_publication_archive','UPDATE')"),
                    {"role": connection.runtime})
                and not db.scalar(text("SELECT has_table_privilege(:role,"
                    "'classsync_scheduling.legacy_publication_archive','DELETE')"),
                    {"role": connection.runtime}),
                "Runtime received identity, audit or archive mutation grant")


def enrolled_projection_fixture(academic, snapshot):
    """Save generated enrollment before solver hashing, never decorate a draft."""
    sections = sorted(entry.record.id for entry in snapshot.records
                      if entry.record.kind == "sections" and entry.record.active)
    require(len(sections) == 2, "Projection fixture requires two distinct sections")
    enrollments = []
    for student, section in zip(("student-a", "student-other"), sections, strict=True):
        offerings = sorted(entry.record.id for entry in snapshot.records
                           if entry.record.kind == "offerings" and entry.record.active
                           and entry.record.section_id == section)
        require(offerings, "Projection fixture section has no active offerings")
        enrollments.append(Enrollment(student_id=student, offering_ids=offerings))
    rules = next(entry for entry in snapshot.records if entry.record.kind == "constraints")
    return academic.save(snapshot.period.id, "constraints", rules.record.id, RecordWrite(
        expected_revision=rules.revision,
        record=rules.record.model_copy(update={"enrollments": enrollments}),
    ))


def projection_membership_fixture(owner, teacher_id):
    """Link only this disposable cluster's identities to its generated records."""
    with transaction(owner) as db:
        for student in ("student-other", "student-unassigned"):
            db.execute(text("INSERT INTO classsync_identity.students VALUES "
                            "('tenant-a',:id,'person-a')"), {"id": student})
            identity_context(db, tenant_id="tenant-a", uid="uid-" + student)
            audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
            db.execute(text("INSERT INTO classsync_identity.memberships VALUES "
                "('tenant-a',:uid,'person-a',:student,NULL,ARRAY['student'],'active',1)"),
                {"uid": "uid-" + student, "student": student})
        db.execute(text("INSERT INTO classsync_identity.faculty VALUES "
                        "('tenant-a',:id,'person-a')"), {"id": teacher_id})
        identity_context(db, tenant_id="tenant-a", uid="uid-teacher")
        audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
        db.execute(text("UPDATE classsync_identity.memberships SET faculty_id=:id, "
                        "revision=revision+1 WHERE tenant_id='tenant-a' AND uid='uid-teacher'"),
                   {"id": teacher_id})


def saved_draft(runtime, snapshot, *, uid="uid-admin"):
    ready = academic_readiness(snapshot)
    require(ready.ready and ready.inputs is not None, "Generated academic fixture is not ready")
    result = generate_week(ready.inputs)
    verified_result(ready.inputs, result)
    drafts = PostgresDraftRepository(runtime, tenant_id="tenant-a",
        firebase_project_id="synthetic-project", principal=VerifiedPrincipal(uid=uid))
    drafts.remember_run(ready.inputs, result)
    draft, created = drafts.save(SaveDraftRequest(
        run_id=result.run_id, input_hash=result.input_hash,
        title="Generated publication qualification",
        idempotency_key="qualification-save-" + uuid4().hex,
    ))
    require(created and drafts.get(draft.id) == draft, "Generated immutable draft changed")
    return draft


def publish_command(draft, snapshot, *, version=0, start=None):
    calendar = snapshot.period.calendar.model_copy(deep=True)
    if start:
        calendar.effective_start = date.fromisoformat(start)
        calendar.phases = []
    return PublicationCommand(
        draft_id=draft.id,
        dataset="synthetic" if draft.input_snapshot.synthetic else "institutional",
        expected_version=version, expected_academic_revision=snapshot.period.revision,
        idempotency_key="qualification-publish-" + uuid4().hex, calendar=calendar,
    )


def wait_for_locks(owner, *, runtime=None, application=None, count=1):
    require((runtime is None) != (application is None), "One lock observation scope required")
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        with transaction(owner) as db:
            observed = db.scalar(text("SELECT count(*) FROM pg_stat_activity "
                "WHERE wait_event_type='Lock' AND "
                + ("usename=:value" if runtime else "application_name=:value")),
                {"value": runtime or application})
        if observed == count:
            return observed
        time.sleep(0.02)
    raise RuntimeError(f"Did not observe {count} competing PostgreSQL lock waiters")


def competing_publications(connection, owner, runtime, repo, draft, snapshot, version):
    commands = [publish_command(draft, snapshot, version=version, start=start)
                for start in ("2026-12-07", "2026-12-14")]
    gate = Barrier(3)

    def publish(body):
        gate.wait(timeout=10)
        try:
            return "published", repo.publish(body, commit=True)
        except DraftError as error:
            return "denied", {"status": error.status, "code": error.code}

    with ThreadPoolExecutor(max_workers=2) as pool:
        with transaction(owner) as db:
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                       {"key": encode(["classsync-publication", "tenant-a", commands[0].dataset])})
            futures = [pool.submit(publish, body) for body in commands]
            gate.wait(timeout=10)
            observed = wait_for_locks(owner, runtime=connection.runtime, count=2)
        outcomes = [future.result(timeout=20) for future in futures]
    winners = [value for outcome, value in outcomes if outcome == "published"]
    losers = [value for outcome, value in outcomes if outcome == "denied"]
    require(len(winners) == len(losers) == 1 and winners[0]["revision"] == version + 1
            and losers == [{"status": 409, "code": "publication_version_conflict"}],
            "Competing publication did not have exactly one precise winner and stale loser")
    return {"observed_waiters": observed, "winner_revision": winners[0]["revision"],
            "loser": losers[0]}


def check_writer_transition(before, after, receipt, restriction):
    for table in ("solver_runs", "drafts"):
        require(after[table] == before[table], "Writer race changed private immutable snapshots")
    for table, key in (("published_versions", "id"), ("restriction_audit", "revision")):
        old = {entry[key]: entry for entry in before[table]}
        new = {entry[key]: entry for entry in after[table]}
        require(len(new) == len(old) + 1 and all(new.get(k) == value for k, value in old.items()),
                "Writer race mutated immutable history or committed an unexpected row count")
    new_version = next(row for row in after["published_versions"] if row["id"] == receipt["id"])
    require(new_version["revision"] == receipt["revision"],
            "Writer race receipt lost exact revision")
    require(len(before["publication_heads"]) == len(after["publication_heads"]) == 1,
            "Writer race unexpectedly created another scope")
    old_head, new_head = before["publication_heads"][0], after["publication_heads"][0]
    require(new_head == old_head | {"revision": old_head["revision"] + 1}
            and new_head["revision"] == receipt["revision"], "Writer race head transition differs")
    require(len(before["room_restrictions"]) == len(after["room_restrictions"]) == 1,
            "Writer race unexpectedly created another restriction")
    old_restriction, new_restriction = before["room_restrictions"][0], after["room_restrictions"][0]
    require(new_restriction["revision"] == old_restriction["revision"] + 1
            == restriction["revision"]
            and json.loads(new_restriction["payload"]) == restriction
            and new_restriction["checksum"] == digest(new_restriction["payload"]),
            "Writer race restriction did not commit one exact checksummed revision")
    audits = sorted(after["restriction_audit"], key=lambda row: row["revision"])
    require(audits[-1]["old_snapshot"] == audits[-2]["new_snapshot"]
            and audits[-1]["new_snapshot"]["payload"] == new_restriction["payload"]
            and audits[-1]["new_snapshot"]["revision"] == restriction["revision"],
            "Writer race audit chain did not preserve the exact previous restriction")


def restriction_publication_races(connection, owner, runtime, draft, snapshot, version):
    results = []
    for first_writer, start in (("publication", "2026-12-21"), ("restriction", "2026-12-28")):
        pub_repo, room_repo = repository(runtime), repository(runtime)
        command = publish_command(draft, snapshot, version=version, start=start)
        before = state(owner)
        stored = room_repo.restriction_value(before["room_restrictions"][0])
        restriction_revision = stored.pop("revision")
        body = RoomRestriction.model_validate(stored | {
            "expected_revision": restriction_revision,
            "reason": "Generated observed writer ordering: " + first_writer,
        })
        entered, release = Event(), Event()
        first_hook_called = False
        hooked = pub_repo if first_writer == "publication" else room_repo
        method = "review_scope" if first_writer == "publication" else "expanded"
        real_method = getattr(hooked, method)

        def delegate_then_pause(*args, _delegate=real_method, _entered=entered,
                                _release=release, **kwargs):
            nonlocal first_hook_called
            result = _delegate(*args, **kwargs)
            if not first_hook_called:
                first_hook_called = True
                _entered.set()
                require(_release.wait(timeout=2.5), "Writer ordering observation gate timed out")
            return result

        def publication(bound_repo=pub_repo, bound_command=command):
            return bound_repo.publish(bound_command, commit=True)

        def restriction(bound_repo=room_repo, bound_body=body):
            return bound_repo.put_restriction(bound_body)

        with patch.object(hooked, method, side_effect=delegate_then_pause), ThreadPoolExecutor(
            max_workers=2,
        ) as pool:
            first = pool.submit(publication if first_writer == "publication" else restriction)
            try:
                require(entered.wait(timeout=3), "First writer never reached real validated scope")
                second = pool.submit(restriction if first_writer == "publication" else publication)
                observed = wait_for_locks(owner, runtime=connection.runtime, count=1)
                require(not first.done() and not second.done(),
                        "Writer race failed to hold the first transaction and observe the second")
            finally:
                release.set()
            first_result, second_result = first.result(timeout=20), second.result(timeout=20)
        receipt, saved_restriction = (
            (first_result, second_result) if first_writer == "publication"
            else (second_result, first_result)
        )
        require(receipt["status"] == "published" and receipt["revision"] == version + 1,
                "Serialized publication was not a successful exact next revision")
        after = state(owner)
        check_writer_transition(before, after, receipt, saved_restriction)
        results.append({"first_writer": first_writer, "observed_lock_waiters": observed,
                        "publication_revision": receipt["revision"],
                        "restriction_revision": saved_restriction["revision"],
                        "both_real_writers_committed_once": True,
                        "immutable_history_and_audit_prefix_unchanged": True})
        version += 1
    return results, version


def authority_lock_probe(owner, repo, *, project=False):
    tag = "classsync-authority-" + uuid4().hex[:20]

    def mutation():
        with transaction(owner) as db:
            db.execute(text("SELECT set_config('application_name',:tag,true)"), {"tag": tag})
            if project:
                db.execute(text("UPDATE classsync_identity.tenants "
                                "SET firebase_project_id='synthetic-project-changed' "
                                "WHERE id='tenant-a'"))
            else:
                identity_context(db, tenant_id="tenant-a", uid="uid-admin")
                audit_actor(db, VerifiedPrincipal(uid="synthetic-qualification-operator"))
                db.execute(text("UPDATE classsync_identity.memberships SET state='revoked',"
                                "revision=revision+1 WHERE tenant_id='tenant-a' "
                                "AND uid='uid-admin'"))

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with repo.session(dataset="institutional"):
                future = pool.submit(mutation)
                waiters = wait_for_locks(owner, application=tag)
                require(not future.done(), "Authority mutation passed the publication row lock")
            future.result(timeout=10)
        must_fail(lambda: repo.history("institutional", "generated-scope"), "membership_denied")
    finally:
        with transaction(owner) as db:
            if project:
                db.execute(text("UPDATE classsync_identity.tenants "
                                "SET firebase_project_id='synthetic-project' WHERE id='tenant-a'"))
            else:
                identity_context(db, tenant_id="tenant-a", uid="uid-admin")
                audit_actor(db, VerifiedPrincipal(uid="synthetic-qualification-operator"))
                db.execute(text("UPDATE classsync_identity.memberships SET state='active',"
                                "revision=revision+1 WHERE tenant_id='tenant-a' "
                                "AND uid='uid-admin'"))
    return {"observed_waiters": waiters, "mutation_denied_after_commit": True}


def academic_lock_probe(owner, repo, period):
    tag = "classsync-academic-" + uuid4().hex[:20]

    def mutation():
        with transaction(owner) as db:
            db.execute(text("SELECT set_config('application_name',:tag,true)"), {"tag": tag})
            db.execute(text("UPDATE classsync_academic.period_metadata SET revision=revision+1 "
                            "WHERE tenant_id='tenant-a' AND owner_uid='uid-admin' AND id=:period"),
                       {"period": period})

    with ThreadPoolExecutor(max_workers=1) as pool:
        with repo.session(dataset="institutional") as db:
            repo.academic.period_in(db, period, lock=True)
            future = pool.submit(mutation)
            observed = wait_for_locks(owner, application=tag)
            require(not future.done(), "Academic mutation passed the publication period row lock")
        future.result(timeout=10)
    return {"observed_waiters": observed, "generated_revision_advanced_after_release": True}


def independent_period_conflict(
    runtime, other_repo, other_academic, repo, snapshot, original_draft,
):
    distinct = complete(FixtureCalls(other_academic))
    distinct = other_academic.save_calendar(distinct.period.id, CalendarWrite(
        expected_revision=distinct.period.revision, calendar=configuration().calendar,
    ))
    draft = saved_draft(runtime, distinct, uid="uid-admin-other")
    conflict = publish_command(draft, distinct)
    try:
        other_repo.publish(conflict, commit=True)
    except DraftError as error:
        require(error.status == 422
                and error.code in {"publication_conflict", "publication_workload"},
                f"Unexpected actual cross-period resource negative: {error.code}")
        conflict_code = error.code
    else:
        raise RuntimeError("Shared generated resources accepted competing period publication")
    outside = publish_command(original_draft, snapshot, version=3, start="2026-12-21")
    outside.calendar.effective_end = date(2027, 1, 1)
    must_fail(lambda: repo.publish(outside, commit=True), "publication_calendar", 422)
    return {"solver_status": draft.solver_status, "actual_shared_resource_negative": conflict_code,
            "outside_saved_semester_denied": True}


def restrictions_proof(owner, repo, body, snapshot):
    view = repo.admin_calendar(body.dataset, snapshot.period.id,
                               date(2026, 10, 1), date(2026, 10, 31))
    require(view["occurrences"], "Administrator projection has no real published occurrences")
    event = view["occurrences"][0]
    # Across UTC midnight, entirely before instructional hours in Manila.
    room = event["room"]["id"]
    restriction = RoomRestriction(
        id="generated-midnight-restriction", dataset=body.dataset, room_id=room,
        starts_at="2026-10-05T23:30:00+00:00", ends_at="2026-10-06T00:00:00+00:00",
        kind="reservation", reason="Generated disposable midnight interval", expected_revision=0,
    )
    first = repo.put_restriction(restriction)
    changed = restriction.model_copy(update={"expected_revision": 1,
                                            "reason": "Generated revision two"})
    second = repo.put_restriction(changed)
    require(first["revision"] == 1 and second["revision"] == 2
            and first["starts_at"] == "2026-10-05T23:30:00+00:00",
            "Restriction UTC/revision changed")
    must_fail(lambda: repo.put_restriction(restriction), "restriction_version_conflict", 409)
    overlapping = restriction.model_copy(update={
        "id": "generated-overlapping-restriction", "starts_at": event["starts_at"],
        "ends_at": event["ends_at"], "expected_revision": 0,
    })
    before = state(owner)
    must_fail(lambda: repo.put_restriction(overlapping), "restriction_publication_conflict", 409)
    require(state(owner) == before, "Rejected restriction left publication or audit writes")
    audits = state(owner)["restriction_audit"]
    require(len(audits) == 2 and [entry["revision"] for entry in audits] == [1, 2]
            and audits[0]["old_snapshot"] is None
            and audits[1]["old_snapshot"] == audits[0]["new_snapshot"]
            and all(entry["actor_uid"] == "uid-admin" for entry in audits),
            "Restriction audit is missing or changed its previous immutable snapshot")
    return {"revision_one_two_exact_audits": True, "utc_midnight_interval": True,
            "overlapping_published_event_denied": True}


def audit_failure_rollback(owner, repo):
    before = state(owner)
    require(len(before["room_restrictions"]) == 1, "Expected one generated restriction")
    row = before["room_restrictions"][0]
    value = repo.restriction_value(row)
    require(value.pop("revision") == 2, "Generated restriction is not revision two")
    body = RoomRestriction.model_validate(value | {"expected_revision": 2,
                                                  "reason": "Generated audit recovery revision"})
    constraint = "qualification_audit_" + uuid4().hex
    with transaction(owner) as db:
        db.execute(text("ALTER TABLE classsync_scheduling.restriction_audit "
                        f"ADD CONSTRAINT {constraint} CHECK (revision<>3)"))
    try:
        must_fail(lambda: repo.put_restriction(body), "publication_integrity", 409)
        require(state(owner) == before,
                "AFTER audit failure left a new restriction or partial audit")
    finally:
        with transaction(owner) as db:
            db.execute(text("ALTER TABLE classsync_scheduling.restriction_audit "
                            f"DROP CONSTRAINT {constraint}"))
    recovered = repo.put_restriction(body)
    require(recovered["revision"] == 3, "Audit failure recovery did not advance exactly once")
    after = state(owner)
    audits = sorted(after["restriction_audit"], key=lambda entry: entry["revision"])
    require(len(audits) == 3 and audits[-1]["revision"] == 3
            and audits[-1]["old_snapshot"] == audits[-2]["new_snapshot"],
            "Audit recovery lost the exact prior snapshot or created duplicate revision")
    return {"forced_after_trigger_failure_rolls_back_all_state": True,
            "named_generated_constraint_removed": True, "recovery_revision_three_once": True}


def migration_rollback_rehearsal(owner, connection, migrator, repo, body, period, receipt, history):
    """Rehearse publication rollback/reapply without losing earlier published state."""
    before = state(owner)
    preserved = ("solver_runs", "drafts", "published_versions", "publication_heads")
    require(before["room_restrictions"] and before["restriction_audit"],
            "Migration rehearsal requires generated restriction and audit rows")
    hashes = {table: digest(encode(before[table])) for table in preserved}
    with transaction(owner) as db:
        db.execute(text(f"SET LOCAL ROLE {migrator}"))
        migrate(db, target="0007_publication_state", downgrade=True)
        db.execute(text("RESET ROLE"))
    with transaction(owner) as db:
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        require(db.scalar(text("SELECT version_num FROM public.alembic_version"))
                == "0007_publication_state", "publication downgrade did not reach 0007")
        require(db.scalar(text("SELECT to_regclass('classsync_scheduling.room_restrictions')"))
                is None and db.scalar(text(
                    "SELECT to_regclass('classsync_scheduling.restriction_audit')")) is None,
                "publication downgrade retained its owned restriction relations")
        for table in preserved:
            rows = db.scalar(text("SELECT coalesce(jsonb_agg(to_jsonb(t) "
                "ORDER BY to_jsonb(t)::text),'[]') FROM classsync_scheduling." + table + " t"))
            require(rows == before[table], f"publication downgrade changed {table}")
        db.execute(text(f"SET LOCAL ROLE {migrator}"))
        migrate(db, target=MIGRATION)
        db.execute(text("RESET ROLE"))
    with transaction(owner) as db:
        require(db.scalar(text("SELECT version_num FROM public.alembic_version")) == MIGRATION,
                "publication re-upgrade did not restore the head revision")
        require(db.scalar(text("SELECT count(*) FROM classsync_scheduling.room_restrictions"))
                == 0 and db.scalar(text(
                    "SELECT count(*) FROM classsync_scheduling.restriction_audit")) == 0,
                "Re-upgraded restriction relations were not empty after rollback")
        require(db.scalar(text("SELECT count(*) FROM "
                    "classsync_scheduling.legacy_publication_archive")) == 0,
                "Legacy archive relation was not empty after rollback/re-upgrade")
        db.execute(text("GRANT SELECT,INSERT,UPDATE ON classsync_scheduling.room_restrictions "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT SELECT ON classsync_scheduling.restriction_audit "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT SELECT,INSERT ON classsync_scheduling.legacy_publication_archive "
                        f"TO {connection.runtime}"))
        db.execute(text("GRANT EXECUTE ON FUNCTION classsync_scheduling."
                        f"lock_publication_authority() TO {connection.runtime}"))
    after = state(owner)
    require(all(after[table] == before[table] for table in preserved),
            "Publication rollback/reapply changed earlier immutable publication records")
    require(not after["room_restrictions"] and not after["restriction_audit"],
            "0008 restriction data unexpectedly survived its explicit rollback")
    require(repo.history(body.dataset, period) == history
            and repo.publish(body, commit=True) == receipt,
            "History or exact idempotent receipt changed after migration rollback")
    draft = repo.drafts.get(body.draft_id)
    require(draft.input_snapshot.rooms, "Generated migration probe draft has no eligible room")
    restriction = RoomRestriction(
        id="migration-reapply-" + uuid4().hex[:24],
        room_id=draft.input_snapshot.rooms[0].id,
        dataset=body.dataset,
        starts_at="2027-12-01T08:00:00+08:00",
        ends_at="2027-12-01T09:00:00+08:00",
        kind="reservation",
        reason="Generated migration re-upgrade probe",
        expected_revision=0,
    )
    created = repo.put_restriction(restriction)
    revised = repo.put_restriction(restriction.model_copy(update={
        "expected_revision": 1, "reason": "Generated migration re-upgrade revision two",
    }))
    after_write = state(owner)
    restrictions = [row for row in after_write["room_restrictions"]
                    if row["id"] == restriction.id]
    audits = sorted((row for row in after_write["restriction_audit"]
                     if row["id"] == restriction.id), key=lambda row: row["revision"])
    require(created["revision"] == 1 and revised["revision"] == 2
            and len(restrictions) == 1 and restrictions[0]["revision"] == 2
            and len(audits) == 2 and audits[0]["old_snapshot"] is None
            and audits[1]["old_snapshot"] == audits[0]["new_snapshot"],
            "Re-upgraded restriction permissions or audited write path failed")
    return {"upgrade_downgrade_upgrade": True,
            "preserved_tables": list(preserved), "preserved_table_sha256": hashes,
            "restriction_rows_removed_only_by_disposable_0008_rollback": True,
            "record_projection_policy_restored_by_0009_reapply": True,
            "history_and_exact_replay_after_reupgrade": True,
            "restriction_insert_update_and_audit_after_reupgrade": True}


def legacy_archive_probe(connection, owner, runtime, migrator, body):
    """Import one generated SQLite-format history row into archive-only PG storage."""
    root = checked_connection(connection)
    source = root / "legacy-publication-source.sqlite"
    if source.exists():
        raise RuntimeError("Generated source fixture path already exists")
    state_before = state(owner)
    candidates = [row for row in state_before["published_versions"]
                  if row["draft_id"] == body.draft_id]
    require(candidates, "Generated publication source row is missing")
    current = candidates[0]
    source_tenant = "generated-legacy-tenant"
    actor = current["actor_uid"]
    payload = current["payload"]
    checksum = digest(payload)
    source_row = {
        "sequence": 1,
        "id": "legacy-generated-" + uuid4().hex,
        "tenant": source_tenant,
        "dataset": body.dataset,
        "period_id": current["period_id"],
        "revision": current["revision"],
        "draft_id": current["draft_id"],
        "actor": actor,
        "created_at": current["created_at"],
        "idempotency_key": "legacy-archive-" + uuid4().hex[:24],
        "request_hash": digest("opaque legacy command with unavailable preimage"),
        "payload": payload,
        "checksum": checksum,
    }
    with closing(sqlite3.connect(source)) as database:
        database.row_factory = sqlite3.Row
        with database:
            database.execute("""
                CREATE TABLE published_versions (
                    sequence INTEGER PRIMARY KEY,id TEXT UNIQUE NOT NULL,tenant TEXT NOT NULL,
                    dataset TEXT NOT NULL,period_id TEXT NOT NULL,revision INTEGER NOT NULL,
                    draft_id TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,payload TEXT NOT NULL,
                    checksum TEXT NOT NULL)
            """)
            database.execute("INSERT INTO published_versions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             tuple(source_row.values()))
            selected = dict(database.execute("SELECT * FROM published_versions").fetchone())
    source_fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    arguments = {
        "tenant_id": "tenant-a",
        "firebase_project_id": "synthetic-project",
        "principal": VerifiedPrincipal(uid="uid-admin"),
        "source_fingerprint": source_fingerprint,
        "owner_map": {(source_tenant, actor): ("tenant-a", "uid-admin")},
    }
    before_import = state(owner)
    imported = import_legacy_publications(runtime, rows=[selected], **arguments)
    require(imported == 1, "Generated legacy publication was not archived")
    archived_state = state(owner)
    require(archived_state["published_versions"] == before_import["published_versions"]
            and archived_state["publication_heads"] == before_import["publication_heads"]
            and len(archived_state["legacy_publication_archive"])
            == len(before_import["legacy_publication_archive"]) + 1,
            "Archive import mutated active published versions or heads")
    stored = next(row for row in archived_state["legacy_publication_archive"]
                  if row["source_fingerprint"] == source_fingerprint)
    require(stored["request_hash"] == source_row["request_hash"]
            and stored["payload"] == source_row["payload"]
            and stored["checksum"] == source_row["checksum"],
            "Archive import changed the source hash or payload")
    require(import_legacy_publications(runtime, rows=[selected], **arguments) == 0,
            "Exact archive retry was not idempotent")
    collision = selected | {
        "sequence": selected["sequence"] + 1,
        "id": selected["id"] + "-collision",
    }
    try:
        import_legacy_publications(runtime, rows=[collision], **arguments)
    except LegacyPublicationError:
        pass
    else:
        raise RuntimeError("Archive key collision was accepted")
    final = state(owner)
    require(final == archived_state, "Failed archive import partially changed target state")
    try:
        with transaction(owner) as db:
            db.execute(text(f"SET LOCAL ROLE {migrator}"))
            migrate(db, target="0009_publication_record_projection", downgrade=True)
    except DBAPIError as error:
        require(getattr(error.orig, "sqlstate", None) == "55000",
                "Archive downgrade failed for an unexpected database reason")
    else:
        raise RuntimeError("Nonempty immutable archive downgrade was accepted")
    with transaction(owner) as db:
        require(db.scalar(text("SELECT version_num FROM public.alembic_version")) == MIGRATION
                and db.scalar(text("SELECT count(*) FROM "
                    "classsync_scheduling.legacy_publication_archive"))
                == len(archived_state["legacy_publication_archive"]),
                "Rejected archive downgrade did not preserve migration and data")
    return {"generated_sqlite_source_fingerprint": source_fingerprint,
            "opaque_request_hash_and_payload_preserved": True,
            "archive_not_active_publication": True,
            "exact_replay_idempotent": True,
            "conflicting_key_atomic_rollback": True,
            "nonempty_archive_downgrade_denied": True}


def outage_proof(connection, owner, runtime, repo, dataset, period, body):
    check_pool(runtime)
    expected = repo.history(dataset, period)
    for table in ("classsync_identity.memberships", "classsync_scheduling.published_versions"):
        with transaction(owner) as db:
            db.execute(text(f"REVOKE SELECT ON {table} FROM {connection.runtime}"))
        try:
            must_fail(lambda: repo.history(dataset, period), "persistence_unavailable", 503)
        finally:
            with transaction(owner) as db:
                db.execute(text(f"GRANT SELECT ON {table} TO {connection.runtime}"))
        require(repo.history(dataset, period) == expected, "Read outage recovery changed history")
    with transaction(owner) as db:
        db.execute(text("REVOKE EXECUTE ON FUNCTION classsync_scheduling."
                        f"lock_publication_authority() FROM {connection.runtime}"))
    try:
        must_fail(lambda: repo.publish(body, commit=False), "persistence_unavailable", 503)
    finally:
        with transaction(owner) as db:
            db.execute(text("GRANT EXECUTE ON FUNCTION classsync_scheduling."
                            f"lock_publication_authority() TO {connection.runtime}"))
    held = []
    try:
        for _ in range(5):
            held.append(runtime.connect())
        check_pool(runtime, exhausted=True)
        must_fail(lambda: repo.history(dataset, period), "persistence_unavailable", 503)
    finally:
        for db in held:
            db.close()
    require(repo.history(dataset, period) == expected, "Pool recovery changed history")
    return {"membership_and_publication_select_outage": True, "actual_five_connection_pool": True,
            "authority_helper_execute_outage": True}


def corrupt_immutable_fixture(owner, repo, draft, snapshot, *, version):
    """Last probe intentionally leaves corrupt GENERATED state, then the cluster is stopped.

    SQL is the fault injector; no runtime decoder, identity or validation is replaced.
    Earlier valid immutable rows are preserved. Never apply this probe to originals.
    """
    command = publish_command(draft, snapshot, version=version, start="2026-12-23")
    value = encode(command.model_dump(mode="json"))
    draft_value = draft.model_dump(mode="json")
    draft_value["generation_result"]["input_hash"] = "0" * 64
    payload = encode({"draft": draft_value, "calendar": command.calendar.model_dump(mode="json"),
                      "review": {"status": "intentional-generated-corruption-fixture"}})
    row = {"tenant_id": "tenant-a", "dataset": command.dataset, "period_id": draft.period_id,
           "owner_uid": "uid-admin", "actor_uid": "uid-admin", "draft_id": draft.id,
           "id": str(uuid4()), "revision": version + 1,
           "academic_revision": snapshot.period.revision,
           "created_at": datetime.now(UTC), "idempotency_key": command.idempotency_key,
           "command": value, "request_hash": digest(value), "payload": payload,
           "checksum": digest(payload)}
    require(json.loads(payload)["draft"]["generation_result"]["input_hash"] != draft.input_hash,
            "Generated corruption fixture did not alter the independently validated hash")
    with transaction(owner) as db:
        db.execute(INSERT_VERSION, row)
        db.execute(text("UPDATE classsync_scheduling.publication_heads SET revision=:revision "
                        "WHERE tenant_id='tenant-a' AND dataset=:dataset AND period_id=:period"),
                   {"dataset": command.dataset, "period": draft.period_id, "revision": version + 1})
    must_fail(lambda: repo.history(command.dataset, draft.period_id), "publication_integrity", 409)
    must_fail(lambda: repo.admin_calendar(command.dataset, draft.period_id,
              date(2026, 12, 21), date(2026, 12, 31)), "publication_integrity", 409)
    must_fail(lambda: repo.publish(command, commit=True), "publication_integrity", 409)
    return {"checksum_consistent_raw_generated_version": row["id"],
            "history_projection_replay_all_typed409": True,
            "intentional_generated_corrupt_version_left_until_cluster_stop": True}


def negative_runtime_privileges(owner, runtime, repo):
    statements = (
        "UPDATE classsync_identity.memberships SET roles=ARRAY['administrator'] "
        "WHERE tenant_id='tenant-a' AND uid='uid-student'",
        "INSERT INTO classsync_scheduling.restriction_audit "
        "SELECT * FROM classsync_scheduling.restriction_audit LIMIT 1",
    )
    for statement in statements:
        try:
            with transaction(runtime) as db:
                repo.context.context(db, repo.principal)
                db.execute(text(statement))
                raise RuntimeError("Runtime wrote identity or restriction audit")
        except DBAPIError as error:
            require(error.orig.sqlstate == "42501", "Wrong runtime privilege SQLSTATE")
    try:
        with transaction(owner) as db:
            db.execute(text("UPDATE classsync_scheduling.restriction_audit "
                            "SET actor_uid=actor_uid"))
            raise RuntimeError("Restriction audit accepted mutation")
    except DBAPIError as error:
        require(error.orig.sqlstate == "42501", "Wrong immutable audit SQLSTATE")
    return {"identity_update_and_audit_insert_denied": True, "audit_immutable": True}


def publication_policy_cycle_probe(owner, runtime, migrator):
    """Reproduce old runtime INSERT rewrite recursion, then verify forward repair."""
    def catalog():
        with transaction(owner) as db:
            policies = [dict(row) for row in db.execute(text("""
                SELECT c.relname,p.polname,p.polcmd,
                    pg_get_expr(p.polqual,p.polrelid) AS using_expression,
                    pg_get_expr(p.polwithcheck,p.polrelid) AS check_expression,
                    pg_get_userbyid(c.relowner) AS owner,
                    c.relrowsecurity,c.relforcerowsecurity
                FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='classsync_scheduling'
                    AND c.relname IN ('published_versions','publication_heads')
                ORDER BY c.relname,p.polname
            """)).mappings()]
            require(policies and all(row["owner"] == migrator and row["relrowsecurity"]
                    and row["relforcerowsecurity"] for row in policies),
                    "Publication policy ownership/RLS changed")
            return policies

    with transaction(owner) as db:
        db.execute(text(f"SET LOCAL ROLE {migrator}"))
        migrate(db, target="0010_legacy_publication_archive", downgrade=True)
    before = catalog()
    try:
        with transaction(runtime) as db:
            identity_context(db, tenant_id="tenant-a", uid="uid-admin")
            db.execute(text("SELECT set_config('classsync.project_id','synthetic-project',true)"))
            db.execute(text("EXPLAIN INSERT INTO classsync_scheduling.published_versions "
                            "DEFAULT VALUES RETURNING *"))
    except DBAPIError as error:
        require(error.orig.sqlstate == "42P17" and "infinite recursion" in str(error.orig),
                "Expected the confirmed publication RLS recursion")
    else:
        raise RuntimeError("Old policy did not reproduce INSERT RETURNING recursion")
    with transaction(owner) as db:
        db.execute(text(f"SET LOCAL ROLE {migrator}"))
        migrate(db, target=MIGRATION)
    after = catalog()
    changed = [row for row in after if row not in before]
    require(len(changed) == 1 and changed[0]["polname"] == "publication_create"
            and "publication_heads" not in changed[0]["check_expression"],
            "Corrective migration altered more than the version write policy")
    with transaction(runtime) as db:
        identity_context(db, tenant_id="tenant-a", uid="uid-admin")
        db.execute(text("SELECT set_config('classsync.project_id','synthetic-project',true)"))
        db.execute(text("EXPLAIN INSERT INTO classsync_scheduling.published_versions "
                        "DEFAULT VALUES RETURNING *"))
        for table in ("published_versions", "publication_heads"):
            require(db.scalar(text(f"SELECT count(*) FROM classsync_scheduling.{table}")) == 0,
                    "Policy rewrite probe mutated publication data")
    return {"old_runtime_insert_returning_42P17": True, "forward_upgrade_rewrite_pass": True,
            "before_pg_policy": before, "after_pg_policy": after,
            "real_insert_commit_and_projections": "asserted by subsequent repository probes"}


def publication_read_context_denials(runtime):
    contexts = [None, ("tenant-a", "missing", "administrator", "", "synthetic-project"),
                ("tenant-b", "uid-admin", "administrator", "", "synthetic-project"),
                ("tenant-a", "uid-admin", "administrator", "", "wrong-project"),
                ("tenant-a", "uid-student", "student", "wrong-student", "synthetic-project"),
                ("tenant-a", "uid-teacher", "teacher", "wrong-faculty", "synthetic-project"),
                ("tenant-a", "uid-student", "teacher", "faculty-a", "synthetic-project")]
    for context in contexts:
        with transaction(runtime) as db:
            if context:
                tenant, uid, role, record, project = context
                identity_context(db, tenant_id=tenant, uid=uid)
                for key, value in (("role", role), ("record_id", record), ("project_id", project)):
                    db.execute(text("SELECT set_config(:key,:value,true)"),
                               {"key": "classsync." + key, "value": value})
            for table in ("published_versions", "publication_heads"):
                require(db.scalar(text(f"SELECT count(*) FROM classsync_scheduling.{table}")) == 0,
                        f"Denied publication context exposed {table}")
    return {"direct_versions_and_heads_denied_contexts": len(contexts)}


def exercise(connection):
    root = checked_connection(connection)
    owner, runtime = engine_for(connection, bootstrap=True), None
    try:
        runtime = bounded_runtime(connection)
        check_pool(runtime)
        with transaction(owner) as db:
            verify_fresh_target(db, connection, root)
        first, _unused_empty, migrator = prepare_source(connection, owner, runtime)
        authorize_grants(connection, owner, migrator)
        policy_cycle = publication_policy_cycle_probe(owner, runtime, migrator)
        direct_helper = direct_authority_helper(connection, owner, runtime, migrator)
        first = enrolled_projection_fixture(academic_store(runtime), first)
        repo = repository(runtime)
        draft = saved_draft(runtime, first)
        require(draft.input_snapshot.enrollments,
                "Published Student control must have persisted enrollment")
        teacher_id = draft.generation_result.assignments[0].teacher_id
        projection_membership_fixture(owner, teacher_id)
        body = publish_command(draft, first)
        before = state(owner)
        with patch("sqlite3.connect", side_effect=AssertionError("SQLite fallback prohibited")):
            review = repo.publish(body, commit=False)
            require(review["status"] == "ready-for-review" and review["occurrences"] > 0,
                    "Actual owned PG review did not validate real occurrences")
            require(state(owner) == before, "Review mutated durable publication state")
            receipt = repo.publish(body, commit=True)
            require(receipt["status"] == "published" and receipt["revision"] == 1,
                    "First publication did not atomically establish revision one")
        denied_reads = publication_read_context_denials(runtime)
        second_body = publish_command(draft, first, version=1, start="2026-11-16")
        second_receipt = repo.publish(second_body, commit=True)
        require(second_receipt["revision"] == 2
                and repo.publish(body, commit=True) == receipt,
                "Later publication changed the immutable original replay receipt")
        history = repo.history(body.dataset, first.period.id)
        require([entry["status"] for entry in history] == ["published", "superseded"]
                and [entry["revision"] for entry in history] == [2, 1],
                "History did not expose exact current/superseded revisions")
        before = state(owner)
        for changes in ({"expected_version": 999}, {"draft_id": "another-draft"},
                        {"expected_academic_revision": 999}):
            must_fail(lambda c=changes: repo.publish(body.model_copy(update=c), commit=True),
                      "publish_key_conflict", 409)
        must_fail(lambda: repo.publish(publish_command(draft, first), commit=True),
                  "publication_version_conflict", 409)
        duplicate = publish_command(draft, first, version=2, start="2026-11-16")
        must_fail(lambda: repo.publish(duplicate, commit=True), "duplicate_publication", 409)
        require(state(owner) == before, "Rejected replay/stale/duplicate changed publication")
        view = repo.admin_calendar(body.dataset, first.period.id,
                                   date(2026, 10, 1), date(2026, 10, 31))
        require(view["occurrences"] and view["teachers"] and view["sections"],
                "Actual Administrator projection is incomplete")
        routed_calendar = repo.calendar(
            repo.keys["tenant"], body.dataset, first.period.id,
            date(2026, 10, 1), date(2026, 10, 31),
            {"role": "administrator", "uid": "uid-admin"},
        )
        periods = repo.periods("administrator", dataset=body.dataset)["periods"]
        require(routed_calendar["occurrences"] == view["occurrences"]
                and any(item["id"] == first.period.id for item in periods),
                "Institutional provider read did not use the authorized PG snapshot")
        event = view["occurrences"][0]
        occupancy = repo.availability(
            body.dataset, event["room"]["id"], datetime.fromisoformat(event["starts_at"]),
            datetime.fromisoformat(event["ends_at"]),
        )
        require(occupancy["occupancy"] == "occupied" and occupancy["sessions"] == 1,
                "PG room availability did not report the exact published session")
        must_fail(
            lambda: repo.calendar(
                repo.keys["tenant"], body.dataset, first.period.id,
                date(2026, 10, 1), date(2026, 10, 31),
                {"role": "student", "uid": "uid-admin", "student_id": "student-a"},
            ),
            "membership_denied",
        )
        student_repo = repository(runtime, uid="uid-student")
        student_view = student_repo.calendar(
            repo.keys["tenant"], body.dataset, first.period.id,
            date(2026, 10, 1), date(2026, 10, 31),
            {"role": "student", "uid": "uid-student", "student_id": "student-a"},
        )
        student_periods = student_repo.periods(
            "student", dataset=body.dataset, student_id="student-a"
        )["periods"]
        require(student_view["occurrences"]
                and {row["offering_id"] for row in student_view["occurrences"]}
                <= {offering for enrollment in draft.input_snapshot.enrollments
                    if enrollment.student_id == "student-a"
                    for offering in enrollment.offering_ids}
                and all("student_id" not in row for row in student_view["occurrences"])
                and any(item["id"] == first.period.id for item in student_periods),
                "Current student record projection was not available through PostgreSQL RLS")
        other_student = repository(runtime, uid="uid-student-other")
        other_view = other_student.calendar(
            "tenant-a", body.dataset, first.period.id,
            date(2026, 10, 1), date(2026, 10, 31),
            {"role": "student", "uid": "uid-student-other", "student_id": "student-other"},
        )
        require(other_view["occurrences"] and not (
            {row["offering_id"] for row in other_view["occurrences"]}
            & {row["offering_id"] for row in student_view["occurrences"]}
        ), "Student sections leaked into each other's calendars")
        unassigned = repository(runtime, uid="uid-student-unassigned")
        must_fail(lambda: unassigned.calendar(
            "tenant-a", body.dataset, first.period.id,
            date(2026, 10, 1), date(2026, 10, 31),
            {"role": "student", "uid": "uid-student-unassigned",
             "student_id": "student-unassigned"},
        ), "projection_forbidden", 403)
        try:
            with transaction(owner) as db:
                identity_context(db, tenant_id="tenant-a", uid="uid-student")
                audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                db.execute(text("UPDATE classsync_identity.memberships SET state='revoked', "
                                "revision=revision+1 WHERE tenant_id='tenant-a' "
                                "AND uid='uid-student'"))
            must_fail(lambda: student_repo.calendar(
                "tenant-a", body.dataset, first.period.id,
                date(2026, 10, 1), date(2026, 10, 31),
                {"role": "student", "uid": "uid-student", "student_id": "student-a"},
            ), "membership_denied")
        finally:
            with transaction(owner) as db:
                identity_context(db, tenant_id="tenant-a", uid="uid-student")
                audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                db.execute(text("UPDATE classsync_identity.memberships SET state='active', "
                                "revision=revision+1 WHERE tenant_id='tenant-a' "
                                "AND uid='uid-student'"))
        teacher_repo = repository(runtime, uid="uid-teacher")
        teacher_view = teacher_repo.calendar(
            repo.keys["tenant"], body.dataset, first.period.id,
            date(2026, 10, 1), date(2026, 10, 31),
            {"role": "teacher", "uid": "uid-teacher", "faculty_id": teacher_id},
        )
        require(teacher_view["occurrences"] and all(
                row["teacher"]["id"] == teacher_id for row in teacher_view["occurrences"]),
                "Current teacher record projection was not available through PostgreSQL RLS")
        for candidate in (repository(runtime, uid="uid-student"),
                          repository(runtime, uid="uid-teacher"),
                          repository(runtime, uid="missing"),
                          repository(runtime, tenant="tenant-b"),
                          repository(runtime, project="wrong-project")):
            must_fail(lambda c=candidate: c.history(body.dataset, first.period.id),
                      "membership_denied")
            must_fail(lambda c=candidate: c.publish(body, commit=True), "membership_denied")
        other_academic = academic_store(runtime, uid="uid-admin-other")
        # Only the generated fixture identifier is controlled. Every academic write,
        # current-role read, readiness check, CP solve and draft save remains real.
        with patch("services.academic.app.postgres_repository.uuid4",
                   return_value=UUID(first.period.id)):
            other = complete(FixtureCalls(other_academic))
        other = other_academic.save_calendar(other.period.id, CalendarWrite(
            expected_revision=other.period.revision, calendar=configuration().calendar,
        ))
        other_draft = saved_draft(runtime, other, uid="uid-admin-other")
        other_repo = repository(runtime, uid="uid-admin-other")
        must_fail(lambda: other_repo.publish(body, commit=True), "publish_key_conflict", 409)
        collision = publish_command(other_draft, other, version=2, start="2026-12-21")
        must_fail(lambda: other_repo.publish(collision, commit=True),
                  "publication_owner_conflict", 409)
        private = publish_command(draft, first, version=2, start="2026-12-21")
        must_fail(lambda: other_repo.publish(private, commit=False), "draft_not_found", 404)
        concurrency = competing_publications(connection, owner, runtime, repo, draft, first, 2)
        restrictions = restrictions_proof(owner, repo, body, first)
        audit_recovery = audit_failure_rollback(owner, repo)
        privileges = negative_runtime_privileges(owner, runtime, repo)
        conflict = independent_period_conflict(runtime, other_repo, other_academic,
                                               repo, first, draft)
        writer_races, current_version = restriction_publication_races(
            connection, owner, runtime, draft, first, 3,
        )
        # Force an application exception after version/head INSERT, before transaction exit.
        before = state(owner)
        rollback = publish_command(draft, first, version=current_version, start="2026-12-23")
        with patch.object(repo, "receipt", side_effect=RuntimeError("generated rollback")):
            try:
                repo.publish(rollback, commit=True)
            except RuntimeError as error:
                require(str(error) == "generated rollback", "Unexpected application failure")
            else:
                raise RuntimeError("Publication rollback probe did not execute")
        require(state(owner) == before, "Exception left a partial immutable version or head")
        outages = outage_proof(connection, owner, runtime, repo, body.dataset,
                                first.period.id, body)
        locks = {"membership_revocation": authority_lock_probe(owner, repo),
                 "tenant_project": authority_lock_probe(owner, repo, project=True)}
        require(state(owner) == before, "Authority recovery changed publication state")
        expected_history = repo.history(body.dataset, first.period.id)
        with runtime.connect() as db:
            old_backend = db.scalar(text("SELECT pg_backend_pid()"))
        runtime.dispose()
        with runtime.connect() as db:
            require(db.scalar(text("SELECT pg_backend_pid()")) != old_backend,
                    "Physical reconnect reused the old backend")
        require(repo.history(body.dataset, first.period.id) == expected_history
                and repo.publish(body, commit=True) == receipt
                and state(owner) == before, "Reconnect changed history/replay/raw state")
        academic_lock = academic_lock_probe(owner, repo, first.period.id)
        migration_rollback = migration_rollback_rehearsal(
            owner, connection, migrator, repo, body, first.period.id, receipt,
            expected_history,
        )
        legacy_archive = legacy_archive_probe(connection, owner, runtime, migrator, body)
        before = state(owner)
        academic = academic_store(runtime)
        subject = next(entry for entry in first.records if entry.record.id == "subject-a")
        changed = academic.save(first.period.id, "subjects", "subject-a", RecordWrite(
            expected_revision=subject.revision,
            record=subject.record.model_copy(update={"name": "Generated freshness change"}),
        ))
        stale = publish_command(draft, first, version=current_version, start="2026-12-23")
        must_fail(lambda: repo.publish(stale, commit=True), "academic_version_conflict", 409)
        updated_revision = stale.model_copy(update={
            "expected_academic_revision": changed.period.revision,
            "idempotency_key": "fresh-revision-stale-input-key",
        })
        must_fail(lambda: repo.publish(updated_revision, commit=True),
                  "academic_input_changed", 409)
        require(state(owner) == before, "Stale academic inputs became published state")
        corruption = corrupt_immutable_fixture(owner, repo, draft, first,
                                                version=current_version)
        with transaction(runtime) as db:
            for table in TABLES:
                require(db.scalar(text(
                    f"SELECT count(*) FROM classsync_scheduling.{table}"
                )) == 0,
                        "Pooled publication context leaked")
        return {"migration": MIGRATION, "actual_solver_statuses": [draft.solver_status,
                   other_draft.solver_status], "ready_generated_academic_drafts": True,
                "privileged_migration_rejected_transactionally": True,
                "direct_authority_helper": direct_helper,
                "fixture_same_period_uuid_only_controlled": True,
                "review_no_write": True, "publish_one_two_original_receipt": True,
                "history_admin_projection_reconnect_exact": True,
                "two_active_admin_same_period_owner_denied": True,
                "strict_key_stale_duplicate_denials": True,
                "negative_roles_tenant_project": True,
                "concurrent_publication": concurrency, "restrictions": restrictions,
                "postgres_provider_projection": {
                    "calendar_period_room_occupancy": True,
                    "current_student_and_teacher_record_scopes": True,
                    "unauthorized_role_projection_denied": True,
                    "persisted_student_enrollment_before_generation": True,
                    "other_section_and_unassigned_denial": True,
                    "revoked_student_calendar_denied": True,
                },
                "observed_restriction_publication_writer_orders": writer_races,
                "audit_failure_recovery": audit_recovery,
                "actual_cross_period_conflict": conflict,
                "runtime_privilege_negatives": privileges,
                "actual_corruption": corruption,
                "authority_row_locks": locks, "outages": outages,
                "academic_period_lock": academic_lock,
                "migration_rollback_rehearsal": migration_rollback,
                "publication_policy_cycle": policy_cycle,
                "direct_publication_read_denials": denied_reads,
                "legacy_publication_archive": legacy_archive,
                "exception_atomic_rollback": True, "academic_revision_and_hash_freshness": True,
                "pooled_context_reset": True,
                "valid_state_before_deliberate_corruption_sha256": digest(encode(before)),
                "limitations": ["No provider/HTTP/browser composition", "No approval authority",
                    "No outbox/realtime acceptance", "No old history migration or restore",
                    "No full publication resource/scale matrix in this qualifier"],
                "full_p3b": False, "production_acceptance": False}
    finally:
        if runtime is not None:
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
    print("PostgreSQL publication repository qualification passed; owned cluster stopped")


if __name__ == "__main__":
    main()
