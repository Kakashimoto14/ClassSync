"""Internal identity/membership boundary; no role provisioning.

Only a trusted identity verifier may construct VerifiedPrincipal. Deserializing a
request into this model does not verify identity. Institutional repositories and
identity provisioning remain separately gated.
"""

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import UserRole


class _ImmutableContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _SubjectContract(_ImmutableContract):
    uid: str = Field(strict=True, min_length=1)

    @field_validator("uid")
    @classmethod
    def nonblank_uid(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("UID must not be blank")
        return value


class VerifiedPrincipal(_SubjectContract):
    """Trusted verifier output, never a source of tenant roles or record membership."""


class MembershipState(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"


class MembershipSnapshot(_SubjectContract):
    tenant_id: str = Field(strict=True, min_length=1)
    person_id: str | None = Field(default=None, strict=True, min_length=1)
    student_id: str | None = Field(default=None, strict=True, min_length=1)
    faculty_id: str | None = Field(default=None, strict=True, min_length=1)
    roles: frozenset[UserRole]
    state: MembershipState
    revision: int = Field(strict=True, ge=1)

    @field_validator("tenant_id", "person_id", "student_id", "faculty_id")
    @classmethod
    def nonblank_identifier(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Identifier must not be blank")
        return value


class CurrentMembershipLookup(Protocol):
    def lookup_current(self, *, tenant_id: str, uid: str) -> MembershipSnapshot | None:
        """Read current authority; never fall back to token roles or sample data."""
        ...


class MembershipErrorCode(StrEnum):
    DENIED = "membership_denied"
    UNAVAILABLE = "membership_unavailable"


class MembershipAuthorizationError(Exception):
    def __init__(self, code: MembershipErrorCode):
        self.code = code
        super().__init__(code.value)


class AuthorizedMembership(_ImmutableContract):
    principal: VerifiedPrincipal
    membership: MembershipSnapshot
    required_role: UserRole


def authorize_current_membership(
    principal: VerifiedPrincipal,
    tenant_id: str,
    required_role: UserRole,
    repository: CurrentMembershipLookup,
) -> AuthorizedMembership:
    """Recheck current membership for each call; a UID/token role is insufficient.

    Record-level ownership and transaction-bound rechecks remain the caller's
    responsibility. This snapshot must not authorize a later write on its own.
    """
    if not isinstance(principal, VerifiedPrincipal):
        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
    if not isinstance(required_role, UserRole):
        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
    membership = current_membership(principal, tenant_id, repository)
    if required_role not in membership.roles:
        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
    return AuthorizedMembership(
        principal=principal, membership=membership, required_role=required_role
    )


def current_membership(
    principal: VerifiedPrincipal, tenant_id: str, repository: CurrentMembershipLookup
) -> MembershipSnapshot:
    """A current, active tenant/UID snapshot, without choosing an institutional role."""
    if not isinstance(principal, VerifiedPrincipal):
        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
    try:
        membership = repository.lookup_current(tenant_id=tenant_id, uid=principal.uid)
    except Exception as error:
        raise MembershipAuthorizationError(MembershipErrorCode.UNAVAILABLE) from error
    if membership is not None and not isinstance(membership, MembershipSnapshot):
        raise MembershipAuthorizationError(MembershipErrorCode.UNAVAILABLE)
    if (
        membership is None
        or membership.uid != principal.uid
        or membership.tenant_id != tenant_id
        or membership.state != MembershipState.ACTIVE
        or not membership.roles
    ):
        raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
    return membership
