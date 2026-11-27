"""Reports, utilization, restriction preflight and the activity listing on real PostgreSQL."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from classync_contracts.academic import PeriodClone
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from sqlalchemy import text

from scripts.seed_campus_data import PERIOD_ID, apply_seed
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.catalog import excluded_space_ids, schedulable_space_ids
from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository
from services.scheduling.app.reports import booked_sessions
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT, ADMIN = "cdm", "demo-classsync-reports", "admin-uid"
SECOND = "second-admin-uid"


@pytest.fixture(scope="module")
def world(cluster):  # noqa: F811
    provisioned = provision(cluster)
    engine = provisioned.engine
    with transaction(engine("boot")) as db:
        for table in ("solver_runs", "drafts", "published_versions"):
            execute(db, f"GRANT INSERT ON classsync_scheduling.{table} TO runtime")
        for table in ("publication_heads", "room_restrictions"):
            execute(db, f"GRANT INSERT,UPDATE ON classsync_scheduling.{table} TO runtime")
        execute(db, "GRANT EXECUTE ON FUNCTION "
                    "classsync_scheduling.lock_publication_authority() TO runtime")
        execute(db, "INSERT INTO classsync_identity.tenants VALUES (:t,:p)", t=TENANT, p=PROJECT)
        identity_context(db, tenant_id=TENANT, uid=ADMIN)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        execute(db, "INSERT INTO classsync_identity.people(tenant_id,id) VALUES (:t,'p-admin')",
                t=TENANT)
        execute(db, "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,roles,state,revision) VALUES "
                    "(:t,:u,'p-admin',ARRAY['administrator'],'active',1)", t=TENANT, u=ADMIN)
        identity_context(db, tenant_id=TENANT, uid=SECOND)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        execute(db, "INSERT INTO classsync_identity.people(tenant_id,id) VALUES (:t,'p-second')",
                t=TENANT)
        execute(db, "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,roles,state,revision) VALUES "
                    "(:t,:u,'p-second',ARRAY['administrator'],'active',1)", t=TENANT, u=SECOND)

    def repository(user, kind, uid=ADMIN):
        return kind(engine(user), tenant_id=TENANT, firebase_project_id=PROJECT,
                    principal=VerifiedPrincipal(uid=uid))

    apply_seed(repository("operator", PostgresAcademicRepository))
    academic = repository("runtime", PostgresAcademicRepository)
    publication = repository("runtime", PostgresPublicationRepository)
    empty = academic.clone_period(PERIOD_ID, PeriodClone(title="Unpublished copy"))
    snapshot = academic.snapshot(PERIOD_ID)
    inputs = academic_readiness(snapshot).inputs
    result = generate_week(inputs)
    drafts = repository("runtime", PostgresDraftRepository)
    drafts.remember_run(inputs, result)
    draft, _ = drafts.save(SaveDraftRequest(
        run_id=result.run_id, input_hash=result.input_hash, title="Reports runtime",
        idempotency_key="reports-runtime-draft",
    ))
    publication.publish(PublicationCommand(
        draft_id=draft.id, dataset="institutional", expected_version=0,
        expected_academic_revision=snapshot.period.revision,
        idempotency_key="reports-runtime-publish", calendar=snapshot.period.calendar,
    ), commit=True)
    try:
        yield SimpleNamespace(
            publication=publication, snapshot=snapshot, result=result, inputs=inputs,
            empty=empty.period.id, engine=engine,
            second=repository("runtime", PostgresPublicationRepository, uid=SECOND),
        )
    finally:
        for item in provisioned.engines.values():
            item.dispose()


def _restriction(world, identity, room, day, *, revision=0, status="active"):
    return RoomRestriction(
        id=identity, room_id=room, starts_at=f"{day}T07:00:00+08:00",
        ends_at=f"{day}T09:00:00+08:00", kind="operational", reason="Invented maintenance",
        expected_revision=revision, status=status,
    )


def _free_slot(world):
    """A schedulable room and instructional date with no published class between 07:00-09:00."""
    day = world.snapshot.period.calendar.effective_start
    while day.weekday() != 0:
        day += timedelta(days=1)
    busy = {a.room_id for a in world.result.assignments if a.day == 0 and a.start < 540}
    return min(schedulable_space_ids() - busy), day


def test_report_covers_every_room_instructor_and_program(world):
    report = world.publication.report(PERIOD_ID)
    assert report["published"]["revision"] == 1
    assert len(report["rooms"]) == 41
    assert not {room["id"] for room in report["rooms"]} & excluded_space_ids()
    assert len(report["faculty"]) == 57
    assert sum(f["sessions"] for f in report["faculty"]) == len(world.result.assignments)
    assert sum(f["weekly_minutes"] for f in report["faculty"]) == sum(
        a.end - a.start for a in world.result.assignments
    )
    assert all(f["max_weekly_minutes"] and f["load"] <= 100 for f in report["faculty"])
    assert sum(p["offerings"] for p in report["programs"]) == 247
    assert sum(i["sessions"] for i in report["institutes"]) == len(world.result.assignments)
    assert len(report["sections"]) == 36
    assert sum(b["rooms"] for b in report["buildings"]) == 41
    assert sum(t["rooms"] for t in report["room_types"]) == 41
    booked = sum(room["booked_minutes"] for room in report["rooms"])
    dates = report["basis"]["instructional_dates"]
    assert dates > 50 and booked > 0
    # 07:00-21:00, Monday-Saturday, for each of the 41 rooms.
    assert {room["operating_minutes"] for room in report["rooms"]} == {dates * 840}
    assert all(0 <= room["utilization"] <= 100 for room in report["rooms"])


def test_report_bookings_match_the_publication_expansion(world):
    """The single-pass booking list equals the dated events publication itself validates."""
    calendar = world.snapshot.period.calendar
    with world.publication.session() as db:
        rows = world.publication.rows(db, TENANT, "institutional")
        events, day = [], calendar.effective_start
        while day <= calendar.effective_end:
            last = min(day + timedelta(days=62), calendar.effective_end)
            events.extend(world.publication.expanded(rows, day, last))
            day = last + timedelta(days=1)
        booked = booked_sessions(
            world.publication.report_versions(rows, None, None, calendar),
            calendar.effective_start, calendar.effective_end,
        )
    assert sorted((e["room"]["id"], e["starts_at"], e["ends_at"]) for e in events) == sorted(
        (b["room_id"], b["starts_at"].isoformat(), b["ends_at"].isoformat()) for b in booked
    )


def test_active_restrictions_reduce_operating_minutes_and_cancelled_ones_do_not(world):
    room, day = _free_slot(world)
    before = next(r for r in world.publication.report(PERIOD_ID)["rooms"] if r["id"] == room)
    world.publication.put_restriction(_restriction(world, "report-window", room, day))
    during = next(r for r in world.publication.report(PERIOD_ID)["rooms"] if r["id"] == room)
    assert during["restricted_minutes"] == before["restricted_minutes"] + 120
    assert during["available_minutes"] == before["available_minutes"] - 120
    world.publication.put_restriction(
        _restriction(world, "report-window", room, day, revision=1, status="cancelled")
    )
    after = next(r for r in world.publication.report(PERIOD_ID)["rooms"] if r["id"] == room)
    assert after["available_minutes"] == before["available_minutes"]
    listed = world.publication.restriction_list("institutional", include_cancelled=True)
    assert [(r["id"], r["status"]) for r in listed] == [("report-window", "cancelled")]
    assert world.publication.restriction_list("institutional") == []


def test_preflight_lists_the_published_sessions_a_restriction_would_hit(world):
    first = world.result.assignments[0]
    day = world.snapshot.period.calendar.effective_start
    while day.weekday() != first.day:
        day += timedelta(days=1)
    body = RoomRestriction(
        id="preflight", room_id=first.room_id, starts_at=f"{day}T00:00:00+08:00",
        ends_at=f"{day}T23:30:00+08:00", kind="reservation", reason="Invented event",
        expected_revision=0,
    )
    impact = world.publication.restriction_preflight(body)
    assert impact["total"] == len(impact["sessions"]) >= 1
    assert impact["sessions"][0]["date"] == day.isoformat()
    with pytest.raises(DraftError) as refused:
        world.publication.put_restriction(body)
    assert refused.value.code == "restriction_publication_conflict"
    with pytest.raises(DraftError) as excluded:
        world.publication.restriction_preflight(
            body.model_copy(update={"room_id": min(excluded_space_ids())})
        )
    assert excluded.value.status == 422


def test_unpublished_period_has_no_workload_but_shows_shared_room_use(world):
    report = world.publication.report(world.empty)
    assert report["published"] is None
    # The copy has the same dates, so the shared rooms stay booked by the published period.
    assert [r["booked_minutes"] for r in report["rooms"]] == [
        r["booked_minutes"] for r in world.publication.report(PERIOD_ID)["rooms"]
    ]
    assert sum(f["sessions"] for f in report["faculty"]) == 0
    assert report["sections"] == [] and sum(p["students"] for p in report["programs"]) == 0
    with pytest.raises(DraftError) as missing:
        world.publication.report("00000000-0000-4000-8000-000000000000")
    assert missing.value.status == 404


def test_any_administrator_revises_a_restriction_with_their_own_attribution(world):
    room, day = _free_slot(world)
    world.publication.put_restriction(_restriction(world, "shared-window", room, day))
    revised = _restriction(world, "shared-window", room, day, revision=1)
    assert world.second.put_restriction(revised)["revision"] == 2
    with pytest.raises(DraftError) as stale:
        world.publication.put_restriction(revised)
    assert stale.value.code == "restriction_version_conflict"
    with transaction(world.engine("boot")) as db:
        actors = db.execute(text(
            "SELECT revision,actor_uid FROM classsync_scheduling.restriction_audit "
            "WHERE id='shared-window' ORDER BY revision"
        )).all()
    assert actors == [(1, ADMIN), (2, SECOND)]


def test_activity_listing_returns_period_and_campus_restriction_events(world):
    events = world.publication.administrator_activity(PERIOD_ID, limit=500)
    types = {event["event_type"] for event in events}
    assert {"scheduling.publication.published", "scheduling.restriction.saved"} <= types
    assert {event["actor_uid"] for event in events} == {ADMIN, SECOND}
    assert all(len(event["entity_ref"]) == 64 for event in events)
