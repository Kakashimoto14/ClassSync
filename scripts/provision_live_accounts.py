"""Provision Firebase accounts against an existing, verified ClassSync tenant.

This is an explicit operator command, not an application startup hook. It never
creates a tenant, student roster entry, or faculty record from command-line data.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import secrets
import string
import sys
from getpass import getpass
from typing import Any

from classync_contracts.firebase import FirebaseSettings, initialize_firebase
from classync_persistence.database import postgres_engine
from classync_persistence.schema import migrate
from firebase_admin import auth
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url

STUDENT_ID_PATTERN = re.compile(r"^[0-9]{2}-[0-9]{5}$")
STUDENT_EMAIL_PATTERN = re.compile(r"^[a-z]+(?:\.[a-z]+)*@student\.pnm\.edu\.ph$")
GENERAL_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
CONFIRMATION_TEXT = "PROVISION LIVE CLASSSYNC ACCOUNTS"
BOOTSTRAP_ACTOR = "bootstrap:provision_live_accounts"


def validate_database_target(value: str) -> tuple[URL, str]:
    """Accept only an explicit remote PostgreSQL endpoint with TLS enabled."""
    try:
        url = make_url(value)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        try:
            is_loopback = ipaddress.ip_address(url.host).is_loopback if url.host else False
        except ValueError:
            is_loopback = False
        if (
            url.drivername != "postgresql+psycopg"
            or not url.host
            or not url.port
            or not url.username
            or not url.password
            or "." not in url.host
            or url.host.lower() in {"localhost", "host.docker.internal"}
            or is_loopback
            or not url.database
        ):
            raise ValueError
        query = dict(url.query)
        if set(query) - {"sslmode"}:
            raise ValueError
        sslmode = query.get("sslmode")
        if isinstance(sslmode, tuple) or sslmode not in {"require", "verify-full"}:
            raise ValueError
        return url.set(query={}), sslmode
    except Exception:
        raise ValueError(
            "DATABASE_URL must be a remote PostgreSQL URL with sslmode=require or verify-full"
        ) from None


def validate_student_identity(student_id: str, email: str) -> tuple[str, str]:
    student_id = student_id.strip()
    email = email.strip()
    if not STUDENT_ID_PATTERN.fullmatch(student_id):
        raise ValueError("Student Number must use YY-NNNNN format.")
    if not STUDENT_EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Student email must use the lowercase student.pnm.edu.ph format.")
    return student_id, email


def validate_student_roster_record(student_id: str, email: str, row: dict[str, Any] | None) -> str:
    if (
        not row
        or row.get("id") != student_id
        or row.get("registered_email") != email
        or row.get("enrollment_status") != "active"
        or not row.get("person_id")
    ):
        raise ValueError(
            "Student provisioning requires an active Registrar record with the exact "
            "registered email."
        )
    return str(row["person_id"])


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(32))


def action_actor(*, operator_uid: str | None, bootstrap_first_admin: bool, admin_only: bool) -> str:
    if bootstrap_first_admin and admin_only and not operator_uid:
        return BOOTSTRAP_ACTOR
    if (
        operator_uid
        and 1 <= len(operator_uid) <= 128
        and not any(ch.isspace() for ch in operator_uid)
    ):
        return operator_uid
    raise ValueError(
        "Supply an existing Administrator --operator-uid, or use the explicitly marked "
        "first-Administrator bootstrap mode."
    )


def validate_password(value: str) -> str:
    if (
        len(value) < 12
        or len(value) > 128
        or not value.isascii()
        or not value.isprintable()
    ):
        raise ValueError("Passwords must be 12–128 printable ASCII characters without line breaks.")
    return value


def _email(value: str, *, student: bool = False) -> str:
    value = value.strip().lower()
    pattern = STUDENT_EMAIL_PATTERN if student else GENERAL_EMAIL_PATTERN
    if not pattern.fullmatch(value):
        raise ValueError("Enter a valid institutional account email.")
    return value


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True, help="Existing ClassSync tenant ID")
    parser.add_argument("--admin-email", help="Administrator Firebase email")
    parser.add_argument("--admin-password", help="Optional password; prefer the secure prompt")
    parser.add_argument("--teacher-email", help="Faculty Firebase email")
    parser.add_argument("--teacher-password", help="Optional password; prefer the secure prompt")
    parser.add_argument("--teacher-faculty-id", help="Existing verified faculty identity ID")
    parser.add_argument("--student-id", help="Student Number in YY-NNNNN format")
    parser.add_argument("--student-email", help="Email already present on an active roster record")
    parser.add_argument("--student-password", help="Optional password; prefer the secure prompt")
    parser.add_argument(
        "--operator-uid", help="Existing active Administrator Firebase UID performing this grant"
    )
    parser.add_argument(
        "--bootstrap-first-administrator",
        action="store_true",
        help="Record the initial admin grant with an explicit bootstrap actor marker",
    )
    parser.add_argument(
        "--confirm-live-provisioning",
        metavar="PHRASE",
        help=f"Required exact confirmation phrase: {CONFIRMATION_TEXT}",
    )
    parser.add_argument(
        "--confirm-tenant-id",
        help="Repeat --tenant-id to confirm the target tenant before migration and writes",
    )
    return parser.parse_args()


def _credential(args: argparse.Namespace, option: str, role: str) -> str:
    provided = getattr(args, option)
    if provided is None:
        try:
            provided = getpass(f"Set {role} password (blank generates a secure password): ")
        except EOFError:
            provided = ""
        if not provided:
            return generate_password()
    return validate_password(provided)


def _set_identity_context(
    connection, tenant_id: str, uid: str | None = None, actor_uid: str | None = None
) -> None:
    connection.execute(
        text("SELECT set_config('classsync.tenant_id', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )
    if uid is not None:
        connection.execute(text("SELECT set_config('classsync.uid', :uid, true)"), {"uid": uid})
    if actor_uid is not None:
        connection.execute(
            text("SELECT set_config('classsync.actor_uid', :actor_uid, true)"),
            {"actor_uid": actor_uid},
        )


def _preflight(engine, tenant_id: str, firebase_project_id: str, args: argparse.Namespace):
    with engine.begin() as connection:
        role = (
            connection.execute(
                text("""SELECT r.rolsuper, r.rolbypassrls
                      FROM pg_roles r WHERE r.rolname = current_user""")
            )
            .mappings()
            .one()
        )
        if role["rolsuper"] or role["rolbypassrls"]:
            raise RuntimeError(
                "Use the dedicated non-superuser, non-BYPASSRLS migration/provisioning role."
            )
        _set_identity_context(connection, tenant_id)
        tenant = (
            connection.execute(
                text("SELECT firebase_project_id FROM classsync_identity.tenants WHERE id=:tenant"),
                {"tenant": tenant_id},
            )
            .mappings()
            .one_or_none()
        )
        if not tenant or tenant["firebase_project_id"] != firebase_project_id:
            raise RuntimeError("The existing tenant does not match the Firebase project.")
        profiles = {}
        if args.student_id:
            row = (
                connection.execute(
                    text("""SELECT id, registered_email, enrollment_status, person_id,
                                 password_configured
                          FROM classsync_identity.students WHERE tenant_id=:tenant AND id=:id"""),
                    {"tenant": tenant_id, "id": args.student_id},
                )
                .mappings()
                .one_or_none()
            )
            profiles["student"] = validate_student_roster_record(
                args.student_id, args.student_email, row
            )
        if args.teacher_email:
            row = (
                connection.execute(
                    text("""SELECT id, person_id FROM classsync_identity.faculty
                          WHERE tenant_id=:tenant AND id=:id"""),
                    {"tenant": tenant_id, "id": args.teacher_faculty_id},
                )
                .mappings()
                .one_or_none()
            )
            if not row or not row["person_id"]:
                raise RuntimeError(
                    "Teacher provisioning requires the supplied existing faculty identity record."
                )
            profiles["teacher"] = str(row["person_id"])
        return profiles


def _membership(
    connection, tenant_id, uid, person_id, role, *, actor_uid, student_id=None, faculty_id=None
):
    _set_identity_context(connection, tenant_id, uid, actor_uid)
    if role == "administrator":
        connection.execute(
            text("""INSERT INTO classsync_identity.people (tenant_id,id)
                      VALUES (:tenant,:person) ON CONFLICT (tenant_id,id) DO NOTHING"""),
            {"tenant": tenant_id, "person": person_id},
        )
    result = connection.execute(
        text("""INSERT INTO classsync_identity.memberships
                    (tenant_id,uid,person_id,student_id,faculty_id,roles,state,revision)
                 VALUES (:tenant,:uid,:person,:student,:faculty,ARRAY[:role]::text[],'active',1)
                 ON CONFLICT (tenant_id,uid) DO UPDATE
                    SET state='active', revision=classsync_identity.memberships.revision+1
                 WHERE classsync_identity.memberships.person_id=EXCLUDED.person_id
                   AND classsync_identity.memberships.student_id
                       IS NOT DISTINCT FROM EXCLUDED.student_id
                   AND classsync_identity.memberships.faculty_id
                       IS NOT DISTINCT FROM EXCLUDED.faculty_id
                   AND classsync_identity.memberships.roles=EXCLUDED.roles"""),
        {
            "tenant": tenant_id,
            "uid": uid,
            "person": person_id,
            "student": student_id,
            "faculty": faculty_id,
            "role": role,
        },
    )
    if result.rowcount != 1:
        raise RuntimeError(
            "Existing membership has a different role or record link; refusing to replace it."
        )
    if student_id:
        connection.execute(
            text("""UPDATE classsync_identity.students SET password_configured=true
                      WHERE tenant_id=:tenant AND id=:student"""),
            {"tenant": tenant_id, "student": student_id},
        )


def _firebase_account(app, email: str, password: str) -> tuple[str, bool]:
    try:
        existing = auth.get_user_by_email(email, app=app)
    except auth.UserNotFoundError:
        created = auth.create_user(email=email, password=password, email_verified=True, app=app)
        return created.uid, True
    updated = auth.update_user(
        existing.uid, email=email, password=password, email_verified=True, app=app
    )
    return updated.uid, False


def _verified_operator(engine, tenant_id: str, operator_uid: str) -> str:
    if not operator_uid or len(operator_uid) > 128 or any(ch.isspace() for ch in operator_uid):
        raise ValueError("Operator UID is malformed.")
    with engine.begin() as connection:
        _set_identity_context(connection, tenant_id, operator_uid)
        row = (
            connection.execute(
                text("""SELECT roles,state FROM classsync_identity.memberships
                      WHERE tenant_id=:tenant AND uid=:uid"""),
                {"tenant": tenant_id, "uid": operator_uid},
            )
            .mappings()
            .one_or_none()
        )
        if not row or row["state"] != "active" or "administrator" not in row["roles"]:
            raise RuntimeError(
                "The operator UID must have an active Administrator membership in this tenant."
            )
    return operator_uid


def _print_summary(accounts: list[tuple[str, str, str, str]]) -> None:
    print("\nProvisioned credentials — save them in an approved password manager")
    print("Role          Student Number  Email                                      Password")
    print(f"{'-' * 12}  {'-' * 14}  {'-' * 41}  {'-' * 32}")
    for role, identifier, email, password in accounts:
        print(f"{role:<12}  {identifier or '—':<14}  {email:<41}  {password}")


def main() -> int:
    args = _arguments()
    if args.confirm_live_provisioning != CONFIRMATION_TEXT:
        print(
            f"Refusing to write. Re-run with --confirm-live-provisioning '{CONFIRMATION_TEXT}'.",
            file=sys.stderr,
        )
        return 2
    if args.confirm_tenant_id != args.tenant_id:
        print("Refusing to write. Repeat the target with --confirm-tenant-id.", file=sys.stderr)
        return 2
    if not (args.admin_email or args.teacher_email or args.student_id or args.student_email):
        print("Select at least one account to provision.", file=sys.stderr)
        return 2
    if bool(args.student_id) != bool(args.student_email):
        print("--student-id and --student-email must be supplied together.", file=sys.stderr)
        return 2
    if bool(args.teacher_email) != bool(args.teacher_faculty_id):
        print(
            "--teacher-email and --teacher-faculty-id must be supplied together.", file=sys.stderr
        )
        return 2
    admin_only = bool(args.admin_email) and not args.teacher_email and not args.student_id
    if args.bootstrap_first_administrator and not admin_only:
        print(
            "First-Administrator bootstrap mode can provision only an Administrator account.",
            file=sys.stderr,
        )
        return 2
    if not os.environ.get("DATABASE_URL") or not os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"):
        print(
            "Set DATABASE_URL and FIREBASE_SERVICE_ACCOUNT_JSON in the operator environment.",
            file=sys.stderr,
        )
        return 2
    if os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
        print(
            "Refusing live provisioning while Firebase Auth Emulator is configured.",
            file=sys.stderr,
        )
        return 2

    try:
        database_url, sslmode = validate_database_target(os.environ["DATABASE_URL"])
        requested = []
        if args.admin_email:
            requested.append(
                ("administrator", _email(args.admin_email), None, "administrator", None)
            )
        if args.teacher_email:
            requested.append(
                ("teacher", _email(args.teacher_email), None, "teacher", args.teacher_faculty_id)
            )
        if args.student_id:
            student_id, student_email = validate_student_identity(
                args.student_id, args.student_email
            )
            requested.append(("student", student_email, student_id, "student", None))
        passwords = {}
        for role, email, *_ in requested:
            option = "admin_password" if role == "administrator" else role + "_password"
            passwords[email] = _credential(args, option, role)

        service_account = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
        settings = FirebaseSettings(firebase_service_account_json=json.dumps(service_account))
        app = initialize_firebase(settings)
        if not app.project_id:
            raise RuntimeError("Firebase service account does not identify a project.")

        engine = postgres_engine(database_url, connect_args={"sslmode": sslmode})
        try:
            with engine.begin() as connection:
                role = (
                    connection.execute(
                        text("""SELECT r.rolsuper, r.rolbypassrls FROM pg_roles r
                              WHERE r.rolname=current_user""")
                    )
                    .mappings()
                    .one()
                )
                if role["rolsuper"] or role["rolbypassrls"]:
                    raise RuntimeError("Use a non-superuser, non-BYPASSRLS database role.")
                migrate(connection, target="head")
            profiles = _preflight(engine, args.tenant_id, app.project_id, args)
            actor_uid = (
                action_actor(
                    operator_uid=args.operator_uid,
                    bootstrap_first_admin=args.bootstrap_first_administrator,
                    admin_only=admin_only,
                )
                if args.bootstrap_first_administrator
                else _verified_operator(engine, args.tenant_id, args.operator_uid or "")
            )

            firebase_records = {}
            created_users = []
            try:
                for _, email, *_ in requested:
                    uid, created = _firebase_account(app, email, passwords[email])
                    firebase_records[email] = (uid, created)
                    if created:
                        created_users.append(uid)
                with engine.begin() as connection:
                    for role, email, identifier, membership_role, linked_id in requested:
                        uid, _ = firebase_records[email]
                        if role == "administrator":
                            _membership(
                                connection,
                                args.tenant_id,
                                uid,
                                uid,
                                membership_role,
                                actor_uid=actor_uid,
                            )
                        elif role == "teacher":
                            _membership(
                                connection,
                                args.tenant_id,
                                uid,
                                profiles["teacher"],
                                membership_role,
                                actor_uid=actor_uid,
                                faculty_id=linked_id,
                            )
                        else:
                            _membership(
                                connection,
                                args.tenant_id,
                                uid,
                                profiles["student"],
                                membership_role,
                                actor_uid=actor_uid,
                                student_id=identifier,
                            )
            except Exception:
                for uid in created_users:
                    try:
                        auth.delete_user(uid, app=app)
                    except Exception:
                        pass
                raise
            accounts = []
            for role, email, identifier, _, _ in requested:
                accounts.append((role, identifier or "", email, passwords[email]))
            _print_summary(accounts)
            print(f"Tenant: {args.tenant_id} · Firebase project: {app.project_id} · TLS: {sslmode}")
            print("Database migration: head (0001–0020).")
            print("Existing student roster or faculty identity evidence was required.")
            return 0
        finally:
            engine.dispose()
    except Exception as error:
        # Provider exceptions can contain connection URLs, account data, or request values.
        print(
            f"Provisioning failed safely: {type(error).__name__} (details omitted).",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
