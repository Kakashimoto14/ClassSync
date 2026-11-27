"""Roster and period behaviour on a throwaway PostgreSQL cluster, as the runtime role.

Mocked repositories cannot see parameter typing, check constraints, privileges or row-level
security, which is how a roster HTTP 503 reached production. This starts a new loopback-only
cluster in a temporary directory; it never connects to a configured or hosted database.
"""

import re
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import pytest
from classync_contracts.academic import (
    PeriodClone,
    RosterBulkStatus,
    RosterImportCommit,
    RosterImportPreview,
    RosterStudentWrite,
)
from classync_contracts.identity import MembershipAuthorizationError, VerifiedPrincipal
from classync_persistence import schema
from classync_persistence.academic_periods import PostgresAcademicPeriods
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from pydantic import ValidationError
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


def test_0029_keeps_every_earlier_activity_event_and_adds_three(database):
    earlier = {
        "academic.period.created", "academic.period.archived", "academic.record.created",
        "academic.record.updated", "academic.record.deleted", "academic.calendar.saved",
        "scheduling.draft.saved", "scheduling.publication.published",
        "academic.student.created", "academic.student.updated", "academic.student.deleted",
    }
    added = {"academic.period.cloned", "scheduling.restriction.saved", "academic.roster.imported"}
    with transaction(database.engine("boot")) as db:
        definition = db.scalar(text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname='administrator_activity_event_type_check'"
        ))
    assert set(re.findall(r"'([a-z_.]+)'::text", definition)) == earlier | added


def _activity(database, event):
    with transaction(database.engine("boot")) as db:
        return db.scalar(text(
            "SELECT count(*) FROM classsync_scheduling.administrator_activity "
            "WHERE event_type=:e"
        ), {"e": event})


def _statuses(runtime, ids):
    return {
        item: runtime.roster_page(PERIOD_ID, search=item)["items"][0]["enrollment_status"]
        for item in ids
    }


def test_bulk_status_skips_matching_rows_audits_changes_and_is_atomic(database):
    runtime = database.repository("runtime")
    ids = [row["student_id"] for row in runtime.roster_page(PERIOD_ID, limit=3)["items"]]
    revision = runtime.snapshot(PERIOD_ID).period.revision

    def command(status, students, expected):
        return RosterBulkStatus(
            expected_period_revision=expected, student_ids=students, enrollment_status=status
        )

    runtime.bulk_roster_status(PERIOD_ID, command("inactive", ids[:1], revision))
    before = _activity(database, "academic.student.updated")
    result = runtime.bulk_roster_status(PERIOD_ID, command("inactive", ids, revision + 1))
    assert result == {"updated": 2, "skipped": 1, "period_revision": revision + 2}
    assert set(_statuses(runtime, ids).values()) == {"inactive"}
    assert _activity(database, "academic.student.updated") == before + 2
    again = runtime.bulk_roster_status(PERIOD_ID, command("inactive", ids, revision + 2))
    assert again == {"updated": 0, "skipped": 3, "period_revision": revision + 2}

    with pytest.raises(AcademicError) as stale:
        runtime.bulk_roster_status(PERIOD_ID, command("active", ids, revision))
    assert stale.value.status == 409
    with pytest.raises(AcademicError) as unknown:
        runtime.bulk_roster_status(PERIOD_ID, command("active", [*ids, "99-99999"], revision + 2))
    assert unknown.value.status == 404
    assert set(_statuses(runtime, ids).values()) == {"inactive"}
    with pytest.raises(ValidationError):
        command("active", [f"90-{n:05}" for n in range(501)], 1)


def _csv(section, rows):
    header = "student_id,full_name,email,section,enrollment_status\n"
    return header + "".join(
        f"{student},{name},{email},{section},{status}\n" for student, name, email, status in rows
    )


def _label(runtime, section):
    sections = runtime.roster_page(PERIOD_ID)["sections"]
    return next(s["label"] for s in sections if s["id"] == section.id)


def test_import_preview_reports_row_errors_and_commit_requires_the_same_rows(database):
    runtime = database.repository("runtime")
    label = _label(runtime, _section(runtime))
    existing = runtime.roster_page(PERIOD_ID)["items"][0]
    bad = _csv(label, [
        ("91-00001", "Fine Person", "Fine.Person@Example.EDU", "unverified"),
        ("91-00001", "Repeat Id", "other@example.edu", "unverified"),
        ("91-00002", "Repeat Email", "fine.person@example.edu", "unverified"),
        (existing["student_id"], "Taken Id", "taken@example.edu", "unverified"),
        ("91-00003", "Taken Email", existing["registered_email"], "unverified"),
        ("wrong", "", "not-an-email", "graduated"),
    ]) + "91-00004,No Section,nobody@example.edu,NOPE-9Z,active\n"
    preview = runtime.preview_roster_import(PERIOD_ID, RosterImportPreview(csv=bad))
    errors = [bool(row["errors"]) for row in preview["rows"]]
    assert errors == [False, True, True, True, True, True, True]
    assert preview["rows"][0]["email"] == "fine.person@example.edu"
    assert preview["rows_hash"] is None and preview["invalid"] == 6
    with pytest.raises(AcademicError) as malformed:
        runtime.preview_roster_import(PERIOD_ID, RosterImportPreview(csv="a,b\n1,2\n"))
    assert malformed.value.status == 422

    good = _csv(label, [
        ("91-00011", "First Import", "first.import@example.edu", "active"),
        ("91-00012", "Second Import", "second.import@example.edu", ""),
    ])
    preview = runtime.preview_roster_import(PERIOD_ID, RosterImportPreview(csv=good))
    assert preview["invalid"] == 0 and preview["total"] == 2

    def commit(content, digest, revision):
        return runtime.commit_roster_import(PERIOD_ID, RosterImportCommit(
            csv=content, rows_hash=digest, expected_period_revision=revision,
        ))

    with pytest.raises(AcademicError) as mismatch:
        commit(good.replace("First Import", "Edited Import"), preview["rows_hash"],
               preview["period_revision"])
    assert mismatch.value.code == "roster_import_changed"
    with pytest.raises(AcademicError) as stale:
        commit(good, preview["rows_hash"], preview["period_revision"] - 1)
    assert stale.value.status == 409
    assert not runtime.roster_page(PERIOD_ID, search="91-0001")["items"]

    assert commit(good, preview["rows_hash"], preview["period_revision"])["imported"] == 2
    rows = runtime.roster_page(PERIOD_ID, search="91-0001")["items"]
    assert [(r["student_id"], r["enrollment_status"]) for r in rows] == [
        ("91-00011", "active"), ("91-00012", "unverified"),
    ]
    assert _activity(database, "academic.roster.imported") == 1
    # Importing the same file again reports duplicates instead of changing anything.
    assert runtime.preview_roster_import(PERIOD_ID, RosterImportPreview(csv=good))["invalid"] == 2


def test_import_accepts_the_row_limit_in_one_transaction_and_rejects_more(database):
    runtime = database.repository("runtime")
    label = _label(runtime, _section(runtime, year=1))

    def rows(count):
        return _csv(label, [
            (f"92-{n:05}", f"Bulk Person {n}", f"bulk.{n}@example.edu", "unverified")
            for n in range(count)
        ])

    with pytest.raises(AcademicError) as over:
        runtime.preview_roster_import(PERIOD_ID, RosterImportPreview(csv=rows(2001)))
    assert over.value.status == 422
    content = rows(2000)
    preview = runtime.preview_roster_import(PERIOD_ID, RosterImportPreview(csv=content))
    assert preview["invalid"] == 0
    started = perf_counter()
    result = runtime.commit_roster_import(PERIOD_ID, RosterImportCommit(
        csv=content, rows_hash=preview["rows_hash"],
        expected_period_revision=preview["period_revision"],
    ))
    print(f"\n2,000-row import commit: {perf_counter() - started:.2f} s")
    assert result["imported"] == 2000
    assert runtime.roster_page(PERIOD_ID, search="92-0")["total"] == 2000


def _identity_state(database):
    with transaction(database.engine("boot")) as db:
        students = db.execute(text(
            "SELECT s.id,s.person_id,s.registered_email,s.enrollment_status,p.display_name "
            "FROM classsync_identity.students s JOIN classsync_identity.people p "
            "ON p.tenant_id=s.tenant_id AND p.id=s.person_id ORDER BY s.id"
        )).all()
        people = db.scalar(text("SELECT count(*) FROM classsync_identity.people"))
    return {row[0]: tuple(row) for row in students}, people


def _enrollments(repo, period):
    rules = next(e.record for e in repo.snapshot(period).records if e.record.kind == "constraints")
    return {item.student_id: item for item in rules.enrollments}


def test_continuing_students_join_a_cloned_period_without_new_identities(database):
    runtime = database.repository("runtime")
    source = _enrollments(runtime, PERIOD_ID)
    clone = runtime.clone_period(PERIOD_ID, PeriodClone(title="Continuing term")).period.id
    assert _enrollments(runtime, clone) == {}
    sections = {e.record.id: e.record for e in runtime.snapshot(clone).records
                if e.record.kind == "sections"}
    labels = {s["id"]: s["label"] for s in runtime.roster_page(PERIOD_ID)["sections"]}
    seeded = runtime.roster_page(PERIOD_ID, search="24-001", limit=5)["items"]
    first, second, third = seeded[:3]
    before, people = _identity_state(database)

    def body(item, **changes):
        return RosterStudentWrite(**{
            "expected_period_revision": runtime.snapshot(clone).period.revision,
            "student_id": item["student_id"],
            "full_name": item["display_name"],
            "email": item["registered_email"],
            "year_level": item["year_level"],
            "section_id": item["section_id"],
            **changes,
        })

    # Identity mismatches are refused and nothing is written.
    for changes in ({"full_name": "Somebody Else"}, {"email": "other@example.edu"}):
        with pytest.raises(AcademicError) as mismatch:
            runtime.create_roster_student(clone, body(first, **changes))
        assert mismatch.value.code == "student_id_conflict"
    assert _enrollments(runtime, clone) == {}

    # A different spacing or letter case is the same person; the record is not rewritten.
    added = runtime.create_roster_student(clone, body(
        first, full_name=f"  {first['display_name'].upper()}  ", enrollment_status="inactive"
    ))
    assert added == {"continuing": True, "enrollment_status": first["enrollment_status"]}
    with pytest.raises(AcademicError) as duplicate:
        runtime.create_roster_student(clone, body(first))
    assert duplicate.value.code == "student_roster_duplicate"

    section = sections[second["section_id"]]
    other_cohort = next(
        s for s in sections.values()
        if s.program_id == section.program_id and s.year_level != section.year_level
    )
    content = "student_id,full_name,email,section,enrollment_status\n" + "".join(
        f"{item['student_id']},{item['display_name']},{item['registered_email']},"
        f"{labels[item['section_id']]},{status}\n"
        for item, status in ((second, ""), (third, "inactive"))
    ) + f"93-00001,Brand New,brand.new@example.edu,{labels[second['section_id']]},active\n"
    preview = runtime.preview_roster_import(clone, RosterImportPreview(csv=content))
    assert [row["action"] for row in preview["rows"]] == [
        "enroll_existing", "enroll_existing", "create_new",
    ]
    assert (preview["invalid"], preview["enroll_existing"], preview["create_new"]) == (0, 2, 1)
    assert preview["rows"][1]["enrollment_status"] == third["enrollment_status"]
    assert "is not applied" in preview["rows"][1]["note"]

    conflicts = (
        "student_id,full_name,email,section\n"
        f"{first['student_id']},{first['display_name']},{first['registered_email']},"
        f"{labels[first['section_id']]}\n"
        f"{second['student_id']},Wrong Name,{second['registered_email']},"
        f"{labels[second['section_id']]}\n"
        f"{third['student_id']},{third['display_name']},{third['registered_email']},"
        f"{labels[other_cohort.id]}\n"
    )
    refused = runtime.preview_roster_import(clone, RosterImportPreview(csv=conflicts))
    messages = [" ".join(row["errors"]) for row in refused["rows"]]
    assert "already enrolled in this period" in messages[0]
    assert "does not match" in messages[1]
    assert section.curriculum_version_id and "cohort differs" in messages[2]

    result = runtime.commit_roster_import(clone, RosterImportCommit(
        csv=content, rows_hash=preview["rows_hash"],
        expected_period_revision=preview["period_revision"],
    ))
    assert (result["imported"], result["created"], result["enrolled_existing"]) == (3, 1, 2)

    enrolled = _enrollments(runtime, clone)
    assert set(enrolled) == {
        first["student_id"], second["student_id"], third["student_id"], "93-00001",
    }
    # Earlier-period enrollments and records are exactly as they were; one identity is new.
    assert _enrollments(runtime, PERIOD_ID) == source
    after, people_after = _identity_state(database)
    assert people_after == people + 1
    assert set(after) - set(before) == {"93-00001"}
    assert {key: after[key] for key in before} == before

    # Removing a continuing student from the new period keeps the shared record.
    runtime.delete_roster_student(
        clone, first["student_id"], runtime.snapshot(clone).period.revision
    )
    assert _identity_state(database)[0][first["student_id"]] == before[first["student_id"]]
    assert _enrollments(runtime, PERIOD_ID) == source


def test_a_record_outside_your_periods_cannot_be_enrolled(database):
    """Removing it later could delete a record another Administrator still relies on."""
    runtime = database.repository("runtime")
    section = _section(runtime)
    with transaction(database.engine("boot")) as db:
        execute(db, "INSERT INTO classsync_identity.people(tenant_id,id,display_name) "
                    "VALUES (:t,'p-outside','Outside Record')", t=TENANT)
        execute(db, "INSERT INTO classsync_identity.students "
                    "(tenant_id,id,person_id,registered_email,enrollment_status,"
                    "verification_source) VALUES "
                    "(:t,'94-00001','p-outside','outside@example.edu','unverified','unverified')",
                t=TENANT)
    request = _student(runtime, section, "94-00001", name="Outside Record").model_copy(
        update={"email": "outside@example.edu"}
    )
    with pytest.raises(AcademicError) as refused:
        runtime.create_roster_student(PERIOD_ID, request)
    assert refused.value.code == "student_id_conflict"
    assert "not in any of your academic periods" in str(refused.value)
    assert not runtime.roster_page(PERIOD_ID, search="94-00001")["items"]
