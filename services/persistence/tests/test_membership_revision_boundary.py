from types import SimpleNamespace

import pytest
from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_persistence.membership_changes import (
    MembershipRevisionConflict,
    change_membership_state,
)

ACTOR = VerifiedPrincipal(uid="synthetic-actor")


@pytest.mark.parametrize("fields", [
    {"tenant_id": " "}, {"uid": ""}, {"expected_revision": True}, {"expected_revision": 0},
    {"expected_revision": "1"}, {"state": "active"}, {"actor": {"uid": "forged"}},
])
def test_state_change_requires_explicit_valid_inputs_before_sql(fields):
    values = dict(tenant_id="tenant", uid="uid", expected_revision=1, state=MembershipState.REVOKED,
                  actor=ACTOR)
    with pytest.raises(ValueError):
        change_membership_state(None, **(values | fields))


def test_state_change_requires_caller_transaction():
    with pytest.raises(ValueError, match="Caller-owned transaction"):
        change_membership_state(SimpleNamespace(in_transaction=lambda: False),
                                tenant_id="tenant", uid="uid", expected_revision=1,
                                state=MembershipState.REVOKED, actor=ACTOR)


def test_unmatched_revision_returns_typed_conflict_without_synthetic_success():
    connection = SimpleNamespace(in_transaction=lambda: True, scalar=lambda *args: None,
                                 execute=lambda *args: None)
    with pytest.raises(MembershipRevisionConflict):
        change_membership_state(connection, tenant_id="tenant", uid="uid", expected_revision=1,
                                state=MembershipState.REVOKED, actor=ACTOR)
