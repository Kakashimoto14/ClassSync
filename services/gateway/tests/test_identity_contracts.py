"""Synthetic contract doubles only; no production identity provider or database."""

import pytest
from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipErrorCode,
    MembershipSnapshot,
    VerifiedPrincipal,
    authorize_current_membership,
)
from classync_contracts.models import UserRole
from pydantic import ValidationError


def snapshot(**changes):
    return MembershipSnapshot(
        **{
            "uid": "synthetic-uid",
            "tenant_id": "synthetic-tenant",
            "person_id": "synthetic-person",
            "roles": ["student"],
            "state": "active",
            "revision": 1,
            **changes,
        }
    )


class Lookup:
    def __init__(self, membership):
        self.membership = membership
        self.calls = []

    def lookup_current(self, **key):
        self.calls.append(key)
        return self.membership


def authorize(repository, role=UserRole.STUDENT, **changes):
    return authorize_current_membership(
        changes.get("principal", VerifiedPrincipal(uid="synthetic-uid")),
        changes.get("tenant_id", "synthetic-tenant"),
        role,
        repository,
    )


@pytest.mark.parametrize("role", list(UserRole))
def test_each_current_grant_can_authorize_without_using_academic_person_as_uid(role):
    repository = Lookup(snapshot(roles=[role]))
    context = authorize(repository, role)
    assert context.membership.person_id != context.principal.uid
    assert context.required_role == role
    assert repository.calls == [{"tenant_id": "synthetic-tenant", "uid": "synthetic-uid"}]
    with pytest.raises(ValidationError):
        context.required_role = UserRole.ADMINISTRATOR


@pytest.mark.parametrize(
    "membership",
    [
        None,
        snapshot(state="inactive"),
        snapshot(state="revoked"),
        snapshot(roles=[]),
        snapshot(roles=["teacher"]),
        snapshot(uid="other-uid"),
        snapshot(tenant_id="other-tenant"),
    ],
)
def test_verified_uid_alone_cannot_authorize_or_cross_membership_boundaries(membership):
    with pytest.raises(MembershipAuthorizationError) as caught:
        authorize(Lookup(membership))
    assert caught.value.code == MembershipErrorCode.DENIED


def test_each_call_reads_current_membership_and_observes_revocation():
    repository = Lookup(snapshot())
    authorize(repository)
    repository.membership = snapshot(state="revoked", revision=2)
    with pytest.raises(MembershipAuthorizationError):
        authorize(repository)
    assert len(repository.calls) == 2


def test_repository_failure_is_unavailable_without_claims_or_sample_fallback():
    class BrokenLookup:
        def lookup_current(self, **key):
            raise RuntimeError("synthetic private driver detail")

    with pytest.raises(MembershipAuthorizationError) as caught:
        authorize(BrokenLookup())
    assert caught.value.code == MembershipErrorCode.UNAVAILABLE
    assert str(caught.value) == "membership_unavailable"


def test_invalid_adapter_response_is_unavailable():
    with pytest.raises(MembershipAuthorizationError) as caught:
        authorize(Lookup({"role": "administrator"}))
    assert caught.value.code == MembershipErrorCode.UNAVAILABLE


@pytest.mark.parametrize("changes", [{"uid": ""}, {"uid": " "}, {"uid": 3}])
def test_principal_rejects_malformed_uid(changes):
    with pytest.raises(ValidationError):
        VerifiedPrincipal(**changes)


@pytest.mark.parametrize("field", ["role", "tenant_id", "person_id"])
def test_client_membership_fields_cannot_be_embedded_in_principal(field):
    with pytest.raises(ValidationError):
        VerifiedPrincipal(uid="synthetic-uid", **{field: "administrator"})


@pytest.mark.parametrize(
    "changes",
    [
        {"roles": ["owner"]},
        {"revision": 0},
        {"revision": True},
        {"tenant_id": " "},
        {"person_id": " "},
    ],
)
def test_invalid_membership_data_rejected(changes):
    with pytest.raises(ValidationError):
        snapshot(**changes)


def test_snapshot_and_nested_grants_are_immutable():
    membership = snapshot()
    with pytest.raises(ValidationError):
        membership.uid = "other-uid"
    with pytest.raises(AttributeError):
        membership.roles.add(UserRole.ADMINISTRATOR)


@pytest.mark.parametrize(
    "changes",
    [
        {"role": "owner"},
        {"role": "student"},
        {"tenant_id": " "},
        {"principal": {"uid": "synthetic-uid"}},
        {"principal": snapshot()},
    ],
)
def test_invalid_authorization_inputs_fail_before_lookup(changes):
    repository = Lookup(snapshot())
    with pytest.raises(MembershipAuthorizationError):
        authorize(repository, **changes)
    assert repository.calls == []
