"""Roster and period behaviour on a throwaway PostgreSQL cluster, as the runtime role.

Mocked repositories cannot see parameter typing, check constraints, privileges or row-level
security, which is how a roster HTTP 503 reached production. This starts a new loopback-only
cluster in a temporary directory; it never connects to a configured or hosted database.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from classync_contracts.academic import RosterStudentWrite
from classync_contracts.identity import MembershipAuthorizationError, VerifiedPrincipal
from classync_persistence import schema
from classync_persistence.academic_periods import PostgresAcademicPeriods
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from sqlalchemy import text

from scripts.seed_campus_data import (
    ARCHIVED_LEGACY_TITLE,
    LEGACY_PERIOD_ID,
    PERIOD_ID,
    PERIOD_TITLE,
    apply_seed,
)
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.academic.app.record_rules import AcademicError
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT, ADMIN = "cdm", "demo-classsync-roster", "admin-uid"


@pytest.fixture(scope="module")
def database(cluster):  # noqa: F811
    """Migrate as a non-superuser owner, seed as an operator, and expose the runtime role."""
    provisioned = provision(cluster)
    engine, engines = provisioned.engine, provisioned.engines

    with transaction(engine("boot")) as db:
        execute(db, "INSERT INTO classsync_identity.tenants VALUES (:t,:p)", t=TENANT, p=PROJECT)
        for uid, person in ((ADMIN, "p-admin"), ("other-admin", "p-other")):
            identity_context(db, tenant_id=TENANT, uid=uid)
            audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
            execute(db, "INSERT INTO classsync_identity.people(tenant_id,id) VALUES (:t,:p)",
                    t=TENANT, p=person)
            execute(db, "INSERT INTO classsync_identity.memberships "
                        "(tenant_id,uid,person_id,roles,state,revision) VALUES "
                        "(:t,:u,:p,ARRAY['administrator'],'active',1)",
                    t=TENANT, u=uid, p=person)

    def repository(user, uid=ADMIN, kind=PostgresAcademicRepository):
        return kind(engine(user), tenant_id=TENANT, firebase_project_id=PROJECT,
                    principal=VerifiedPrincipal(uid=uid))

    operator = repository("operator")
    # A broken legacy period, as found in the defense tenant, archived by the real seed.
    with operator.session(write=True) as db:
        execute(db, "INSERT INTO classsync_academic.period_metadata "
                    "(tenant_id,owner_uid,id,title) VALUES (:t,:o,:i,:n)",
                t=TENANT, o=ADMIN, i=LEGACY_PERIOD_ID, n=PERIOD_TITLE)
    first = apply_seed(operator)
    second = apply_seed(operator)
    with operator.session(write=True) as db:
        active = operator.period_in(db, PERIOD_ID).revision
        # A wide margin keeps the archived revision highest after later roster writes.
        while operator.period_in(db, LEGACY_PERIOD_ID).revision < active + 25:
            operator.bump(db, LEGACY_PERIOD_ID)
    try:
        yield SimpleNamespace(
            repository=repository, engine=engine, first_seed=first, second_seed=second
        )
    finally:
        for item in engines.values():
            item.dispose()


def _section(repo, year=3):
    return next(
        entry.record for entry in repo.snapshot(PERIOD_ID).records
        if entry.record.kind == "sections" and entry.record.year_level == year
    )


def _student(repo, section, student_id, *, name="Runtime Check", status="unverified"):
    return RosterStudentWrite(
        expected_period_revision=repo.snapshot(PERIOD_ID).period.revision,
        student_id=student_id,
        full_name=name,
        email=f"s{student_id.replace('-', '')}@student.example.edu",
        year_level=section.year_level,
        section_id=section.id,
        enrollment_status=status,
    )


def test_runtime_role_neither_owns_the_tables_nor_bypasses_row_security(database):
    with transaction(database.engine("runtime")) as db:
        superuser, bypass = db.execute(text(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )).one()
        owner = db.scalar(text(
            "SELECT tableowner FROM pg_tables "
            "WHERE schemaname='classsync_identity' AND tablename='students'"
        ))
        writable = db.scalar(text(
            "SELECT has_table_privilege(current_user,'classsync_identity.students','UPDATE')"
        ))
    assert (superuser, bypass, writable) == (False, False, False)
    assert owner == "migrator"


def test_seed_is_idempotent_on_postgresql(database):
    assert database.first_seed[1] == 432  # Phase B: all seven extra programs
    assert database.second_seed == (0, 0)


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"search": "24-00101"},
        {"year_level": 3},
        {"section": True},
        {"year_level": 3, "section": True},
        {"year_level": 3, "section": True, "search": "24-", "offset": 0, "limit": 5},
    ],
)
def test_runtime_role_reads_the_roster_with_every_filter_combination(database, filters):
    runtime = database.repository("runtime")
    section = _section(runtime)
    arguments = dict(filters)
    if arguments.pop("section", False):
        arguments["section_id"] = section.id
    page = runtime.roster_page(PERIOD_ID, **arguments)
    assert page["items"] and page["total"] >= len(page["items"])
    if "section_id" in arguments:
        assert {item["section_id"] for item in page["items"]} == {section.id}
    if "year_level" in arguments:
        assert {item["year_level"] for item in page["items"]} == {3}


def test_runtime_role_creates_activates_rekeys_and_deletes_a_student(database):
    runtime = database.repository("runtime")
    section = _section(runtime)

    def row(student_id):
        return runtime.roster_page(PERIOD_ID, search=student_id)["items"]

    runtime.create_roster_student(PERIOD_ID, _student(runtime, section, "29-00001"))
    assert row("29-00001")[0]["enrollment_status"] == "unverified"
    runtime.update_roster_student(
        PERIOD_ID, "29-00001", _student(runtime, section, "29-00001", status="active")
    )
    assert row("29-00001")[0]["enrollment_status"] == "active"
    runtime.update_roster_student(
        PERIOD_ID, "29-00001", _student(runtime, section, "29-00002", status="active")
    )
    assert not row("29-00001") and row("29-00002")
    runtime.delete_roster_student(
        PERIOD_ID, "29-00002", runtime.snapshot(PERIOD_ID).period.revision
    )
    assert not row("29-00002")
    with transaction(database.engine("boot")) as db:
        events = db.scalars(text(
            "SELECT event_type FROM classsync_scheduling.administrator_activity "
            "WHERE entity_type='student_roster' ORDER BY created_at"
        )).all()
    assert events == [
        "academic.student.created",
        "academic.student.updated",
        "academic.student.updated",
        "academic.student.deleted",
    ]


def test_roster_stays_scoped_to_its_administrator(database):
    with pytest.raises(AcademicError) as other:
        database.repository("runtime", "other-admin").roster_page(PERIOD_ID)
    assert other.value.status == 404
    with pytest.raises(MembershipAuthorizationError):
        database.repository("runtime", "not-a-member").roster_page(PERIOD_ID)


def test_archived_period_is_retained_but_never_listed(database):
    runtime = database.repository("runtime")
    assert [period.id for period in runtime.periods()] == [PERIOD_ID]
    listed = PostgresAcademicPeriods(
        database.engine("runtime"), tenant_id=TENANT, firebase_project_id=PROJECT
    ).list_for(VerifiedPrincipal(uid=ADMIN))
    assert [period.id for period in listed] == [PERIOD_ID]
    publication = database.repository("runtime", kind=PostgresPublicationRepository)
    assert publication.periods("administrator") == {"periods": []}
    # The row survives for append-only audit references, with the higher revision.
    archived = runtime.snapshot(LEGACY_PERIOD_ID).period
    assert archived.title == ARCHIVED_LEGACY_TITLE
    assert archived.revision > runtime.snapshot(PERIOD_ID).period.revision


def test_activity_event_constraint_never_drops_an_earlier_event():
    """Each migration that rewrites the constraint must keep every previously allowed event."""
    versions = Path(schema.__file__).parent / "migrations" / "versions"
    history = []
    for path in sorted(versions.glob("[0-9][0-9][0-9][0-9]_*.py")):
        upgrade = path.read_text(encoding="utf-8").split("def downgrade")[0]
        for body in re.findall(r"CHECK \(event_type IN \(([^)]*)\)", upgrade):
            history.append((path.name, set(re.findall(r"'([a-z_.]+)'", body))))
    assert history, "No event constraint definitions were found"
    allowed_before = set().union(*(events for _, events in history))
    head_name, head_events = history[-1]
    assert not allowed_before - head_events, (
        f"{head_name} no longer allows {sorted(allowed_before - head_events)}"
    )
