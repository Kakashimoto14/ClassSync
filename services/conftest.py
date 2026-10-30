"""Disposable identity adapters for local tests; never imported by service runtime."""

import pytest
from classync_contracts.identity import MembershipSnapshot, VerifiedPrincipal
from classync_contracts.models import UserRole
from classync_contracts.request_authorization import AuthorizationAdapters
from classync_contracts.token_verification import AdapterTrust

TEST_TOKEN = "e30.e30.synthetic-signature"


class SyntheticTokenVerifier:
    trust = AdapterTrust.TEST

    def __init__(self, uid):
        self.uid = uid
        self.error = None
        self.calls = 0

    def verify(self, token):
        self.calls += 1
        if self.error:
            raise self.error
        return VerifiedPrincipal(uid=self.uid)


class SyntheticMembershipLookup:
    trust = AdapterTrust.TEST

    def __init__(self, membership):
        self.membership = membership
        self.error = None
        self.calls = []

    def lookup_current(self, *, tenant_id, uid):
        self.calls.append((tenant_id, uid))
        if self.error:
            raise self.error
        return self.membership


@pytest.fixture
def identity_adapters(monkeypatch):
    def install(module, role="administrator", uid="synthetic-user", **fields):
        monkeypatch.setattr(module.settings, "classsync_env", "test")
        monkeypatch.setattr(module.settings, "enable_test_identity_adapters", True)
        monkeypatch.setattr(module.settings, "institutional_tenant_id", "synthetic-tenant")
        membership = MembershipSnapshot(
            **{
                "uid": uid,
                "tenant_id": "synthetic-tenant",
                "roles": [UserRole(role)],
                "state": "active",
                "revision": 1,
                "student_id": "synthetic-student",
                "faculty_id": "synthetic-faculty",
                **fields,
            }
        )
        verifier = SyntheticTokenVerifier(uid)
        repository = SyntheticMembershipLookup(membership)
        monkeypatch.setattr(
            module.app.state,
            "authorization_adapters",
            AuthorizationAdapters(verifier, repository),
            raising=False,
        )
        return verifier, repository

    return install
