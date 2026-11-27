"""Migration 0029 period lifecycle on a throwaway PostgreSQL cluster, as the runtime role.

Covers upgrade, downgrade and re-upgrade by the non-superuser owner, clone, one-way archive,
the write guards, activity events and the refusal to downgrade once history exists.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from classync_contracts.academic import (
    CalendarWrite,
    PeriodArchive,
    PeriodClone,
    RecordWrite,
    RosterBulkStatus,
)
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand
from classync_contracts.scheduling import SaveDraftRequest
from classync_persistence import schema
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.seed_campus_data import PERIOD_ID, apply_seed
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.academic.app.record_rules import AcademicError
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT, ADMIN = "cdm", "demo-classsync-lifecycle", "admin-uid"
HEAD = "0029_restrictions_and_period_lifecycle"


@pytest.fixture(scope="module")
def world(cluster):  # noqa: F811
    provisioned = provision(cluster)
    engine = provisioned.engine
    # Empty database: the owner can go back to 0028 and forward again.
    with transaction(engine("migrator")) as db:
        schema.migrate(db, target="0028_room_occupancy_projection", downgrade=True)
    with transaction(engine("migrator")) as db:
        schema.migrate(db)
    with transaction(engine("boot")) as db:
        for table in ("solver_runs", "drafts", "published_versions"):
            execute(db, f"GRANT INSERT ON classsync_scheduling.{table} TO runtime")
        execute(db, "GRANT INSERT,UPDATE ON classsync_scheduling.publication_heads TO runtime")
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

    def repository(user, kind=PostgresAcademicRepository):
        return kind(engine(user), tenant_id=TENANT, firebase_project_id=PROJECT,
                    principal=VerifiedPrincipal(uid=ADMIN))

    apply_seed(repository("operator"))
    runtime = repository("runtime")
    snapshot = runtime.snapshot(PERIOD_ID)
    inputs = academic_readiness(snapshot).inputs
    result = generate_week(inputs)
    drafts = repository("runtime", PostgresDraftRepository)
    drafts.remember_run(inputs, result)
    draft, _ = drafts.save(SaveDraftRequest(
        run_id=result.run_id, input_hash=result.input_hash, title="Lifecycle runtime",
        idempotency_key="lifecycle-runtime-draft",
    ))
    # A second run that is only saved after the period has been archived.
    late = generate_week(inputs.model_copy(update={"data_version": inputs.data_version + "-late"}))
    drafts.remember_run(
        inputs.model_copy(update={"data_version": inputs.data_version + "-late"}), late
    )
    try:
        yield SimpleNamespace(
            engine=engine, repository=repository, runtime=runtime, drafts=drafts,
            draft=draft, late=late,
        )
    finally:
        for item in provisioned.engines.values():
            item.dispose()


def _kinds(snapshot):
    counts = {}
    for entry in snapshot.records:
        counts[entry.record.kind] = counts.get(entry.record.kind, 0) + 1
    return counts


def _rules(snapshot):
    return next(e for e in snapshot.records if e.record.kind == "constraints")


def _events(world, period=None):
    with transaction(world.engine("boot")) as db:
        return db.execute(text(
            "SELECT event_type,period_id,owner_uid FROM classsync_scheduling.administrator_activity"
        )).all()


def test_there_is_one_alembic_head():
    config = Config()
    config.set_main_option("script_location", str(Path(schema.__file__).parent / "migrations"))
    assert ScriptDirectory.from_config(config).get_heads() == [HEAD]


def test_clone_copies_structure_and_rules_without_enrollments_or_locks(world):
    source = world.runtime.snapshot(PERIOD_ID)
    assert _rules(source).record.enrollments
    clone = world.runtime.clone_period(PERIOD_ID, PeriodClone(title="Next semester"))
    assert clone.period.id != PERIOD_ID and clone.period.revision == 1
    assert _kinds(clone) == _kinds(source)
    rules = _rules(clone).record
    assert rules.enrollments == [] and rules.locked_assignments == []
    assert rules.operating_windows == _rules(source).record.operating_windows
    assert rules.daily_shape == _rules(source).record.daily_shape
    assert {e.record.period_id for e in clone.records if e.record.kind == "sections"} == {
        clone.period.id
    }
    calendar = clone.period.calendar
    assert calendar.effective_start == source.period.calendar.effective_start
    assert calendar.exceptions == [] and calendar.phases == []
    assert world.runtime.snapshot(PERIOD_ID) == source
    # Copied records stay editable and their references are enforced.
    program = next(e for e in clone.records if e.record.kind == "programs"
                   and any(s.record.kind == "sections" and s.record.program_id == e.record.id
                           for s in clone.records))
    with pytest.raises(AcademicError) as used:
        world.runtime.delete(clone.period.id, "programs", program.record.id, program.revision)
    assert used.value.code == "record_in_use"
    assert ("academic.period.cloned", clone.period.id, ADMIN) in _events(world)


def test_archive_is_one_way_blocks_every_write_and_still_allows_cloning(world):
    runtime = world.runtime
    before = runtime.snapshot(PERIOD_ID)
    with pytest.raises(AcademicError) as stale:
        runtime.archive_period(PERIOD_ID, PeriodArchive(expected_revision=1))
    assert stale.value.status == 409
    archived = runtime.archive_period(
        PERIOD_ID, PeriodArchive(expected_revision=before.period.revision)
    )
    assert archived.period.archived_at
    revision = archived.period.revision
    entry = next(e for e in archived.records if e.record.kind == "subjects")
    student = _rules(archived).record.enrollments[0].student_id
    attempts = [
        lambda: runtime.save(
            PERIOD_ID, "subjects", entry.record.id,
            RecordWrite(expected_revision=entry.revision, record=entry.record),
        ),
        lambda: runtime.save_calendar(
            PERIOD_ID,
            CalendarWrite(expected_revision=revision, calendar=archived.period.calendar),
        ),
        lambda: runtime.bulk_roster_status(
            PERIOD_ID,
            RosterBulkStatus(
                expected_period_revision=revision, student_ids=[student],
                enrollment_status="active",
            ),
        ),
        lambda: runtime.archive_period(PERIOD_ID, PeriodArchive(expected_revision=revision)),
    ]
    for attempt in attempts:
        with pytest.raises(AcademicError) as blocked:
            attempt()
        assert (blocked.value.status, blocked.value.code) == (409, "period_archived")

    with pytest.raises(DraftError) as draft:
        world.drafts.save(SaveDraftRequest(
            run_id=world.late.run_id, input_hash=world.late.input_hash, title="Too late",
            idempotency_key="lifecycle-late-draft",
        ))
    assert draft.value.code == "period_archived"
    publication = world.repository("runtime", PostgresPublicationRepository)
    with pytest.raises(DraftError) as published:
        publication.publish(PublicationCommand(
            draft_id=world.draft.id, dataset="institutional", expected_version=0,
            expected_academic_revision=revision, idempotency_key="lifecycle-late-publish",
            calendar=archived.period.calendar,
        ), commit=True)
    assert published.value.status == 409

    # The database itself refuses to clear the archive, even for the owner of the period.
    with pytest.raises(AcademicError):
        with runtime.session(write=True) as db:
            db.execute(text(
                "UPDATE classsync_academic.period_metadata "
                "SET archived_at=NULL,archived_by=NULL WHERE id=:p"
            ), {"p": PERIOD_ID})
    assert runtime.snapshot(PERIOD_ID).records == before.records
    listed = runtime.periods()
    assert listed[-1].id == PERIOD_ID and listed[-1].archived_at
    assert runtime.clone_period(PERIOD_ID, PeriodClone(title="From archive")).period.revision == 1
    assert ("academic.period.archived", PERIOD_ID, ADMIN) in _events(world)


def test_downgrade_is_refused_while_lifecycle_history_exists(world):
    with pytest.raises(DBAPIError) as refused:
        with transaction(world.engine("migrator")) as db:
            schema.migrate(db, target="0028_room_occupancy_projection", downgrade=True)
    assert "must be retained" in str(refused.value)
    with transaction(world.engine("boot")) as db:
        version = db.scalar(text("SELECT version_num FROM public.alembic_version"))
        forced = db.scalars(text(
            "SELECT relforcerowsecurity FROM pg_class WHERE relname IN "
            "('period_metadata','administrator_activity','room_restrictions')"
        )).all()
    assert version == HEAD and forced == [True, True, True]
