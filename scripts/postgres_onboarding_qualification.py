"""Real local Auth Emulator/Gateway/new PostgreSQL account journey. Synthetic only."""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import uvicorn
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.request_authorization import AuthorizationAdapters
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import PostgresMembershipLookup, identity_context
from classync_persistence.schema import migrate
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from services.gateway.app.onboarding_repository import OnboardingRepository
from services.testing.emulator_firebase import emulator_firebase


def exercise(
    connection,
    project,
    endpoint,
    *,
    browser=False,
    scanner=False,
    connected=False,
    postman_only=False,
):
    from services.gateway.app import main as gateway

    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    migrator = "classsync_onboarding_" + uuid4().hex
    checks = []
    try:
        with transaction(owner) as db:
            db.execute(text(f"CREATE ROLE {migrator} NOLOGIN NOSUPERUSER NOBYPASSRLS"))
            db.execute(text(f"GRANT CREATE ON DATABASE postgres TO {migrator}"))
            db.execute(text(f"GRANT USAGE,CREATE ON SCHEMA public TO {migrator}"))
            db.execute(text(f"SET LOCAL ROLE {migrator}"))
            migrate(db)
            migrate(db, target="0013_synthetic_review_period_mode", downgrade=True)
            migrate(db)
        with transaction(owner) as db:
            db.execute(
                text(
                    "INSERT INTO classsync_identity.tenants VALUES "
                    "('tenant-a',:project),('tenant-b',:project)"
                ),
                {"project": project},
            )
            db.execute(
                text(
                    "INSERT INTO classsync_identity.people VALUES "
                    "('tenant-a','admin'),('tenant-a','student'),('tenant-a','faculty'),"
                    "('tenant-b','student')"
                )
            )
            db.execute(
                text(
                    "INSERT INTO classsync_identity.students VALUES "
                    "('tenant-a','student-1','student'),('tenant-b','student-2','student')"
                )
            )
            db.execute(
                text(
                    "INSERT INTO classsync_identity.faculty VALUES "
                    "('tenant-a','faculty-1','faculty')"
                )
            )
            db.execute(text(f"GRANT USAGE ON SCHEMA classsync_identity TO {connection.runtime}"))
            db.execute(
                text(
                    "GRANT SELECT ON classsync_identity.tenants,"
                    "classsync_identity.students,classsync_identity.faculty "
                    f"TO {connection.runtime}"
                )
            )
            db.execute(
                text(
                    "GRANT SELECT,INSERT,UPDATE ON classsync_identity.memberships,"
                    "classsync_identity.account_claims,classsync_identity.faculty_invitations "
                    f"TO {connection.runtime}"
                )
            )
        checks.append("migration_upgrade_downgrade_upgrade")
        with (
            pytest.MonkeyPatch.context() as patch,
            emulator_firebase(
                patch,
                project=project,
                endpoint=endpoint,
            ) as (verifier, _sdk),
            httpx.Client(
                base_url=f"http://{endpoint}",
                trust_env=False,
                timeout=5,
            ) as transport,
        ):

            def firebase(action, body, expected=200):
                result = transport.post(
                    "/identitytoolkit.googleapis.com/v1/accounts:" + action,
                    params={"key": "synthetic-emulator-key"},
                    json=body,
                )
                require(result.status_code == expected, f"Auth {action} expected {expected}")
                return result.json()

            def signup(name):
                return firebase(
                    "signUp",
                    {
                        "email": name + "@synthetic.invalid",
                        "password": "Local-emulator-password-42!",
                        "returnSecureToken": True,
                    },
                )

            def verify(identity):
                firebase(
                    "sendOobCode", {"requestType": "VERIFY_EMAIL", "idToken": identity["idToken"]}
                )
                codes = transport.get(f"/emulator/v1/projects/{project}/oobCodes").json()[
                    "oobCodes"
                ]
                code = next(
                    x["oobCode"]
                    for x in reversed(codes)
                    if x["email"] == identity["email"] and x["requestType"] == "VERIFY_EMAIL"
                )
                firebase("update", {"oobCode": code})
                return firebase(
                    "signInWithPassword",
                    {
                        "email": identity["email"],
                        "password": "Local-emulator-password-42!",
                        "returnSecureToken": True,
                    },
                )

            student, teacher, other, admin = [
                signup(x) for x in ["student", "faculty", "other", "admin"]
            ]
            firebase(
                "signUp",
                {
                    "email": student["email"],
                    "password": "Duplicate-not-created!",
                    "returnSecureToken": True,
                },
                expected=400,
            )
            settings = gateway.Settings(
                _env_file=None,
                classsync_env="test",
                institutional_tenant_id="tenant-a",
                enable_test_identity_adapters=True,
                firebase_project_id=project,
                identity_database_url=None,
            )
            patch.setattr(gateway, "settings", settings)
            patch.setattr(
                gateway.app.state,
                "authorization_adapters",
                AuthorizationAdapters(
                    verifier, PostgresMembershipLookup(runtime, firebase_project_id=project)
                ),
                raising=False,
            )
            patch.setattr(
                gateway.app.state,
                "onboarding_repository",
                OnboardingRepository(runtime, tenant="tenant-a", project=project),
                raising=False,
            )
            with TestClient(gateway.app) as client:

                def api(identity, method, path, expected, body=None):
                    result = client.request(
                        method,
                        "/api/v1/auth/" + path,
                        headers={"Authorization": "Bearer " + identity["idToken"]},
                        **({"json": body} if body is not None else {}),
                    )
                    require(
                        result.status_code == expected,
                        f"{method} {path} expected {expected}, got {result.status_code}: "
                        f"{result.text}",
                    )
                    return result.json().get("data")

                require(
                    client.get("/api/v1/auth/onboarding").status_code == 401,
                    "Missing token accepted",
                )
                require(
                    api(student, "GET", "onboarding", 200)["status"] == "verify-email",
                    "Not pending",
                )
                api(student, "POST", "student-claims", 403, {"student_id": "student-1"})
                api(student, "GET", "me", 403)
                student, teacher, other, admin = map(verify, [student, teacher, other, admin])
                checks.append("real_signup_duplicate_email_oob_verification_pending_no_role")
                with transaction(owner) as db:
                    identity_context(db, tenant_id="tenant-a", uid=admin["localId"])
                    audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
                    db.execute(
                        text(
                            "INSERT INTO classsync_identity.memberships VALUES "
                            "('tenant-a',:uid,'admin',NULL,NULL,ARRAY['administrator'],'active',1)"
                        ),
                        {"uid": admin["localId"]},
                    )
                api(student, "POST", "student-claims", 201, {"student_id": "student-1"})
                api(student, "POST", "student-claims", 409, {"student_id": "student-1"})
                require(api(other, "GET", "onboarding", 200)["claim_state"] is None, "Claim leaked")
                api(student, "GET", "student-claims", 403)
                api(
                    student,
                    "POST",
                    "faculty-invitations",
                    403,
                    {"faculty_id": "faculty-1", "email": teacher["email"]},
                )
                api(
                    admin,
                    "PATCH",
                    "student-claims/" + student["localId"],
                    200,
                    {
                        "approve": True,
                        "verification_reference": "Synthetic approved identity review",
                    },
                )
                require(
                    api(student, "GET", "me", 200)["student_id"] == "student-1",
                    "Wrong student binding",
                )
                api(
                    admin,
                    "PATCH",
                    "student-claims/" + student["localId"],
                    409,
                    {"approve": True, "verification_reference": "Replay"},
                )
                checks.append(
                    "student_claim_admin_approval_no_cross_user_read_no_escalation_replay"
                )
                invitation = api(
                    admin,
                    "POST",
                    "faculty-invitations",
                    201,
                    {"faculty_id": "faculty-1", "email": teacher["email"]},
                )
                api(
                    other, "POST", "faculty-invitations/accept", 403, {"token": invitation["token"]}
                )
                api(teacher, "POST", "faculty-invitations/accept", 403, {"token": "x" * 43})
                api(
                    teacher,
                    "POST",
                    "faculty-invitations/accept",
                    200,
                    {"token": invitation["token"]},
                )
                api(
                    teacher,
                    "POST",
                    "faculty-invitations/accept",
                    403,
                    {"token": invitation["token"]},
                )
                require(
                    api(teacher, "GET", "me", 200)["faculty_id"] == "faculty-1",
                    "Wrong faculty binding",
                )
                for state in ["revoked", "expired"]:
                    invitation = api(
                        admin,
                        "POST",
                        "faculty-invitations",
                        201,
                        {"faculty_id": "faculty-1", "email": other["email"]},
                    )
                    if state == "revoked":
                        api(admin, "DELETE", "faculty-invitations/" + invitation["id"], 200)
                    else:
                        with transaction(owner) as db:
                            db.execute(
                                text(
                                    "UPDATE classsync_identity.faculty_invitations "
                                    "SET created_at=transaction_timestamp()-interval '2 hours',"
                                    "expires_at=transaction_timestamp()-interval '1 hour' "
                                    "WHERE id=CAST(:id AS uuid)"
                                ),
                                {"id": invitation["id"]},
                            )
                    api(
                        other,
                        "POST",
                        "faculty-invitations/accept",
                        403,
                        {"token": invitation["token"]},
                    )
                checks.append("faculty_scoped_email_invalid_replay_revoked_expired_invitation")
                api(
                    admin,
                    "PATCH",
                    "memberships/" + teacher["localId"] + "/revoke",
                    200,
                    {"expected_revision": 1},
                )
                api(teacher, "GET", "me", 403)
                # Refresh session and recovery using actual emulator OOB endpoints.
                firebase(
                    "sendOobCode", {"requestType": "PASSWORD_RESET", "email": student["email"]}
                )
                codes = transport.get(f"/emulator/v1/projects/{project}/oobCodes").json()[
                    "oobCodes"
                ]
                reset = next(
                    x["oobCode"]
                    for x in reversed(codes)
                    if x["email"] == student["email"] and x["requestType"] == "PASSWORD_RESET"
                )
                firebase(
                    "resetPassword",
                    {"oobCode": reset, "newPassword": "Changed-emulator-password-42!"},
                )
                recovered = firebase(
                    "signInWithPassword",
                    {
                        "email": student["email"],
                        "password": "Changed-emulator-password-42!",
                        "returnSecureToken": True,
                    },
                )
                api(recovered, "GET", "me", 200)
                api(
                    admin,
                    "PATCH",
                    "memberships/" + student["localId"] + "/revoke",
                    200,
                    {"expected_revision": 1},
                )
                api(recovered, "GET", "me", 403)
                api(other, "POST", "student-claims", 201, {"student_id": "student-1"})
                api(
                    admin,
                    "PATCH",
                    "student-claims/" + other["localId"],
                    409,
                    {"approve": True, "verification_reference": "Synthetic duplicate record check"},
                )
                require(
                    api(other, "GET", "onboarding", 200)["claim_state"] == "pending",
                    "Duplicate-record rejection did not roll back the pending claim",
                )
                checks.append("current_membership_revocation_and_actual_password_recovery")
            # RLS is tested through the least-privileged runtime, not superuser.
            with transaction(runtime) as db:
                identity_context(db, tenant_id="tenant-b", uid=other["localId"])
                require(
                    db.scalar(text("SELECT count(*) FROM classsync_identity.account_claims")) == 0,
                    "Cross-tenant claim leakage",
                )
                require(
                    db.scalar(text("SELECT count(*) FROM classsync_identity.faculty_invitations"))
                    == 0,
                    "Cross-tenant invitation leakage",
                )
            try:
                with transaction(owner) as db:
                    db.execute(
                        text(
                            "INSERT INTO classsync_identity.account_claims "
                            "(tenant_id,uid,student_id,state,decided_by) "
                            "VALUES('tenant-a','bad-reference','student-1','approved','admin')"
                        )
                    )
            except IntegrityError:
                pass
            else:
                raise RuntimeError("Approved claim allowed NULL verification reference")
            checks.append("runtime_cross_tenant_rls_and_database_null_reference_denial")
            browser_result = None
            if browser:
                browser_admin = verify(signup("browser-admin"))
                with transaction(owner) as db:
                    identity_context(db, tenant_id="tenant-a", uid=browser_admin["localId"])
                    audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
                    db.execute(
                        text(
                            "INSERT INTO classsync_identity.memberships VALUES "
                            "('tenant-a',:uid,'admin',NULL,NULL,ARRAY['administrator'],'active',1)"
                        ),
                        {"uid": browser_admin["localId"]},
                    )
                    # The API's duplicate-record fixture deliberately remains pending;
                    # decide it explicitly before the independent browser review flow.
                    db.execute(
                        text(
                            "UPDATE classsync_identity.account_claims "
                            "SET state='rejected',decided_by='synthetic-provisioner' "
                            "WHERE tenant_id='tenant-a' AND uid=:uid"
                        ),
                        {"uid": other["localId"]},
                    )
                    db.execute(
                        text(
                            "INSERT INTO classsync_identity.people VALUES "
                            "('tenant-a','browser-student'),('tenant-a','browser-faculty')"
                        )
                    )
                    db.execute(
                        text(
                            "INSERT INTO classsync_identity.students VALUES "
                            "('tenant-a','browser-student','browser-student')"
                        )
                    )
                    db.execute(
                        text(
                            "INSERT INTO classsync_identity.faculty VALUES "
                            "('tenant-a','browser-faculty','browser-faculty')"
                        )
                    )
                if scanner or connected:
                    from scripts.registration_connected_qualification import run
                    from scripts.registration_published_fixture import prepare

                    fixture = prepare(
                        connection,
                        owner,
                        runtime,
                        uid=browser_admin["localId"],
                        project=project,
                        requests=connected,
                    )
                    browser_result = run(
                        connection,
                        patch,
                        verifier,
                        postman_only=postman_only,
                        project=project,
                        endpoint=endpoint,
                        admin_email=browser_admin["email"],
                        fixture=fixture,
                        owner=owner,
                        runtime=runtime,
                        connected=connected,
                    )
                else:
                    browser_result = qualify_browser(
                        gateway.app, project, endpoint, browser_admin["email"]
                    )
        return {
            "checks": checks,
            "cloud_qualified": False,
            "browser_qualified": browser_result is not None,
            "browser": browser_result,
        }
    finally:
        runtime.dispose()
        owner.dispose()


def qualify_browser(application, project, endpoint, admin_email):
    root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"])
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(application, log_level="error", lifespan="on"))
    worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 15
        while not server.started and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        require(server.started, "Owned account Gateway did not start")
        config = root / "onboarding-browser-config.json"
        config.write_text(
            json.dumps(
                {
                    "root": str(root),
                    "project": project,
                    "authEndpoint": endpoint,
                    "gateway": f"http://127.0.0.1:{listener.getsockname()[1]}",
                    "adminEmail": admin_email,
                    "imageRoot": "C:/Users/lenovo/.codex/visualizations/2026/11/04/"
                    "01a1a6f1-45f4-76b0-8871-98908c92db98",
                }
            )
        )
        result = subprocess.run(
            [shutil.which("node"), "scripts/onboarding_browser.cjs", str(config)],
            check=False,
            timeout=180,
        )
        require(result.returncode == 0, "Actual account browser journey failed")
        return json.loads((root / "onboarding-browser-result.json").read_text())
    finally:
        server.should_exit = True
        worker.join(timeout=15)
        listener.close()
        require(not worker.is_alive(), "Owned account Gateway did not stop")


def main(*, browser=False, scanner=False, connected=False, postman_only=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(
        not args.output.exists() and args.output.parent.is_dir(), "New evidence output required"
    )
    root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"]).resolve()
    require(
        root.parent == Path(tempfile.gettempdir()).resolve()
        and re.fullmatch(r"classsync-auth-run-[a-f0-9]{32}", root.name),
        "Owned Auth root required",
    )
    marker = json.loads((root / "owned-auth.json").read_text())
    require(
        os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == marker["endpoint"], "Auth target mismatch"
    )
    evidence = qualify(
        args.bin,
        lambda connection: exercise(
            connection,
            marker["project"],
            marker["endpoint"],
            browser=browser,
            scanner=scanner,
            connected=connected,
            postman_only=postman_only,
        ),
    )
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(
        "Synthetic onboarding Auth/Gateway/PostgreSQL qualification passed; "
        "owned PostgreSQL stopped"
    )


if __name__ == "__main__":
    main()
