"""FastAPI composition of verified identity and current server-side membership.

No test/emulator provider is shipped here. Unconfigured membership fails closed;
P2b/P3 must provide a qualified authoritative repository before institutional use.
"""

import re
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .identity import (
    CurrentMembershipLookup,
    MembershipAuthorizationError,
    MembershipErrorCode,
    VerifiedPrincipal,
    current_membership,
)
from .models import UserRole
from .token_verification import (
    AdapterTrust,
    FirebaseTokenVerifier,
    TokenErrorCode,
    TokenVerificationError,
    TokenVerifier,
)


class IdentityAccessError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        self.code = code
        super().__init__(
            status, message, headers={"WWW-Authenticate": "Bearer"} if status == 401 else None
        )


async def identity_error_response(request: Request, error: IdentityAccessError):
    return JSONResponse(
        status_code=error.status_code,
        headers=error.headers,
        content={
            "error": {
                "code": error.code,
                "message": error.detail,
                "requestId": getattr(request.state, "request_id", None),
            }
        },
    )


def install_identity_errors(app: FastAPI):
    app.add_exception_handler(IdentityAccessError, identity_error_response)


class UnconfiguredMembershipLookup:
    trust = AdapterTrust.AUTHORITATIVE

    def lookup_current(self, *, tenant_id: str, uid: str):
        raise MembershipAuthorizationError(MembershipErrorCode.UNAVAILABLE)


@dataclass(frozen=True)
class AuthorizationAdapters:
    verifier: TokenVerifier
    memberships: CurrentMembershipLookup


def _unavailable():
    return IdentityAccessError(503, "identity_unavailable", "University access is unavailable")


def request_identity(request: Request, settings, required_role: UserRole | None = None) -> dict:
    header = request.headers.get("Authorization", "")
    if not header:
        raise IdentityAccessError(401, "authentication_required", "Authentication is required")
    match = re.fullmatch(r"(?i:Bearer) ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)", header)
    adapters = getattr(request.app.state, "authorization_adapters", None)
    if adapters is None:
        adapters = AuthorizationAdapters(
            FirebaseTokenVerifier(settings), UnconfiguredMembershipLookup()
        )
    test_allowed = (
        getattr(settings, "classsync_env", None) == "test"
        and getattr(settings, "enable_test_identity_adapters", False) is True
    )
    # Only explicitly injected local-test emulator verification accepts unsigned
    # emulator JWTs. Ambient environment variables cannot enable this parsing.
    if match is None and test_allowed and isinstance(adapters, AuthorizationAdapters) and (
        getattr(adapters.verifier, "trust", None) is AdapterTrust.EMULATOR
    ):
        match = re.fullmatch(r"(?i:Bearer) ([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.)", header)
    if match is None or len(header) > 16_384:
        raise IdentityAccessError(401, "invalid_token", "Invalid authentication token")
    if not isinstance(adapters, AuthorizationAdapters):
        raise _unavailable()
    for adapter, expected in [
        (adapters.verifier, AdapterTrust.FIREBASE),
        (adapters.memberships, AdapterTrust.AUTHORITATIVE),
    ]:
        trust = getattr(adapter, "trust", None)
        if trust is not expected and not (
            test_allowed and trust in {AdapterTrust.TEST, AdapterTrust.EMULATOR}
        ):
            raise _unavailable()
    try:
        principal = adapters.verifier.verify(match[1])
        if type(principal) is not VerifiedPrincipal:
            raise TokenVerificationError(TokenErrorCode.UNAVAILABLE)
    except TokenVerificationError as error:
        if error.code == TokenErrorCode.UNAVAILABLE:
            raise _unavailable() from error
        raise IdentityAccessError(401, error.code.value, "Invalid authentication token") from error
    except Exception as error:
        raise _unavailable() from error
    tenant = getattr(settings, "institutional_tenant_id", None)
    if not isinstance(tenant, str) or not tenant.strip():
        raise _unavailable()
    try:
        membership = current_membership(principal, tenant, adapters.memberships)
    except MembershipAuthorizationError as error:
        status = 503 if error.code == MembershipErrorCode.UNAVAILABLE else 403
        message = (
            "University access is unavailable" if status == 503 else "Current membership required"
        )
        raise IdentityAccessError(status, error.code.value, message) from error
    selected = required_role or request.headers.get("X-ClassSync-Role")
    if selected is None:
        if len(membership.roles) != 1:
            raise IdentityAccessError(403, "role_selection_required", "Select an authorized role")
        selected = next(iter(membership.roles))
    try:
        role = UserRole(selected)
    except ValueError as error:
        raise IdentityAccessError(
            403, "membership_denied", "Current membership required"
        ) from error
    if role not in membership.roles:
        raise IdentityAccessError(403, "membership_denied", "Current membership required")
    if (role == UserRole.STUDENT and not membership.student_id) or (
        role == UserRole.TEACHER and not membership.faculty_id
    ):
        raise IdentityAccessError(
            403, "record_membership_required", "Current academic membership required"
        )
    return {
        "uid": principal.uid,
        "tenant_id": membership.tenant_id,
        "role": role.value,
        "membership_revision": membership.revision,
        **({"student_id": membership.student_id} if role == UserRole.STUDENT else {}),
        **({"faculty_id": membership.faculty_id} if role == UserRole.TEACHER else {}),
    }
