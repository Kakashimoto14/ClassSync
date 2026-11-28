"""Shared Firebase and PostgreSQL helpers for the operator-run provisioning commands.

Used by `provision_live_accounts.py` (one account per run) and `provision_seeded_logins.py`
(owner-authorized defense accounts for seeded records). Nothing here runs at import time or on
service startup.
"""

from __future__ import annotations

import ipaddress

from firebase_admin import auth
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url


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


def validate_password(value: str) -> str:
    if (
        len(value) < 12
        or len(value) > 128
        or not value.isascii()
        or not value.isprintable()
    ):
        raise ValueError("Passwords must be 12–128 printable ASCII characters without line breaks.")
    return value


def require_restricted_role(connection, message: str) -> None:
    """Refuse superusers and BYPASSRLS roles: row-level security must apply to the operator."""
    role = (
        connection.execute(
            text("""SELECT r.rolsuper, r.rolbypassrls
                  FROM pg_roles r WHERE r.rolname = current_user""")
        )
        .mappings()
        .one()
    )
    if role["rolsuper"] or role["rolbypassrls"]:
        raise RuntimeError(message)


def set_identity_context(
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


def require_tenant_project(connection, tenant_id: str, firebase_project_id: str) -> None:
    set_identity_context(connection, tenant_id)
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


def bind_membership(
    connection, tenant_id, uid, person_id, role, *, actor_uid, student_id=None, faculty_id=None
):
    """Insert, or reactivate an identical, single-role membership with audit attribution."""
    set_identity_context(connection, tenant_id, uid, actor_uid)
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


def verified_operator(engine, tenant_id: str, operator_uid: str) -> str:
    if not operator_uid or len(operator_uid) > 128 or any(ch.isspace() for ch in operator_uid):
        raise ValueError("Operator UID is malformed.")
    with engine.begin() as connection:
        set_identity_context(connection, tenant_id, operator_uid)
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


def upsert_firebase_account(app, email: str, password: str, auth_module=auth) -> tuple[str, bool]:
    """Create the account, or reset its password. Returns (uid, created)."""
    try:
        existing = auth_module.get_user_by_email(email, app=app)
    except auth_module.UserNotFoundError:
        created = auth_module.create_user(
            email=email, password=password, email_verified=True, app=app
        )
        return created.uid, True
    updated = auth_module.update_user(
        existing.uid, email=email, password=password, email_verified=True, app=app
    )
    return updated.uid, False
