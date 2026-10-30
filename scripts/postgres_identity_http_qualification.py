"""Offline SDK plus real PostgreSQL through Gateway ASGI requests; synthetic only."""

import argparse
import json
from pathlib import Path

import pytest
from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_contracts.models import UserRole
from classync_contracts.request_authorization import AuthorizationAdapters
from classync_persistence.database import transaction
from classync_persistence.membership_changes import (
    change_membership_grants,
    change_membership_state,
)
from classync_persistence.memberships import PostgresMembershipLookup, identity_context
from fastapi.testclient import TestClient
from sqlalchemy import text

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from services.testing.offline_firebase import offline_firebase


def exercise(connection):
    identity = identity_exercise(connection)
    from services.gateway.app import main as gateway

    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    actor = VerifiedPrincipal(uid="uid-admin")

    class CountingLookup(PostgresMembershipLookup):
        calls = 0

        def lookup_current(self, **parameters):
            self.calls += 1
            return super().lookup_current(**parameters)

    repository = CountingLookup(runtime, firebase_project_id="synthetic-project")

    def state(expected, value):
        with transaction(owner) as session:
            identity_context(session, tenant_id="tenant-a", uid="uid-a")
            return change_membership_state(
                session, tenant_id="tenant-a", uid="uid-a", expected_revision=expected,
                state=value, actor=actor,
            )

    try:
        require(state(2, MembershipState.ACTIVE) == 3, "Synthetic fixture activation failed")
        with pytest.MonkeyPatch.context() as patch, offline_firebase(patch) as sdk:
            verifier, encoded, user, _ = sdk
            settings = gateway.Settings(
                _env_file=None, classsync_env="test", institutional_tenant_id="tenant-a",
                enable_test_identity_adapters=False, firebase_project_id="synthetic-project",
                firebase_service_account_json=None, firebase_client_email=None,
                firebase_private_key=None,
            )
            patch.setattr(gateway, "settings", settings)
            patch.setattr(gateway.app.state, "authorization_adapters",
                          AuthorizationAdapters(verifier, repository), raising=False)
            token = encoded(sub="uid-a", student_id="forged", faculty_id="forged")
            with TestClient(gateway.app) as client:
                def request(status, role=None, *, signed=token, code=None):
                    headers = {"X-Tenant-ID": "tenant-b"}
                    if signed is not None:
                        headers["Authorization"] = "Bearer " + signed
                    if role:
                        headers["X-ClassSync-Role"] = role
                    response = client.get(
                        "/api/v1/auth/me?tenant_id=tenant-b&role=administrator", headers=headers,
                    )
                    require(response.status_code == status, f"HTTP {status}: {response.text}")
                    if code:
                        require(response.json()["error"]["code"] == code, "Wrong denial code")
                    return response.json()

                request(403, code="role_selection_required")
                for role, key, value in (("student", "student_id", "student-a"),
                                         ("teacher", "faculty_id", "faculty-a")):
                    require(request(200, role)["data"] == {
                        "uid": "uid-a", "tenant_id": "tenant-a", "role": role,
                        key: value, "membership_revision": 3,
                    }, "Signed/client claims changed current record authority")
                for role in ("administrator", "superadmin"):
                    request(403, role)
                require(request(200, signed=encoded(sub="uid-admin", role="student"))["data"]
                        ["role"] == "administrator", "Separate administrator UID failed")
                request(403, signed=encoded(sub="absent"))
                before = repository.calls
                parts = token.split(".")
                parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
                for invalid in (None, "malformed", encoded(sub="uid-a", exp=1),
                                encoded(sub="uid-a", iss="https://attacker.invalid"),
                                encoded(sub="uid-a", aud="other-project"), ".".join(parts)):
                    request(401, "student", signed=invalid)
                user.disabled = True
                request(401, "student")
                user.disabled = False
                require(repository.calls == before, "Invalid identity reached PostgreSQL")
                with transaction(owner) as session:
                    identity_context(session, tenant_id="tenant-a", uid="uid-a")
                    require(change_membership_grants(
                        session, tenant_id="tenant-a", uid="uid-a", expected_revision=3,
                        roles=frozenset({UserRole.STUDENT}), actor=actor,
                    ) == 4, "Grant withdrawal failed")
                request(403, "teacher")
                require(request(200, "student")["data"]["membership_revision"] == 4,
                        "Same signed token cached former revision")
                state(4, MembershipState.INACTIVE)
                request(403, "student")
                state(5, MembershipState.REVOKED)
                request(403, "student")
                with transaction(owner) as session:
                    session.execute(text(
                        f"REVOKE SELECT ON classsync_identity.tenants FROM {connection.runtime}"
                    ))
                try:
                    error = request(503, "student", code="membership_unavailable")
                    rendered = json.dumps(error)
                    require(all(secret not in rendered for secret in
                                (token, connection.runtime, "SELECT", "permission denied")),
                            "Private database/token details leaked")
                finally:
                    with transaction(owner) as session:
                        session.execute(text(
                            f"GRANT SELECT ON classsync_identity.tenants TO {connection.runtime}"
                        ))
                require(state(6, MembershipState.ACTIVE) == 7, "Fixture reactivation failed")
                require(request(200, "student")["data"]["membership_revision"] == 7,
                        "Correct tenant/project control must authorize the same token")
                settings.institutional_tenant_id = "absent"
                request(403, "student")
                settings.institutional_tenant_id = None
                request(503, "student")
                settings.institutional_tenant_id = "tenant-a"
                wrong = PostgresMembershipLookup(runtime, firebase_project_id="other-project")
                patch.setattr(gateway.app.state, "authorization_adapters",
                              AuthorizationAdapters(verifier, wrong))
                request(403, "student")
                patch.setattr(gateway.app.state, "authorization_adapters",
                              AuthorizationAdapters(verifier, repository))
                request(200, "student")
        return {"identity": identity, "offline_sdk_asgi_current_postgres": True,
                "forged_claims_and_role_selection": True, "invalid_identity_before_db": True,
                "same_token_current_grants_state_revision": True,
                "database_outage_http503_redacted": True, "tenant_project_denied": True,
                "emulator_or_live_identity_acceptance": False}
    finally:
        runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("Output must be a new file in an existing directory")
    evidence = qualify(args.bin, exercise)
    with args.output.open("x") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
