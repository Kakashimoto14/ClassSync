"""Revision-safe state changes inside an already authorized caller transaction.

This is not a provisioning policy or authorization check. Ordinary membership
readers lack UPDATE permission; no service endpoint exposes this operation yet.
"""

from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_contracts.models import UserRole
from sqlalchemy import Connection, text


class MembershipRevisionConflict(Exception):
    """The scoped membership is absent, invisible or no longer at the expected revision."""


def audit_actor(connection: Connection, actor: VerifiedPrincipal):
    """Record trusted caller provenance; this does not verify or authorize a caller."""
    if not isinstance(actor, VerifiedPrincipal) or len(actor.uid) > 128:
        raise ValueError("Explicit verified-principal audit actor required")
    if not connection.in_transaction():
        raise ValueError("Caller-owned transaction required")
    connection.execute(text("SELECT set_config('classsync.actor_uid', :actor, true)"),
                       {"actor": actor.uid})


def _parameters(connection, tenant_id, uid, expected_revision, actor):
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("Explicit tenant required")
    if not isinstance(uid, str) or not uid.strip():
        raise ValueError("Explicit UID required")
    if type(expected_revision) is not int or expected_revision < 1:
        raise ValueError("Positive strict expected revision required")
    if not isinstance(actor, VerifiedPrincipal) or len(actor.uid) > 128:
        raise ValueError("Explicit verified-principal audit actor required")
    if not connection.in_transaction():
        raise ValueError("Caller-owned transaction required")
    audit_actor(connection, actor)
    return {"tenant": tenant_id, "uid": uid, "expected": expected_revision}


def _revision(revision):
    if revision is None:
        raise MembershipRevisionConflict()
    return revision


def change_membership_state(
    connection: Connection, *, tenant_id: str, uid: str, expected_revision: int,
    state: MembershipState, actor: VerifiedPrincipal,
) -> int:
    if not isinstance(state, MembershipState):
        raise ValueError("Known membership state required")
    parameters = _parameters(connection, tenant_id, uid, expected_revision, actor)
    revision = connection.scalar(text("""
        UPDATE classsync_identity.memberships SET state=:state, revision=revision+1
        WHERE tenant_id=:tenant AND uid=:uid AND revision=:expected
        RETURNING revision
    """), parameters | {"state": state.value})
    return _revision(revision)


def change_membership_grants(
    connection: Connection, *, tenant_id: str, uid: str, expected_revision: int,
    roles: frozenset[UserRole], actor: VerifiedPrincipal,
) -> int:
    """Caller must already have provisioning authority; record-link checks remain in DB."""
    if not isinstance(roles, frozenset) or not roles or any(
        not isinstance(role, UserRole) for role in roles
    ):
        raise ValueError("Explicit nonempty set of known grants required")
    parameters = _parameters(connection, tenant_id, uid, expected_revision, actor)
    revision = connection.scalar(text("""
        UPDATE classsync_identity.memberships SET roles=CAST(:roles AS text[]), revision=revision+1
        WHERE tenant_id=:tenant AND uid=:uid AND revision=:expected
        RETURNING revision
    """), parameters | {"roles": sorted(role.value for role in roles)})
    return _revision(revision)
