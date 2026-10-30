"""Current membership lookup; intentionally not installed into service runtime yet."""

from classync_contracts.identity import MembershipSnapshot
from classync_contracts.token_verification import AdapterTrust
from sqlalchemy import Connection, Engine, text

from .database import transaction


def identity_context(connection: Connection, *, tenant_id: str, uid: str):
    """Caller supplies server-bound tenant and verified UID, never request grants."""
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("Explicit tenant required")
    if not isinstance(uid, str) or not uid.strip():
        raise ValueError("Verified UID required")
    connection.execute(text(
        "SELECT set_config('classsync.tenant_id', :tenant, true), "
        "set_config('classsync.uid', :uid, true)"
    ), {"tenant": tenant_id, "uid": uid})


class PostgresMembershipLookup:
    trust = AdapterTrust.AUTHORITATIVE

    def __init__(self, engine: Engine, *, firebase_project_id: str):
        if not firebase_project_id or not firebase_project_id.strip():
            raise ValueError("Explicit verifier project binding required")
        self.engine = engine
        self.firebase_project_id = firebase_project_id

    def lookup_current(self, *, tenant_id: str, uid: str) -> MembershipSnapshot | None:
        # A fresh transaction/read for every call; outages propagate to the P2a
        # authorization boundary as unavailable. No cache, token claims or sample.
        with transaction(self.engine) as connection:
            identity_context(connection, tenant_id=tenant_id, uid=uid)
            row = connection.execute(text("""
                SELECT m.tenant_id, m.uid, m.person_id, m.student_id, m.faculty_id,
                       m.roles, m.state, m.revision
                FROM classsync_identity.memberships m
                JOIN classsync_identity.tenants t ON t.id = m.tenant_id
                WHERE m.tenant_id = :tenant AND m.uid = :uid
                    AND t.firebase_project_id = :project
            """), {"tenant": tenant_id, "uid": uid, "project": self.firebase_project_id})
            membership = row.mappings().one_or_none()
            return MembershipSnapshot(**membership) if membership is not None else None
