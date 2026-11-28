"""Migration 0030 facility issue reports on a throwaway PostgreSQL cluster.

Covers upgrade and downgrade by the non-superuser owner, runtime grants, Teacher row-level
isolation, Administrator transitions, illegal transitions, append-only history, a linked room
restriction and the refusal to downgrade once a report exists. Only HTTP identity
verification is replaced; every statement is real.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence import schema
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.seed_campus_data import PERIOD_ID, apply_seed, stable_uuid
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.scheduling.app import facility_issues, main
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.catalog import excluded_space_ids, schedulable_space_ids
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT, ADMIN = "cdm", "demo-classsync-issues", "admin-uid"
TEACHER, OTHER = "teacher-uid", "other-teacher-uid"
BASE = "/api/v1/timetables/issues"
PREVIOUS, HEAD = "0029_restrictions_and_period_lifecycle", "0030_facility_issue_reports"
REPORTS = "classsync_scheduling.facility_issue_reports"
EVENTS = "classsync_scheduling.facility_issue_events"
TRANSITION = "classsync_scheduling.transition_facility_issue(uuid,integer,text,text,text)"


def _member(engine, uid, person, faculty, role):
    with transaction(engine("boot")) as db:
        identity_context(db, tenant_id=TENANT, uid=uid)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        if faculty is None:
            execute(db, "INSERT INTO classsync_identity.people(tenant_id,id) VALUES (:t,:p)",
                    t=TENANT, p=person)
        execute(db, "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,faculty_id,roles,state,revision) VALUES "
                    "(:t,:u,:p,:f,ARRAY[:r],'active',1)",
                t=TENANT, u=uid, p=person, f=faculty, r=role)


@pytest.fixture(scope="module")
def world(cluster):  # noqa: F811
    provisioned = provision(cluster)
    engine = provisioned.engine
    # An empty database goes back to 0029 and forward again, this time with the hosted
    # runtime role name present and deliberately over-granting default privileges.
    with transaction(engine("migrator")) as db:
        schema.migrate(db, target=PREVIOUS, downgrade=True)
    with transaction(engine("boot")) as db:
        assert db.scalar(text(f"SELECT to_regclass('{REPORTS}')")) is None
        execute(db, "CREATE ROLE classsync_app NOLOGIN NOSUPERUSER NOBYPASSRLS")
        execute(db, "ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA classsync_scheduling "
                    "GRANT ALL ON TABLES TO classsync_app")
    with transaction(engine("migrator")) as db:
        schema.migrate(db)
    with transaction(engine("boot")) as db:
        for table in ("solver_runs", "drafts", "published_versions"):
            execute(db, f"GRANT INSERT ON classsync_scheduling.{table} TO runtime")
        for table in ("publication_heads", "room_restrictions"):
            execute(db, f"GRANT INSERT,UPDATE ON classsync_scheduling.{table} TO runtime")
        execute(db, "GRANT EXECUTE ON FUNCTION "
                    "classsync_scheduling.lock_publication_authority() TO runtime")
        # Exactly what the migration gives classsync_app.
        execute(db, f"GRANT SELECT ON {REPORTS}, {EVENTS} TO runtime")
        execute(db, f"GRANT INSERT ON {REPORTS} TO runtime")
        execute(db, "INSERT INTO classsync_identity.tenants VALUES (:t,:p)", t=TENANT, p=PROJECT)
    _member(engine, ADMIN, "p-admin", None, "administrator")

    def repository(user, kind, uid=ADMIN):
        return kind(engine(user), tenant_id=TENANT, firebase_project_id=PROJECT,
                    principal=VerifiedPrincipal(uid=uid))

    apply_seed(repository("operator", PostgresAcademicRepository))
    snapshot = repository("runtime", PostgresAcademicRepository).snapshot(PERIOD_ID)
    inputs = academic_readiness(snapshot).inputs
    result = generate_week(inputs)
    assert result.solver_status in {"feasible", "optimal"}
    drafts = repository("runtime", PostgresDraftRepository)
    drafts.remember_run(inputs, result)
    draft, _ = drafts.save(SaveDraftRequest(
        run_id=result.run_id, input_hash=result.input_hash, title="Issue runtime",
        idempotency_key="issue-runtime-draft",
    ))
    repository("runtime", PostgresPublicationRepository).publish(PublicationCommand(
        draft_id=draft.id, dataset="institutional", expected_version=0,
        expected_academic_revision=snapshot.period.revision,
        idempotency_key="issue-runtime-publish", calendar=snapshot.period.calendar,
    ), commit=True)

    ordered = sorted(result.assignments, key=lambda item: item.id)
    mine = ordered[0]
    theirs = next(item for item in ordered if item.teacher_id != mine.teacher_id)
    for uid, assignment in ((TEACHER, mine), (OTHER, theirs)):
        _member(engine, uid, stable_uuid("faculty-person", assignment.teacher_id),
                assignment.teacher_id, "teacher")
    claims = {
        TEACHER: {"role": "teacher", "uid": TEACHER, "faculty_id": mine.teacher_id},
        OTHER: {"role": "teacher", "uid": OTHER, "faculty_id": theirs.teacher_id},
        ADMIN: {"role": "administrator", "uid": ADMIN},
    }
    try:
        yield SimpleNamespace(
            engine=engine, repository=repository, mine=mine, theirs=theirs, claims=claims,
        )
    finally:
        for item in provisioned.engines.values():
            item.dispose()


@pytest.fixture
def api(world, monkeypatch):
    """The real routes over the runtime role; only token verification is replaced."""
    acting = {"uid": TEACHER}

    def repository(_request, *, teacher=False, admin=False):
        claims = world.claims[acting["uid"]]
        wanted = "teacher" if teacher else "administrator" if admin else claims["role"]
        if claims["role"] != wanted:
            from fastapi import HTTPException

            raise HTTPException(403, "Current university access required")
        publication = world.repository(
            "runtime", PostgresPublicationRepository, uid=claims["uid"]
        )
        return facility_issues.FacilityIssues(publication), claims

    monkeypatch.setattr(facility_issues, "repository", repository)
    client = TestClient(main.app)

    def as_user(uid):
        acting["uid"] = uid
        return client

    def occurrence(assignment, week=0):
        day = date(2026, 9, 7) + timedelta(weeks=week, days=assignment.day)
        return {"period_id": PERIOD_ID, "occurrence_id": f"{assignment.id}:{day}",
                "occurrence_date": str(day)}

    def report(uid=TEACHER, **changes):
        body = {"id": str(uuid4()), "room_id": world.mine.room_id, "category": "equipment",
                "description": "The projector does not turn on.", **changes}
        return as_user(uid).post(BASE, json=body)

    def listed(uid):
        response = as_user(uid).get(BASE)
        assert response.status_code == 200, response.text
        return response.json()["issues"]

    def transition(issue, status, uid=ADMIN, **changes):
        body = {"expected_revision": issue["revision"], "status": status, **changes}
        return as_user(uid).post(f"{BASE}/{issue['id']}/transition", json=body)

    def created(**changes):
        response = report(**changes)
        assert response.status_code == 201, response.text
        return response.json()

    return SimpleNamespace(
        report=report, created=created, listed=listed, transition=transition,
        occurrence=occurrence,
    )


def _as(world, uid, role, statement, **params):
    """Run SQL as the runtime role with a verified identity context, as the service does."""
    record = world.claims[uid].get("faculty_id") if uid in world.claims else None
    publication = world.repository("runtime", PostgresPublicationRepository, uid=uid)
    with transaction(publication.engine) as db:
        publication.context.context(db, publication.principal)
        db.execute(text(
            "SELECT set_config('classsync.role',:role,true), "
            "set_config('classsync.record_id',:record,true)"
        ), {"role": role, "record": record or ""})
        result = db.execute(text(statement), params)
        return result.all() if result.returns_rows else result.rowcount


def test_runtime_role_gets_least_privilege_and_forced_row_security(world):
    with transaction(world.engine("boot")) as db:
        privileges = {
            (table, action): db.scalar(text(
                "SELECT has_table_privilege('classsync_app',:t,:a)"
            ), {"t": table, "a": action})
            for table in (REPORTS, EVENTS)
            for action in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")
        }
        assert {key for key, granted in privileges.items() if granted} == {
            (REPORTS, "SELECT"), (REPORTS, "INSERT"), (EVENTS, "SELECT"),
        }
        assert db.scalar(text(
            "SELECT has_function_privilege('classsync_app',:f,'EXECUTE')"
        ), {"f": TRANSITION})
        assert db.execute(text(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname IN "
            "('facility_issue_reports','facility_issue_events')"
        )).all() == [(True, True), (True, True)]
        assert db.execute(text(
            "SELECT r.rolsuper,r.rolbypassrls,r.rolname FROM pg_class c "
            "JOIN pg_roles r ON r.oid=c.relowner WHERE c.relname='facility_issue_reports'"
        )).one() == (False, False, "migrator")


def test_teacher_reports_only_own_classes_and_schedulable_rooms(world, api):
    plain = api.created()
    assert (plain["status"], plain["revision"], plain["occurrence_id"]) == ("open", 1, None)
    reference = api.occurrence(world.mine)
    linked = api.created(**reference)
    assert linked["occurrence_id"] == reference["occurrence_id"]
    assert linked["occurrence_date"] == reference["occurrence_date"]
    # A repeated submission returns the same report instead of creating another one.
    again = api.report(id=linked["id"], **reference)
    assert again.status_code == 201 and again.json()["id"] == linked["id"]
    assert api.report(id=linked["id"], description="Another matter").status_code == 409

    excluded = sorted(excluded_space_ids())[0]
    assert api.report(room_id=excluded).status_code == 422
    assert api.report(room_id="not-a-room").status_code == 422
    assert api.report(**api.occurrence(world.theirs)).status_code == 403
    assert api.report(occurrence_id=reference["occurrence_id"]).status_code == 422
    assert api.report(description="x" * 2001).status_code == 422
    assert api.report(uid=ADMIN).status_code == 403
    assert {item["id"] for item in api.listed(TEACHER)} == {plain["id"], linked["id"]}
    assert [e["to_status"] for e in api.listed(TEACHER)[0]["history"]] == ["open"]


def test_row_security_isolates_teachers_and_denies_direct_changes(world, api):
    mine = api.created()
    other = api.created(uid=OTHER, room_id=world.theirs.room_id)
    assert other["id"] not in {item["id"] for item in api.listed(TEACHER)}
    assert [item["id"] for item in api.listed(OTHER)] == [other["id"]]
    count = f"SELECT count(*) FROM {REPORTS} WHERE id=CAST(:id AS uuid)"
    history = f"SELECT count(*) FROM {EVENTS} WHERE issue_id=CAST(:id AS uuid)"
    for statement in (count, history):
        assert _as(world, OTHER, "teacher", statement, id=mine["id"]) == [(0,)]
        assert _as(world, TEACHER, "teacher", statement, id=mine["id"]) == [(1,)]
        assert _as(world, ADMIN, "administrator", statement, id=mine["id"]) == [(1,)]
        # An unverified role claim reveals nothing.
        assert _as(world, OTHER, "administrator", statement, id=mine["id"]) == [(0,)]

    insert = (
        f"INSERT INTO {REPORTS} (tenant_id,id,reporter_uid,room_id,category,description,status) "
        "VALUES (:t,gen_random_uuid(),:reporter,:room,'other','Forged report',:status)"
    )
    for actor, role, reporter, status in (
        (OTHER, "teacher", TEACHER, "open"),
        (TEACHER, "teacher", TEACHER, "resolved"),
        (ADMIN, "administrator", ADMIN, "open"),
    ):
        with pytest.raises(DBAPIError):
            _as(world, actor, role, insert, t=TENANT, reporter=reporter, room=world.mine.room_id,
                status=status)
    for statement in (
        f"UPDATE {REPORTS} SET status='dismissed'",
        f"DELETE FROM {REPORTS}",
        f"INSERT INTO {EVENTS} (tenant_id,issue_id,revision,to_status,actor_uid) "
        "SELECT tenant_id,id,99,'resolved','x' FROM " + REPORTS,
    ):
        with pytest.raises(DBAPIError) as denied:
            _as(world, TEACHER, "teacher", statement)
        assert denied.value.orig.sqlstate == "42501"
    # A Teacher cannot change status, not even through the function.
    with pytest.raises(DBAPIError) as refused:
        _as(world, TEACHER, "teacher",
            "SELECT * FROM classsync_scheduling.transition_facility_issue("
            "CAST(:id AS uuid),1,'resolved','Done',NULL)", id=mine["id"])
    assert refused.value.orig.sqlstate == "42501"
    assert api.transition(mine, "in_progress", uid=TEACHER).status_code == 403


def test_administrator_transitions_are_checked_and_recorded(world, api):
    issue = api.created()
    assert issue["id"] in {item["id"] for item in api.listed(ADMIN)}
    progress = api.transition(issue, "in_progress")
    assert progress.status_code == 200, progress.text
    progress = progress.json()
    assert (progress["status"], progress["revision"]) == ("in_progress", 2)

    stale = api.transition(issue, "resolved", note="Replaced the lamp")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "issue_stale"
    assert api.transition(progress, "resolved").status_code == 422
    assert api.transition(progress, "resolved", note="  ").status_code == 422
    repeated = api.transition(progress, "in_progress")
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "issue_transition"
    assert api.transition(progress, "open").status_code == 422

    done = api.transition(progress, "resolved", note="Replaced the lamp")
    assert done.status_code == 200, done.text
    done = done.json()
    assert (done["status"], done["resolution_note"]) == ("resolved", "Replaced the lamp")
    for status in ("in_progress", "dismissed", "resolved"):
        closed = api.transition(done, status, note="Reopen attempt")
        assert closed.json()["error"]["code"] == "issue_transition"
    missing = api.transition({"id": str(uuid4()), "revision": 1}, "in_progress")
    assert missing.status_code == 404

    seen = next(item for item in api.listed(TEACHER) if item["id"] == issue["id"])
    assert [(e["from_status"], e["to_status"], e["revision"]) for e in seen["history"]] == [
        (None, "open", 1), ("open", "in_progress", 2), ("in_progress", "resolved", 3),
    ]
    assert seen["resolution_note"] == "Replaced the lamp"


def test_a_linked_restriction_must_be_active_and_for_the_reported_room(world, api):
    issue = api.created()
    other_room = sorted(schedulable_space_ids() - {issue["room_id"]})[0]
    publication = world.repository("runtime", PostgresPublicationRepository)

    def restriction(room_id):
        # Early Sunday: outside every published session.
        return publication.put_restriction(RoomRestriction(
            id=str(uuid4()), room_id=room_id, starts_at="2026-09-13T01:00:00+08:00",
            ends_at="2026-09-13T02:00:00+08:00", kind="operational",
            reason="Projector repair", expected_revision=0,
        ))["id"]

    wrong, right = restriction(other_room), restriction(issue["room_id"])
    for bad in (wrong, "no-such-restriction"):
        refused = api.transition(issue, "in_progress", linked_restriction_id=bad)
        assert refused.status_code == 422, refused.text
    linked = api.transition(issue, "in_progress", linked_restriction_id=right)
    assert linked.status_code == 200, linked.text
    # A later status change keeps the link.
    done = api.transition(linked.json(), "resolved", note="Repair finished")
    assert done.json()["linked_restriction_id"] == right


def test_history_is_append_only_even_for_a_superuser(world, api):
    issue = api.created()
    for statement in (
        f"UPDATE {EVENTS} SET note='rewritten'",
        f"DELETE FROM {EVENTS}",
        f"TRUNCATE {EVENTS}",
    ):
        with pytest.raises(DBAPIError) as blocked:
            with transaction(world.engine("boot")) as db:
                db.execute(text(statement))
        assert "append-only" in str(blocked.value)
    # Evidence stays immutable and transitions stay guarded for privileged writers too.
    for change in ("description='rewritten',revision=revision+1,status='in_progress'",
                   "status='resolved'"):
        with pytest.raises(DBAPIError):
            with transaction(world.engine("boot")) as db:
                identity_context(db, tenant_id=TENANT, uid=ADMIN)
                db.execute(text(f"UPDATE {REPORTS} SET {change} WHERE id=CAST(:id AS uuid)"),
                           {"id": issue["id"]})


def test_downgrade_is_refused_while_reports_exist(world, api):
    api.created(uid=OTHER, room_id=world.theirs.room_id)
    with pytest.raises(DBAPIError) as refused:
        with transaction(world.engine("migrator")) as db:
            schema.migrate(db, target=PREVIOUS, downgrade=True)
    assert "must be retained" in str(refused.value)
    with transaction(world.engine("boot")) as db:
        assert db.scalar(text("SELECT version_num FROM public.alembic_version")) == HEAD
        assert db.scalar(text(
            "SELECT relforcerowsecurity FROM pg_class WHERE relname='facility_issue_reports'"
        ))
