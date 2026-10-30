"""Isolated period metadata adapter, not a replacement for academic snapshots.

Identity comes only from the verified-principal boundary. Current administrator,
tenant, project and owner checks are performed by FORCE RLS in the data statement.
Service installation and complete academic repository adaptation are separate.
"""

from datetime import UTC
from uuid import uuid4

from classync_contracts.academic import AcademicPeriod
from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipErrorCode,
    VerifiedPrincipal,
)
from sqlalchemy import Engine, text

from .database import transaction
from .memberships import identity_context


def utc_timestamp(value):
    """Stable contract text independent of the database session's display timezone."""
    return value.astimezone(UTC).isoformat()


class PostgresAcademicPeriods:
    def __init__(self, engine: Engine, *, tenant_id: str, firebase_project_id: str):
        if not isinstance(tenant_id, str) or not 1 <= len(tenant_id.strip()) <= 128:
            raise ValueError("Explicit server tenant required")
        if not isinstance(firebase_project_id, str) or not 1 <= len(
            firebase_project_id.strip()
        ) <= 128:
            raise ValueError("Explicit verifier project required")
        self.engine = engine
        self.tenant_id = tenant_id
        self.project_id = firebase_project_id

    @staticmethod
    def validate_principal(principal):
        if not isinstance(principal, VerifiedPrincipal):
            raise ValueError("Trusted verified principal required")

    def context(self, connection, principal):
        identity_context(connection, tenant_id=self.tenant_id, uid=principal.uid)
        connection.execute(text("SELECT set_config('classsync.project_id', :project, true)"),
                           {"project": self.project_id})

    @staticmethod
    def decode(row):
        return AcademicPeriod(id=row["id"], title=row["title"], revision=row["revision"],
                              created_at=utc_timestamp(row["created_at"]), source="institutional")

    def list_for(self, principal: VerifiedPrincipal):
        self.validate_principal(principal)
        with transaction(self.engine) as connection:
            self.context(connection, principal)
            rows = connection.execute(text("""
                SELECT p.id, p.title, p.revision, p.created_at
                FROM classsync_identity.memberships m
                JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                LEFT JOIN classsync_academic.period_metadata p
                    ON p.tenant_id=m.tenant_id AND p.owner_uid=m.uid
                WHERE m.tenant_id=:tenant AND m.uid=:uid AND m.state='active'
                    AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=:project
                ORDER BY p.created_at, p.id
            """), {"tenant": self.tenant_id, "uid": principal.uid,
                   "project": self.project_id}).mappings().all()
            if not rows:
                raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
            return [self.decode(row) for row in rows if row["id"] is not None]

    def create_for(self, principal: VerifiedPrincipal, *, title: str):
        self.validate_principal(principal)
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
            raise ValueError("A period title of 1 to 160 characters is required")
        with transaction(self.engine) as connection:
            self.context(connection, principal)
            row = connection.execute(text("""
                INSERT INTO classsync_academic.period_metadata (tenant_id, owner_uid, id, title)
                SELECT :tenant, :uid, :id, :title
                FROM classsync_identity.memberships m
                JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                WHERE m.tenant_id=:tenant AND m.uid=:uid AND m.state='active'
                    AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=:project
                RETURNING id, title, revision, created_at
            """), {"tenant": self.tenant_id, "uid": principal.uid,
                   "project": self.project_id,
                   "id": str(uuid4()), "title": title.strip()}).mappings().one_or_none()
            if row is None:
                raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
            return self.decode(row)
