"""Give existing seeded defense Teachers and Students real ClassSync logins.

Operator-run only. The default is a read-only dry run. `--apply` creates or reuses Firebase Auth
users, binds one single-role membership to each existing seeded faculty/student identity, and can
activate seeded enrollments. It never creates a roster or faculty row, never touches an
Administrator account and never prints a password. See docs/production/SEEDED_LOGINS.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import secrets
import string
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "packages/api-contracts"),
    str(ROOT / "packages/persistence"),
]

import certifi  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from classync_contracts.academic import RosterBulkStatus  # noqa: E402
from classync_contracts.firebase import FirebaseSettings, initialize_firebase  # noqa: E402
from classync_contracts.identity import VerifiedPrincipal  # noqa: E402
from classync_persistence import schema  # noqa: E402
from classync_persistence.database import postgres_engine  # noqa: E402
from firebase_admin import auth, exceptions  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from scripts.lib.identity_provisioning import (  # noqa: E402
    bind_membership,
    require_restricted_role,
    require_tenant_project,
    set_identity_context,
    validate_database_target,
    validate_password,
    verified_operator,
)
from scripts.seed_campus_data import (  # noqa: E402
    PERIOD_ID,
    PERIOD_TITLE,
    build_defense_records,
    load_json,
    stable_uuid,
)
from services.academic.app.postgres_repository import PostgresAcademicRepository  # noqa: E402

CREDENTIALS_PATH = ROOT / ".local" / "seeded-logins.csv"
PASSWORD_ENV = "CLASSSYNC_SEEDED_LOGIN_PASSWORD"
CSV_COLUMNS = ("role", "name", "email", "student_number", "section", "password", "note")
DOMAIN_PATTERN = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
SPECIALS = "!#%^&*_?"
ACTIVATION_CHUNK = 100
MAX_CONSECUTIVE_FAILURES = 5
ROOM_CATALOG = "packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json"


class Refusal(RuntimeError):
    """A deliberate stop whose message is safe to print."""


@dataclass
class Target:
    role: str  # "teacher" or "student"
    record_id: str
    person_id: str
    email: str
    name: str
    sections: str
    enrollment_status: str | None = None
    action: str = ""  # create | link | rotate | unchanged | skip
    reason: str = ""
    uid: str | None = None
    outcome: str = ""  # created | linked | rotated | unchanged | skipped | failed


@dataclass
class Report:
    targets: list = field(default_factory=list)
    activated: int = 0
    activation_failed: int = 0
    not_in_period: int = 0
    exit_code: int = 0


class FirebaseAccounts:
    """Throttled Admin SDK calls; retries only responses that cannot have applied a change."""

    def __init__(self, app, auth_module=auth, *, sleep=time.sleep, interval=0.2, retries=3):
        self.app, self.auth = app, auth_module
        self.sleep, self.interval, self.retries = sleep, interval, retries

    def _call(self, operation, *args, **kwargs):
        for attempt in range(self.retries + 1):
            self.sleep(self.interval)
            try:
                return operation(*args, app=self.app, **kwargs)
            except (exceptions.ResourceExhaustedError, exceptions.UnavailableError):
                if attempt == self.retries:
                    raise
                self.sleep(2**attempt)

    def find(self, email):
        try:
            return self._call(self.auth.get_user_by_email, email)
        except self.auth.UserNotFoundError:
            return None

    def create(self, email, password):
        return self._call(
            self.auth.create_user, email=email, password=password, email_verified=True
        ).uid

    def reset(self, uid, password):
        self._call(self.auth.update_user, uid, password=password, email_verified=True)

    def delete(self, uid):
        self._call(self.auth.delete_user, uid)


def generate_password() -> str:
    """20 random characters containing every class the web password checklist asks for."""
    pools = (string.ascii_uppercase, string.ascii_lowercase, string.digits, SPECIALS)
    required = [secrets.choice(pool) for pool in pools]
    required += [secrets.choice("".join(pools)) for _ in range(20 - 1 - len(required))]
    secrets.SystemRandom().shuffle(required)
    # A leading letter keeps spreadsheet applications from reading the value as a formula.
    return secrets.choice(string.ascii_letters) + "".join(required)


def mask(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def _slug(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return ".".join(re.findall(r"[a-z0-9]+", plain))


def seeded_identities():
    """The identities the defense seed inserts; nothing else may receive a login here."""
    records, students = build_defense_records(PERIOD_ID, load_json(ROOM_CATALOG))
    faculty, used = {}, Counter()
    for record in records:
        if record.kind != "faculty":
            continue
        # Slugs come from the seed definition, so a later name edit cannot change a login.
        slug = _slug(record.name.split("·")[0])
        used[slug] += 1
        faculty[record.id] = {
            "person_id": stable_uuid("faculty-person", record.id),
            "slug": slug if used[slug] == 1 else f"{slug}.{used[slug]}",
        }
    return {s["id"]: s for s in students}, faculty


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def select_targets(db, snapshot, tenant_id, options, report) -> list[Target]:
    seeded_students, seeded_faculty = seeded_identities()
    by_kind = {}
    for entry in snapshot.records:
        by_kind.setdefault(entry.record.kind, {})[entry.record.id] = entry.record
    programs, sections = by_kind.get("programs", {}), by_kind.get("sections", {})
    offerings = by_kind.get("offerings", {})
    faculty_records = by_kind.get("faculty", {})
    rules = next(iter(by_kind.get("constraints", {}).values()), None)
    enrolled = {e.student_id: e.offering_ids for e in (rules.enrollments if rules else [])}

    def label(section):
        program = programs.get(section.program_id)
        return section.custom_label or (
            f"{program.acronym if program else '?'}-{section.year_level}{section.section_letter}"
        )

    wanted = set(sections)
    if options.program:
        matches = {
            p.id for p in programs.values()
            if _normal(options.program) in {_normal(p.acronym), _normal(p.name)}
        }
        if not matches:
            available = ", ".join(sorted(p.acronym for p in programs.values()))
            raise Refusal(f"Unknown program. Programs in this period: {available}")
        wanted = {s for s in wanted if sections[s].program_id in matches}
    if options.section:
        wanted = {s for s in wanted if _normal(label(sections[s])) == _normal(options.section)}
        if not wanted:
            available = ", ".join(sorted(label(s) for s in sections.values()))
            raise Refusal(f"No such section in the selection. Sections: {available}")
    scoped = bool(options.program or options.section)

    def sections_of(offering_ids):
        return {offerings[o].section_id for o in offering_ids if o in offerings} & set(sections)

    def labels(ids):
        return " ".join(sorted(label(sections[s]) for s in ids))

    # A role is included when it has an explicit limit, or when no limit was given at all.
    limited = options.teachers is not None or options.students is not None
    include_teachers = options.teachers is not None or not limited
    include_students = options.students is not None or not limited
    targets: list[Target] = []

    if include_teachers:
        rows = db.execute(
            text("""SELECT f.id, f.person_id, p.display_name
                    FROM classsync_identity.faculty f
                    JOIN classsync_identity.people p
                      ON p.tenant_id=f.tenant_id AND p.id=f.person_id
                    WHERE f.tenant_id=:tenant AND f.id=ANY(CAST(:ids AS text[]))
                    ORDER BY f.id"""),
            {"tenant": tenant_id, "ids": sorted(seeded_faculty)},
        ).mappings().all()
        teachers = []
        for row in rows:
            seeded = seeded_faculty[row["id"]]
            if row["person_id"] != seeded["person_id"]:
                continue
            if row["id"] not in faculty_records:
                report.not_in_period += 1
                continue
            taught = {
                o.section_id for o in offerings.values()
                if row["id"] in o.teacher_ids and o.section_id in sections
            }
            if scoped and not taught & wanted:
                continue
            teachers.append(Target(
                role="teacher", record_id=row["id"], person_id=row["person_id"],
                email=(
                    f"faculty.{seeded['slug']}@{options.faculty_email_domain}"
                    if options.faculty_email_domain else ""
                ),
                name=row["display_name"] or faculty_records[row["id"]].name,
                sections=labels(taught & wanted if scoped else taught),
            ))
        targets += teachers[: options.teachers]

    if include_students:
        rows = db.execute(
            text("""SELECT s.id, s.person_id, s.registered_email, s.enrollment_status,
                           p.display_name
                    FROM classsync_identity.students s
                    JOIN classsync_identity.people p
                      ON p.tenant_id=s.tenant_id AND p.id=s.person_id
                    WHERE s.tenant_id=:tenant AND s.id=ANY(CAST(:ids AS text[]))
                    ORDER BY s.id"""),
            {"tenant": tenant_id, "ids": sorted(seeded_students)},
        ).mappings().all()
        students = []
        for row in rows:
            seeded = seeded_students[row["id"]]
            if (row["person_id"] != seeded["person_id"]
                    or row["registered_email"] != seeded["registered_email"]):
                continue
            own = sections_of(enrolled.get(row["id"], []))
            if not own:
                report.not_in_period += 1
                continue
            if scoped and not own & wanted:
                continue
            students.append(Target(
                role="student", record_id=row["id"], person_id=row["person_id"],
                email=row["registered_email"], name=row["display_name"] or row["id"],
                sections=labels(own), enrollment_status=row["enrollment_status"],
            ))
        targets += students[: options.students]

    if any(t.role == "teacher" for t in targets) and not options.faculty_email_domain:
        raise Refusal("Teacher logins require --faculty-email-domain (there is no default).")
    return targets


def membership_of(engine, tenant_id, uid):
    with engine.begin() as connection:
        set_identity_context(connection, tenant_id, uid)
        return connection.execute(
            text("""SELECT person_id,student_id,faculty_id,roles,state
                    FROM classsync_identity.memberships
                    WHERE tenant_id=:tenant AND uid=:uid"""),
            {"tenant": tenant_id, "uid": uid},
        ).mappings().one_or_none()


def assess(target, *, engine, accounts, tenant_id, operator_uid, rotate):
    """Read-only decision for one target."""
    user = accounts.find(target.email)

    def skip(reason):
        target.action, target.reason = "skip", reason

    if user is None:
        target.action = "create"
        return
    target.uid = user.uid
    if user.uid == operator_uid:
        return skip("protected: this email is the operator's own account")
    membership = membership_of(engine, tenant_id, user.uid)
    if membership and "administrator" in membership["roles"]:
        return skip("protected: this email belongs to an Administrator account")
    if getattr(user, "disabled", False):
        return skip("the existing Firebase account is disabled")
    if membership:
        column = "student_id" if target.role == "student" else "faculty_id"
        if (list(membership["roles"]) != [target.role]
                or membership[column] != target.record_id
                or membership["person_id"] != target.person_id):
            return skip("conflict: this account is already linked to a different record")
        if membership["state"] != "active":
            return skip(f"conflict: membership is {membership['state']}; review it in Admin")
        target.action = "rotate" if rotate else "unchanged"
        return
    if not user.email_verified and not rotate:
        # Binding an unproven account would hand the identity to whoever registered it.
        return skip("an unverified account already uses this email; rerun with --rotate-passwords")
    target.action = "link"


def _link(target, connection, tenant_id, uid, actor_uid):
    column = "student_id" if target.role == "student" else "faculty_id"
    bind_membership(
        connection, tenant_id, uid, target.person_id, target.role,
        actor_uid=actor_uid, **{column: target.record_id},
    )


def record_held_by_another_account(engine, target, tenant_id, operator_uid) -> bool:
    """Row security hides other accounts' memberships, so ask the unique index and roll back."""
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            _link(target, connection, tenant_id, "probe-" + uuid4().hex, operator_uid)
        except IntegrityError as error:
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
            if constraint in {"membership_unique_student_id", "membership_unique_faculty_id"}:
                return True
            raise
        finally:
            transaction.rollback()
    return False


def is_git_ignored(path: Path) -> bool:
    return subprocess.run(
        ["git", "check-ignore", "-q", "--", str(path)],
        cwd=ROOT, capture_output=True, check=False,
    ).returncode == 0


class CredentialFile:
    """Merges rows by email; a stored password is replaced only by a newly set one."""

    def __init__(self, path: Path):
        self.path = path
        self.rows = {}
        if path.exists():
            with path.open(encoding="utf-8", newline="") as handle:
                self.rows = {row["email"]: row for row in csv.DictReader(handle)}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            probe = path.with_name(path.name + ".tmp")
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            if path.exists():
                path.open("a", encoding="utf-8").close()  # fails if a spreadsheet locks it
        except OSError as error:
            raise Refusal(f"Cannot write {path}; close any program using it.") from error

    def record(self, target, password, note):
        if not password and target.email in self.rows:
            return
        name = target.name
        if name[:1] in {"=", "+", "-", "@"}:
            name = "'" + name
        self.rows[target.email] = {
            "role": target.role, "name": name, "email": target.email,
            "student_number": target.record_id if target.role == "student" else "",
            "section": target.sections, "password": password, "note": note,
        }
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                os.chmod(temporary, 0o600)
                writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(self.rows.values())
            os.replace(temporary, self.path)
        except OSError as error:
            # Stop the run: further passwords could not be stored either.
            raise Refusal(
                f"Could not save {self.path}. Close any program using it, then rerun the same "
                "command with --rotate-passwords."
            ) from error


def apply_target(target, *, engine, accounts, tenant_id, operator_uid, credentials, password):
    if target.action == "unchanged":
        target.outcome = "unchanged"
        return
    if target.action in {"create", "link"} and record_held_by_another_account(
        engine, target, tenant_id, operator_uid
    ):
        target.outcome = "skipped"
        target.reason = "conflict: another account already holds this record"
        return
    if target.action == "create":
        secret = password or generate_password()
        uid = accounts.create(target.email, secret)
        try:
            with engine.begin() as connection:
                _link(target, connection, tenant_id, uid, operator_uid)
        except BaseException:
            try:
                accounts.delete(uid)
            except Exception:
                print(f"WARNING: could not remove the new Firebase user for {mask(target.email)}; "
                      "rerun with --rotate-passwords.", file=sys.stderr)
            raise
        target.uid, target.outcome = uid, "created"
        credentials.record(target, secret, "created")
        return
    rotating = target.action == "rotate" or (target.action == "link" and password is not None)
    if rotating:
        secret = password or generate_password()
        # The password changes before any binding, and is recorded as soon as it exists.
        accounts.reset(target.uid, secret)
        credentials.record(target, secret, "password reset")
    if target.action == "rotate":
        target.outcome = "rotated"
        return
    with engine.begin() as connection:
        _link(target, connection, tenant_id, target.uid, operator_uid)
    target.outcome = "linked"
    if not rotating:
        credentials.record(target, "", "existing password kept; --rotate-passwords sets a new one")


def activate(repo, period_id, students, report):
    ids = sorted(t.record_id for t in students)
    for start in range(0, len(ids), ACTIVATION_CHUNK):
        chunk = ids[start : start + ACTIVATION_CHUNK]
        try:
            result = repo.bulk_roster_status(period_id, RosterBulkStatus(
                expected_period_revision=repo.snapshot(period_id).period.revision,
                student_ids=chunk, enrollment_status="active",
            ))
        except Exception as error:
            report.activation_failed += len(chunk)
            print(f"Activation failed for {len(chunk)} students: {type(error).__name__}",
                  file=sys.stderr)
        else:
            report.activated += result["updated"]


def require_current_schema(connection):
    head = ScriptDirectory(str(Path(schema.__file__).parent / "migrations")).get_current_head()
    current = connection.scalar(text("SELECT version_num FROM public.alembic_version"))
    if current != head:
        raise Refusal(f"The database is not at migration head {head}; migrate before provisioning.")


def _find_period(repo, period_id):
    if period_id:
        return period_id
    with repo.session() as db:
        found = db.scalars(
            text("""SELECT id FROM classsync_academic.period_metadata
                    WHERE tenant_id=:tenant AND owner_uid=:owner AND title=:title"""),
            {**repo.keys, "title": PERIOD_TITLE},
        ).all()
    if len(found) != 1:
        raise Refusal(
            "The seeded period was not found for this operator. Use the seeding Administrator's "
            "UID, or pass --period-id."
        )
    return found[0]


def _print_report(report, options):
    targets = report.targets
    counts = Counter(
        (t.role, t.outcome or ("skipped" if t.action == "skip" else t.action)) for t in targets
    )
    print(("APPLIED" if options.apply else "DRY RUN (no writes)") + f": {len(targets)} targets")
    for (role, status), number in sorted(counts.items()):
        print(f"  {role:<8} {status:<10} {number}")
    for target in targets:
        if target.action == "skip" or target.outcome in {"skipped", "failed"}:
            print(f"  - {target.role} {mask(target.email)}: {target.reason}")
    if report.not_in_period:
        print(f"  {report.not_in_period} seeded identities are no longer in this period; ignored.")


def run(options, *, engine, accounts, project_id, credentials_path=CREDENTIALS_PATH,
        ignored=is_git_ignored) -> Report:
    if options.apply:
        if options.confirm_defense_tenant != options.tenant_id:
            raise Refusal("--confirm-defense-tenant must repeat the exact tenant ID.")
        if not ignored(credentials_path):
            raise Refusal(f"{credentials_path} is not ignored by git; refusing to write passwords.")
    with engine.begin() as connection:
        require_restricted_role(connection, "Use a non-superuser, non-BYPASSRLS database role.")
        require_tenant_project(connection, options.tenant_id, project_id)
        require_current_schema(connection)
    verified_operator(engine, options.tenant_id, options.operator_uid)
    repo = PostgresAcademicRepository(
        engine, tenant_id=options.tenant_id, firebase_project_id=project_id,
        principal=VerifiedPrincipal(uid=options.operator_uid),
    )
    period_id = _find_period(repo, options.period_id)
    snapshot = repo.snapshot(period_id)
    report = Report()
    with engine.begin() as connection:
        set_identity_context(connection, options.tenant_id, options.operator_uid)
        report.targets = select_targets(
            connection, snapshot, options.tenant_id, options, report
        )
    if not report.targets:
        raise Refusal("No seeded identities match that selection.")
    common = {"engine": engine, "accounts": accounts, "tenant_id": options.tenant_id,
              "operator_uid": options.operator_uid}

    if not options.apply:
        for target in report.targets:
            assess(target, rotate=options.rotate_passwords, **common)
        _print_report(report, options)
        if options.activate_enrollment:
            pending = sum(
                t.action != "skip" and t.enrollment_status == "unverified" for t in report.targets
            )
            print(f"  would activate up to {pending} unverified seeded enrollments")
        print("Records already held by a different account are detected during --apply.")
        return report

    shared = os.environ.get(PASSWORD_ENV)
    if shared is not None:
        try:
            validate_password(shared)
        except ValueError as error:
            raise Refusal(f"{PASSWORD_ENV}: {error}") from error
    credentials = CredentialFile(credentials_path)
    consecutive = 0
    for target in report.targets:
        try:
            assess(target, rotate=options.rotate_passwords, **common)
            if target.action == "skip":
                target.outcome = "skipped"
            else:
                # A non-None password on a "link" means the operator asked to take it over.
                password = None
                if options.rotate_passwords:
                    password = shared or generate_password()
                elif target.action == "create":
                    password = shared
                apply_target(target, credentials=credentials, password=password, **common)
            consecutive = 0
        except Refusal:
            raise
        except Exception as error:
            # Provider errors can contain URLs, account data or request values.
            target.outcome, target.reason = "failed", type(error).__name__
            consecutive += 1
            if consecutive >= MAX_CONSECUTIVE_FAILURES:
                print("Stopping after repeated failures.", file=sys.stderr)
                break
    if options.activate_enrollment:
        done = {"created", "linked", "rotated", "unchanged"}
        pending = [
            t for t in report.targets
            if t.role == "student" and t.outcome in done and t.enrollment_status == "unverified"
        ]
        activate(repo, period_id, pending, report)
    _print_report(report, options)
    if options.activate_enrollment:
        print(f"  activated enrollments: {report.activated}")
        inactive = sum(t.enrollment_status == "inactive" for t in report.targets)
        if inactive:
            print(f"  left {inactive} inactive enrollments as the Administrator set them")
    print(f"Credentials file: {credentials_path}")
    if report.activation_failed or any(t.outcome == "failed" for t in report.targets):
        report.exit_code = 1
    return report


def _count(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or more")
    return number


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="read-only (default)")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--tenant-id", default=os.environ.get("INSTITUTIONAL_TENANT_ID"))
    parser.add_argument("--confirm-defense-tenant", help="repeat the tenant ID with --apply")
    parser.add_argument("--operator-uid", required=True, help="active Administrator UID")
    parser.add_argument("--faculty-email-domain", help="required when teachers are selected")
    parser.add_argument("--activate-enrollment", action="store_true")
    parser.add_argument("--rotate-passwords", action="store_true")
    parser.add_argument("--program", help="program acronym, for example BSIT")
    parser.add_argument("--section", help="section label, for example BSIT-3A")
    parser.add_argument("--teachers", type=_count, help="first N seeded teachers")
    parser.add_argument("--students", type=_count, help="first N seeded students")
    parser.add_argument("--all-seeded", action="store_true")
    parser.add_argument("--period-id", help=f"defaults to the period titled {PERIOD_TITLE}")
    options = parser.parse_args(argv)
    targeted = any(
        value is not None
        for value in (options.program, options.section, options.teachers, options.students)
    )
    if options.all_seeded == targeted:
        parser.error("choose either --all-seeded or --program/--section/--teachers/--students")
    if not options.tenant_id:
        parser.error("pass --tenant-id or set INSTITUTIONAL_TENANT_ID")
    if options.faculty_email_domain is not None:
        options.faculty_email_domain = options.faculty_email_domain.strip().lower()
        if not DOMAIN_PATTERN.fullmatch(options.faculty_email_domain):
            parser.error("--faculty-email-domain must be a domain such as faculty.example.edu")
    if options.apply and options.confirm_defense_tenant != options.tenant_id:
        parser.error("--apply needs --confirm-defense-tenant with the exact tenant ID")
    return options


def main(argv=None) -> int:
    options = parse_arguments(argv)
    database = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    service_account = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not database or not service_account:
        print("Set MIGRATION_DATABASE_URL (or DATABASE_URL) and FIREBASE_SERVICE_ACCOUNT_JSON.",
              file=sys.stderr)
        return 2
    if os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
        print("Refusing to run while the Firebase Auth Emulator is configured.", file=sys.stderr)
        return 2
    try:
        url, sslmode = validate_database_target(database)
        settings = FirebaseSettings(
            firebase_service_account_json=json.dumps(json.loads(service_account))
        )
        app = initialize_firebase(settings)
        if not app.project_id:
            raise Refusal("The Firebase service account does not identify a project.")
        connect_args = {"sslmode": sslmode}
        if sslmode == "verify-full":
            connect_args["sslrootcert"] = certifi.where()
        engine = postgres_engine(url, connect_args=connect_args)
        try:
            return run(
                options, engine=engine, accounts=FirebaseAccounts(app),
                project_id=app.project_id,
            ).exit_code
        finally:
            engine.dispose()
    except Refusal as error:
        print(str(error), file=sys.stderr)
        return 2
    except Exception as error:
        print(f"Provisioning failed safely: {type(error).__name__} (details omitted).",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
