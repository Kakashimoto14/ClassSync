"""Owned demo Auth Emulator plus new PostgreSQL and Gateway lifecycle checks."""

import argparse
import json
import os
import re
import tempfile
import time
from pathlib import Path

import httpx
import pytest
from classync_contracts.firebase import FirebaseSettings
from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_contracts.request_authorization import AuthorizationAdapters
from classync_contracts.token_verification import FirebaseTokenVerifier, TokenVerificationError
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor, change_membership_state
from classync_persistence.memberships import PostgresMembershipLookup, identity_context
from fastapi.testclient import TestClient
from firebase_admin import auth
from sqlalchemy import text

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from services.testing.emulator_firebase import emulator_firebase


def exercise(connection, *, project, endpoint):
    foundation = identity_exercise(connection)
    from services.gateway.app import main as gateway

    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    try:
        with pytest.MonkeyPatch.context() as patch, emulator_firebase(
            patch, project=project, endpoint=endpoint,
        ) as sdk:
            verifier, app = sdk
            with httpx.Client(
                base_url=f"http://{endpoint}", trust_env=False, timeout=5,
            ) as transport:
                response = transport.post(
                    "/identitytoolkit.googleapis.com/v1/accounts:signUp",
                    params={"key": "synthetic-emulator-key"}, json={"returnSecureToken": True},
                )
                require(response.status_code == 200, "Owned emulator anonymous signup failed")
                identity = response.json()
            token, uid = identity["idToken"], identity["localId"]
            require(token.endswith("."), "Expected actual unsigned Auth Emulator JWT")
            require(verifier.verify(token).uid == uid, "SDK emulator identity did not match signup")
            settings = gateway.Settings(
                _env_file=None, classsync_env="test", institutional_tenant_id="tenant-a",
                enable_test_identity_adapters=True, firebase_project_id=project,
                firebase_service_account_json=None, firebase_client_email=None,
                firebase_private_key=None,
            )
            repository = PostgresMembershipLookup(runtime, firebase_project_id=project)
            patch.setattr(gateway, "settings", settings)
            patch.setattr(gateway.app.state, "authorization_adapters",
                          AuthorizationAdapters(verifier, repository), raising=False)
            with TestClient(gateway.app) as client:
                def request(expected, *, role="student", extra=None):
                    result = client.get("/api/v1/auth/me", headers={
                        "Authorization": "Bearer " + token, "X-ClassSync-Role": role,
                        **(extra or {}),
                    })
                    require(result.status_code == expected,
                            f"Emulator HTTP lifecycle expected{expected} got{result.status_code}")
                    return result.json()

                request(403)  # Real emulator identity has no implicit institutional record.
                with transaction(owner) as session:
                    session.execute(text(
                        "UPDATE classsync_identity.tenants SET firebase_project_id=:project "
                        "WHERE id='tenant-a'"
                    ), {"project": project})
                    identity_context(session, tenant_id="tenant-a", uid=uid)
                    audit_actor(session, VerifiedPrincipal(uid="synthetic-operator"))
                    session.execute(text("""
                        INSERT INTO classsync_identity.memberships
                        VALUES ('tenant-a', :uid, 'person-a', 'student-a', NULL,
                                ARRAY['student'], 'active', 1)
                    """), {"uid": uid})
                require(request(200)["data"] == {
                    "uid": uid, "tenant_id": "tenant-a", "role": "student",
                    "student_id": "student-a", "membership_revision": 1,
                }, "Actual emulator token did not bind current academic record")
                request(403, role="administrator", extra={"X-Tenant-ID": "tenant-b"})
                require(request(200, extra={"X-Tenant-ID": "tenant-b",
                                           "X-Student-ID": "forged"})["data"]["student_id"]
                        == "student-a", "Forged emulator request record selection")
                auth.set_custom_user_claims(uid, {"role": "administrator",
                                                 "tenant_id": "tenant-b"}, app=app)
                with httpx.Client(
                    base_url=f"http://{endpoint}", trust_env=False, timeout=5,
                ) as transport:
                    refreshed = transport.post(
                        "/securetoken.googleapis.com/v1/token",
                        params={"key": "synthetic-emulator-key"},
                        data={"grant_type": "refresh_token",
                              "refresh_token": identity["refreshToken"]},
                    )
                    require(refreshed.status_code == 200, "Synthetic token refresh failed")
                    token = refreshed.json()["id_token"]
                claims = auth.verify_id_token(token, app=app, check_revoked=True)
                require(claims.get("role") == "administrator"
                        and claims.get("tenant_id") == "tenant-b", "Forged claim setup failed")
                request(403, role="administrator")
                request(200)
                # Even this valid emulator token is not an institutional identity.
                for environment, enabled in (("production", True), ("test", False)):
                    settings.classsync_env = environment
                    settings.enable_test_identity_adapters = enabled
                    request(401)
                settings.classsync_env = "test"
                settings.enable_test_identity_adapters = True
                try:
                    FirebaseTokenVerifier(FirebaseSettings(
                        firebase_project_id=project, _env_file=None,
                    )).verify(token)
                except TokenVerificationError as error:
                    require(error.code == "identity_unavailable", "Institutional emulator error")
                else:
                    raise RuntimeError("Institutional SDK verifier accepted emulator token")
                auth.update_user(uid, disabled=True, app=app)
                request(401)
                auth.update_user(uid, disabled=False, app=app)
                request(200)
                with transaction(owner) as session:
                    identity_context(session, tenant_id="tenant-a", uid=uid)
                    change_membership_state(
                        session, tenant_id="tenant-a", uid=uid, expected_revision=1,
                        state=MembershipState.REVOKED,
                        actor=VerifiedPrincipal(uid="synthetic-operator"),
                    )
                request(403)
                with transaction(owner) as session:
                    identity_context(session, tenant_id="tenant-a", uid=uid)
                    change_membership_state(
                        session, tenant_id="tenant-a", uid=uid, expected_revision=2,
                        state=MembershipState.ACTIVE,
                        actor=VerifiedPrincipal(uid="synthetic-operator"),
                    )
                request(200)
                # Revoke in a later actual second than authentication; no timestamp
                # fabrication or password/credential creation is involved.
                time.sleep(1.1)
                auth.revoke_refresh_tokens(uid, app=app)
                request(401)
                # A second real anonymous token provides an active positive
                # control immediately before genuine account-endpoint refusal.
                with httpx.Client(
                    base_url=f"http://{endpoint}", trust_env=False, timeout=5,
                ) as transport:
                    response = transport.post(
                        "/identitytoolkit.googleapis.com/v1/accounts:signUp",
                        params={"key": "synthetic-emulator-key"},
                        json={"returnSecureToken": True},
                    )
                    require(response.status_code == 200, "Second anonymous signup failed")
                    second = response.json()
                token, uid = second["idToken"], second["localId"]
                with transaction(owner) as session:
                    identity_context(session, tenant_id="tenant-a", uid=uid)
                    audit_actor(session, VerifiedPrincipal(uid="synthetic-operator"))
                    session.execute(text("""
                        INSERT INTO classsync_identity.memberships
                        VALUES ('tenant-a', :uid, 'person-a', 'student-a', NULL,
                                ARRAY['student'], 'active', 1)
                    """), {"uid": uid})
                request(200)
                root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"])
                print("CLASSSYNC_OWNED_AUTH_STOP", flush=True)
                deadline = time.monotonic() + 10
                acknowledgement = root / "auth-stopped.json"
                while not acknowledgement.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                require(acknowledgement.exists(), "Owned Auth server did not acknowledge stop")
                require(json.loads(acknowledgement.read_text(encoding="utf-8"))
                        == {"endpoint": endpoint, "stopped": True}, "Wrong stopped endpoint")
                error = request(503)["error"]
                require(error["code"] == "identity_unavailable"
                        and token not in json.dumps(error), "Emulator outage leaked/fell back")
            return {"foundation": foundation, "actual_local_auth_emulator": True,
                    "anonymous_identity_no_implicit_membership": True,
                    "current_record_binding": True, "disabled_and_token_revocation": True,
                    "same_token_membership_revocation": True,
                    "forged_authority_denied": True, "actual_account_endpoint_outage": True,
                    "institutional_and_optout_unsigned_denied": True,
                    "production_acceptance": False}
    finally:
        runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("New output file required")
    # Only the owning Node harness supplies this fresh marker and loopback server.
    root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"]).resolve()
    require(root.parent == Path(tempfile.gettempdir()).resolve()
            and re.fullmatch(r"classsync-auth-run-[a-f0-9]{32}", root.name),
            "Not an owned temporary root")
    marker = json.loads((root / "owned-auth.json").read_text(encoding="utf-8"))
    project, endpoint = marker["project"], marker["endpoint"]
    require(os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == endpoint,
            "Owned emulator endpoint mismatch")
    evidence = qualify(args.bin, lambda connection: exercise(
        connection, project=project, endpoint=endpoint,
    ))
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")
    print("Owned Auth Emulator/PostgreSQL/Gateway qualification passed")


if __name__ == "__main__":
    main()
