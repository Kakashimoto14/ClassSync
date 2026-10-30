import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.models import UserRole
from classync_persistence.membership_changes import audit_actor, change_membership_grants


@pytest.mark.parametrize("roles", [[], frozenset(), frozenset({"administrator"}),
                                  frozenset({UserRole.STUDENT, "unknown"})])
def test_grant_changes_cannot_coerce_unknown_or_empty_roles_into_authority(roles):
    with pytest.raises(ValueError, match="known grants"):
        change_membership_grants(None, tenant_id="tenant", uid="uid", expected_revision=1,
                                 roles=roles, actor=VerifiedPrincipal(uid="synthetic-actor"))


@pytest.mark.parametrize("actor", [None, "uid", {"uid": "uid"},
                                  VerifiedPrincipal(uid="a" * 129)])
def test_audit_context_requires_an_explicit_bounded_verified_principal(actor):
    with pytest.raises(ValueError, match="audit actor"):
        audit_actor(None, actor)
