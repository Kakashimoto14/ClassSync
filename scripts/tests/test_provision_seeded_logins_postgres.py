"""Seeded-login provisioning against a throwaway PostgreSQL cluster and a fake Firebase.

The seed, row-level security, unique indexes, audit trigger, roster functions, Gateway session
and published timetable are all real. Only Firebase Auth is replaced. Nothing here connects to
a configured or hosted database.
"""

import csv
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand
from classync_contracts.request_authorization import AuthorizationAdapters
from classync_contracts.scheduling import SaveDraftRequest, scheduling_input_hash
from classync_contracts.token_verification import AdapterTrust
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import PostgresMembershipLookup, identity_context
from fastapi.testclient import TestClient
from firebase_admin import auth
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts import provision_seeded_logins as seeded
from scripts.seed_campus_data import PERIOD_ID, apply_seed, stable_uuid
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.gateway.app import main as gateway_main
from services.gateway.app.onboarding_repository import OnboardingRepository
from services.scheduling.app import main as scheduling_main
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT, ADMIN = "cdm", "demo-classsync-logins", "admin-uid"
DOMAIN = "faculty.example.edu"


class FakeAuth:
    """In-memory stand-in for `firebase_admin.auth`; records every write."""

    UserNotFoundError = auth.UserNotFoundError

    def __init__(self):
        self.users, self.writes = {}, []

    def add(self, email, uid, *, verified=True, password="original-password"):
        self.users[uid] = SimpleNamespace(
            uid=uid, email=email, email_verified=verified, disabled=False, password=password
        )
        return self.users[uid]

    def by_email(self, email):
        return next((u for u in self.users.values() if u.email == email), None)

    def get_user_by_email(self, email, app=None):
        user = self.by_email(email)
        if user is None:
            raise self.UserNotFoundError("missing")
        return user

    def create_user(self, *, email, password, email_verified, app=None):
        assert self.by_email(email) is None
        self.writes.append(("create", email))
        uid = f"fb-{uuid4().hex}"
        return self.add(email, uid, verified=email_verified, password=password)

    def update_user(self, uid, *, password, email_verified, app=None):
        self.writes.append(("update", self.users[uid].email))
        self.users[uid].password, self.users[uid].email_verified = password, email_verified
        return self.users[uid]

    def delete_user(self, uid, app=None):
        self.writes.append(("delete", self.users[uid].email))
        del self.users[uid]


@pytest.fixture(scope="module")
def world(cluster):  # noqa: F811
    provisioned = provision(cluster)
    engine = provisioned.engine
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

    # The migration owner is the role that seeds and provisions a hosted database.
    apply_seed(repository("migrator"))
    snapshot = repository("runtime").snapshot(PERIOD_ID)
    inputs = academic_readiness(snapshot).inputs
    result = generate_week(inputs)
    assert result.solver_status in {"feasible", "optimal"}
    drafts = repository("runtime", PostgresDraftRepository)
    drafts.remember_run(inputs, result)
    draft, _ = drafts.save(SaveDraftRequest(
        run_id=result.run_id, input_hash=result.input_hash, title="Seeded login runtime",
        idempotency_key="login-runtime-draft",
    ))
    repository("runtime", PostgresPublicationRepository).publish(PublicationCommand(
        draft_id=draft.id, dataset="institutional", expected_version=0,
        expected_academic_revision=snapshot.period.revision,
        idempotency_key="login-runtime-publish", calendar=snapshot.period.calendar,
    ), commit=True)
    try:
        yield SimpleNamespace(
            engine=engine, repository=repository, assignments=result.assignments,
            input_hash=result.input_hash,
            data_version=inputs.data_version, draft_id=draft.id,
            calendar=snapshot.period.calendar,
        )
    finally:
        for item in provisioned.engines.values():
            item.dispose()


@contextmanager
def boot(world):
    with transaction(world.engine("boot")) as db:
        yield db


def provisioning(world, firebase, credentials, *argv, user="migrator", project=PROJECT,
                 operator=ADMIN, ignored=lambda _: True):
    options = seeded.parse_arguments(["--tenant-id", TENANT, "--operator-uid", operator, *argv])
    return seeded.run(
        options, engine=world.engine(user),
        accounts=seeded.FirebaseAccounts(object(), firebase, sleep=lambda _: None),
        project_id=project, credentials_path=credentials, ignored=ignored,
    )


def apply(*argv):
    return ["--apply", "--confirm-defense-tenant", TENANT, *argv]


def memberships(world):
    with boot(world) as db:
        return {
            row.uid: (row.student_id, row.faculty_id, tuple(row.roles), row.state, row.revision)
            for row in db.execute(text("SELECT * FROM classsync_identity.memberships"))
        }


def student(world, student_id):
    with boot(world) as db:
        return db.execute(text(
            "SELECT person_id,registered_email,enrollment_status,verification_source,"
            "password_configured FROM classsync_identity.students WHERE id=:id"
        ), {"id": student_id}).mappings().one()


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["email"]: row for row in csv.DictReader(handle)}


def email_of(student_id):
    return f"student.{student_id[:2]}.{student_id[3:]}@student.pnm.edu.ph"


@pytest.fixture(scope="module")
def section_run(world, tmp_path_factory):
    """One real apply of BSIT-3A, shared by the assertions below."""
    firebase = FakeAuth()
    credentials = tmp_path_factory.mktemp("local") / "seeded-logins.csv"
    argv = ("--section", "BSIT-3A", "--faculty-email-domain", DOMAIN, "--activate-enrollment")
    before = memberships(world)
    dry = provisioning(world, firebase, credentials, *argv)
    dry_evidence = SimpleNamespace(
        writes=list(firebase.writes), memberships=memberships(world) == before,
        csv=credentials.exists(), actions={t.action for t in dry.targets},
        status=student(world, "24-00101")["enrollment_status"],
    )
    report = provisioning(world, firebase, credentials, *apply(*argv))
    return SimpleNamespace(
        firebase=firebase, credentials=credentials, argv=argv, report=report, dry=dry_evidence
    )


def test_dry_run_writes_nothing(section_run):
    dry = section_run.dry
    assert dry.writes == [] and dry.memberships and not dry.csv
    assert dry.actions == {"create"} and dry.status == "unverified"


def test_apply_binds_activates_and_stores_credentials_only_in_the_file(
    world, section_run, capsys
):
    report = section_run.report
    students = [t for t in report.targets if t.role == "student"]
    teachers = [t for t in report.targets if t.role == "teacher"]
    assert report.exit_code == 0 and len(students) == 12 and teachers
    assert {t.outcome for t in report.targets} == {"created"}
    assert report.activated == 12

    row = student(world, "24-00101")
    assert row["enrollment_status"] == "active" and row["password_configured"] is True
    assert row["verification_source"] == "unverified"

    stored = read_csv(section_run.credentials)
    assert len(stored) == len(report.targets)
    bound = memberships(world)
    for target in report.targets:
        user = section_run.firebase.by_email(target.email)
        assert user.email_verified and user.password == stored[target.email]["password"]
        student_id, faculty_id, roles, state, _ = bound[user.uid]
        assert roles == (target.role,) and state == "active"
        assert (student_id or faculty_id) == target.record_id
    assert all(t.email.startswith("faculty.") and t.email.endswith(DOMAIN) for t in teachers)
    with boot(world) as db:
        actors = db.scalars(text(
            "SELECT DISTINCT actor_uid FROM classsync_identity.membership_audit "
            "WHERE subject_uid LIKE 'fb-%'"
        )).all()
    assert actors == [ADMIN]


def test_a_second_run_changes_nothing(world, section_run, capsys):
    firebase, credentials = section_run.firebase, section_run.credentials
    before = (memberships(world), credentials.read_bytes(), list(firebase.writes),
              world.repository("runtime").snapshot(PERIOD_ID).period.revision)
    report = provisioning(world, firebase, credentials, *apply(*section_run.argv))
    after = (memberships(world), credentials.read_bytes(), list(firebase.writes),
             world.repository("runtime").snapshot(PERIOD_ID).period.revision)
    assert before == after
    assert {t.outcome for t in report.targets} == {"unchanged"} and report.activated == 0
    printed = capsys.readouterr().out
    for row in read_csv(credentials).values():
        assert row["password"] not in printed and row["email"] not in printed


def test_activation_makes_the_published_draft_need_regeneration(world, section_run):
    """Known consequence, documented in the runbook: roster activation bumps the period revision,
    which is part of the draft input hash that later publications and approvals revalidate."""
    snapshot = world.repository("runtime").snapshot(PERIOD_ID)
    inputs = academic_readiness(snapshot).inputs
    assert scheduling_input_hash(inputs) != world.input_hash
    # Nothing but the revision stamp differs.
    restored = inputs.model_copy(update={"data_version": world.data_version})
    assert scheduling_input_hash(restored) == world.input_hash
    with pytest.raises(DraftError) as refused:
        world.repository("runtime", PostgresPublicationRepository).publish(PublicationCommand(
            draft_id=world.draft_id, dataset="institutional", expected_version=1,
            expected_academic_revision=snapshot.period.revision,
            idempotency_key="login-runtime-republish", calendar=world.calendar,
        ), commit=False)
    assert refused.value.code == "academic_input_changed"


def _client(monkeypatch, module, world, firebase):
    class Verifier:
        trust = AdapterTrust.FIREBASE

        def verify(self, token):
            user = firebase.users[token.split(".")[1]]
            return VerifiedPrincipal(
                uid=user.uid, email=user.email, email_verified=user.email_verified
            )

    monkeypatch.setattr(module.settings, "institutional_tenant_id", TENANT)
    monkeypatch.setattr(module.settings, "firebase_project_id", PROJECT)
    monkeypatch.setattr(module.app.state, "authorization_adapters", AuthorizationAdapters(
        Verifier(), PostgresMembershipLookup(world.engine("runtime"), firebase_project_id=PROJECT)
    ), raising=False)
    return TestClient(module.app)


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_the_provisioned_session_reads_the_published_schedule(
    world, section_run, monkeypatch, role
):
    taught = {a.teacher_id for a in world.assignments}
    target = next(
        t for t in section_run.report.targets
        if t.role == role and (role == "student" or t.record_id in taught)
    )
    user = section_run.firebase.by_email(target.email)
    headers = {"Authorization": f"Bearer h.{user.uid}.s"}
    gateway = _client(monkeypatch, gateway_main, world, section_run.firebase)
    session = gateway.get("/api/v1/auth/me", headers=headers)
    assert session.status_code == 200, session.text
    claims = session.json()["data"]
    assert claims["role"] == role
    assert claims["student_id" if role == "student" else "faculty_id"] == target.record_id

    scheduling = _client(monkeypatch, scheduling_main, world, section_run.firebase)
    monkeypatch.setattr(
        scheduling_main.settings, "scheduling_database_url", SecretStr("postgresql://unused")
    )
    monkeypatch.setattr(
        scheduling_main.app.state, "scheduling_engine", world.engine("runtime"), raising=False
    )
    periods = scheduling.get("/api/v1/timetables/periods", headers=headers)
    assert periods.status_code == 200, periods.text
    assert [p["id"] for p in periods.json()["periods"]] == [PERIOD_ID]
    calendar = scheduling.get(
        f"/api/v1/timetables/calendar/{PERIOD_ID}",
        params={"start": "2026-09-07", "end": "2026-09-13"}, headers=headers,
    )
    assert calendar.status_code == 200, calendar.text
    assert calendar.json()["occurrences"]


def test_an_activated_student_can_use_student_number_sign_in(world, section_run):
    repository = OnboardingRepository(world.engine("runtime"), tenant=TENANT, project=PROJECT)
    user = section_run.firebase.by_email(email_of("24-00101"))
    assert repository.student_login_email("24-00101") == email_of("24-00101")
    assert repository.student_login_membership_matches(user.uid, "24-00101")


def _hold(world, uid, *, person="p-admin", student_id=None, role="administrator"):
    with boot(world) as db:
        identity_context(db, tenant_id=TENANT, uid=uid)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        if person != "p-admin" and student_id is None:
            execute(db, "INSERT INTO classsync_identity.people(tenant_id,id) VALUES (:t,:p)",
                    t=TENANT, p=person)
        execute(db, "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,student_id,roles,state,revision) VALUES "
                    "(:t,:u,:p,:s,ARRAY[:r],'active',1)",
                t=TENANT, u=uid, p=person, s=student_id, r=role)


def test_an_administrator_account_is_never_touched_even_with_rotation(world, tmp_path):
    firebase = FakeAuth()
    firebase.add(email_of("26-00101"), "second-admin")
    _hold(world, "second-admin", person="p-second-admin")
    before = memberships(world)
    report = provisioning(
        world, firebase, tmp_path / "l.csv",
        *apply("--section", "BSIT-1A", "--students", "1", "--rotate-passwords"),
    )
    (target,) = report.targets
    assert target.outcome == "skipped" and "Administrator" in target.reason
    assert firebase.writes == [] and memberships(world) == before
    assert firebase.users["second-admin"].password == "original-password"


def test_a_record_held_by_another_account_is_reported_and_never_repointed(world, tmp_path):
    firebase = FakeAuth()
    _hold(world, "self-claimed", person=student(world, "25-00101")["person_id"],
          student_id="25-00101", role="student")
    before = memberships(world)
    report = provisioning(
        world, firebase, tmp_path / "l.csv",
        *apply("--section", "BSIT-2A", "--students", "1", "--activate-enrollment"),
    )
    (target,) = report.targets
    assert target.outcome == "skipped" and "another account" in target.reason
    assert firebase.writes == [] and memberships(world) == before
    assert student(world, "25-00101")["enrollment_status"] == "unverified"


def test_an_unverified_squatting_account_needs_an_explicit_takeover(world, tmp_path):
    firebase, credentials = FakeAuth(), tmp_path / "l.csv"
    user = firebase.add(email_of("23-00101"), "squatter", verified=False)
    argv = apply("--section", "BSIT-4A", "--students", "1")
    (target,) = provisioning(world, firebase, credentials, *argv).targets
    assert target.outcome == "skipped" and firebase.writes == []
    assert "squatter" not in memberships(world)

    (target,) = provisioning(world, firebase, credentials, *argv, "--rotate-passwords").targets
    assert target.outcome == "linked" and "squatter" in memberships(world)
    assert user.email_verified and user.password != "original-password"
    assert read_csv(credentials)[email_of("23-00101")]["password"] == user.password
    # Rotating a bound account resets the password without touching the membership.
    previous, bound = user.password, memberships(world)["squatter"]
    (target,) = provisioning(world, firebase, credentials, *argv, "--rotate-passwords").targets
    assert target.outcome == "rotated" and user.password != previous
    assert memberships(world)["squatter"] == bound


def test_an_owner_supplied_password_is_used_only_when_set(world, tmp_path, monkeypatch):
    monkeypatch.setenv(seeded.PASSWORD_ENV, "Shared-Defense-2026!")
    firebase, credentials = FakeAuth(), tmp_path / "l.csv"
    report = provisioning(
        world, firebase, credentials, *apply("--section", "BSIT-1B", "--students", "2")
    )
    assert [t.outcome for t in report.targets] == ["created", "created"]
    assert {u.password for u in firebase.users.values()} == {"Shared-Defense-2026!"}


def test_a_failed_binding_deletes_the_new_account(world, tmp_path, monkeypatch):
    real = seeded.bind_membership

    def failing(connection, tenant_id, uid, *args, **kwargs):
        if uid.startswith("probe-"):
            return real(connection, tenant_id, uid, *args, **kwargs)
        raise RuntimeError("database went away")

    monkeypatch.setattr(seeded, "bind_membership", failing)
    firebase, credentials = FakeAuth(), tmp_path / "l.csv"
    before = memberships(world)
    report = provisioning(
        world, firebase, credentials, *apply("--section", "BSIT-2B", "--students", "1")
    )
    assert report.exit_code == 1 and report.targets[0].outcome == "failed"
    assert [kind for kind, _ in firebase.writes] == ["create", "delete"]
    assert not firebase.users and memberships(world) == before and not credentials.exists()


def test_row_security_requires_an_audit_actor_and_hides_other_accounts(world, section_run):
    user = section_run.firebase.by_email(email_of("24-00101"))
    with pytest.raises(DBAPIError, match="Explicit audit actor required"):
        with transaction(world.engine("migrator")) as db:
            identity_context(db, tenant_id=TENANT, uid="no-actor")
            execute(db, "INSERT INTO classsync_identity.memberships "
                        "(tenant_id,uid,person_id,roles,state,revision) VALUES "
                        "(:t,'no-actor','p-admin',ARRAY['administrator'],'active',1)", t=TENANT)
    with transaction(world.engine("migrator")) as db:
        identity_context(db, tenant_id=TENANT, uid=ADMIN)
        assert db.scalar(text(
            "SELECT count(*) FROM classsync_identity.memberships WHERE uid=:uid"
        ), {"uid": user.uid}) == 0


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"project": "some-other-project"}, "does not match"),
        ({"user": "boot"}, "non-superuser"),
        ({"operator": "not-an-admin"}, "Administrator membership"),
        ({"ignored": lambda _: False}, "not ignored by git"),
    ],
)
def test_wrong_target_role_operator_or_path_writes_nothing(world, tmp_path, overrides, expected):
    firebase, credentials = FakeAuth(), tmp_path / "l.csv"
    before = memberships(world)
    with pytest.raises(RuntimeError, match=expected):
        provisioning(world, firebase, credentials, *apply("--students", "1"), **overrides)
    assert firebase.writes == [] and memberships(world) == before and not credentials.exists()


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["--program", "NOPE"], "Unknown program"),
        (["--section", "BSIT-9Z"], "No such section"),
        (["--teachers", "1"], "--faculty-email-domain"),
    ],
)
def test_unusable_selections_are_refused(world, tmp_path, argv, expected):
    with pytest.raises(seeded.Refusal, match=expected):
        provisioning(world, FakeAuth(), tmp_path / "l.csv", *argv)


def test_targeting_selects_only_seed_rows(world, tmp_path):
    firebase = FakeAuth()
    with boot(world) as db:
        identity_context(db, tenant_id=TENANT, uid=ADMIN)
        # A hand-edited address no longer matches the seed definition.
        execute(db, "UPDATE classsync_identity.students "
                    "SET registered_email='edited.person@student.pnm.edu.ph' "
                    "WHERE id='24-00113'")
    everyone = provisioning(
        world, firebase, tmp_path / "l.csv", "--all-seeded", "--faculty-email-domain", DOMAIN
    )
    students = {t.record_id for t in everyone.targets if t.role == "student"}
    assert len(students) == 431 and "24-00113" not in students
    assert sum(t.role == "teacher" for t in everyone.targets) == 57
    program = provisioning(
        world, firebase, tmp_path / "l.csv", "--program", "BSIT", "--students", "10"
    )
    assert len(program.targets) == 10
    assert all(t.sections.startswith("BSIT-") for t in program.targets)
    assert firebase.writes == []


def test_the_faculty_identity_is_the_seeded_person(world, section_run):
    teacher = next(t for t in section_run.report.targets if t.role == "teacher")
    assert teacher.person_id == stable_uuid("faculty-person", teacher.record_id)
