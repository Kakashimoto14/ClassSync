"""Owned Auth/Firestore emulators and disposable PostgreSQL publication access."""

import os
import re
import shutil
import socket
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_contracts.request_authorization import AuthorizationAdapters
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import PostgresMembershipLookup, identity_context
from fastapi.testclient import TestClient
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import URL
from starlette.responses import JSONResponse

from scripts.firestore_shadow_import import compare_snapshot, plan_snapshot, resume_batch
from scripts.postgres_driver_qualification import require
from scripts.postgres_onboarding_qualification import main
from scripts.registration_connected_qualification import server
from services.gateway.app.firestore_access import (
    AccessConflict,
    FirestoreAccess,
    QualificationMembershipBridge,
)
from services.gateway.app.firestore_faculty_onboarding import FirestoreOnboarding


@contextmanager
def owned_firestore(patch, project):
    require(re.fullmatch(r"demo-classsync-[a-f0-9]{12}", project), "Owned demo project required")
    require(not os.environ.get("FIRESTORE_EMULATOR_HOST"), "Ambient Firestore endpoint denied")
    jar = Path(os.environ["CLASSSYNC_FIRESTORE_EMULATOR_JAR"]).resolve(strict=True)
    require(jar.is_file() and jar.name == "cloud-firestore-emulator-v1.22.0.jar",
            "Explicit pinned Firestore emulator jar required")
    java = shutil.which("java")
    require(java is not None, "Java is required for the local Firestore emulator")
    rules = Path(__file__).resolve().parents[1] / "infrastructure/firebase/firestore.rules"
    root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"])
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    endpoint = f"127.0.0.1:{port}"
    patch.setenv("FIRESTORE_EMULATOR_HOST", endpoint)
    env = {key: os.environ[key] for key in ("SystemRoot", "TEMP", "TMP") if key in os.environ}
    with (root / "firestore-emulator.log").open("xb") as log:
        proc = subprocess.Popen(
            [java, "-Xmx384m", "-XX:ActiveProcessorCount=2", "-jar", str(jar),
             "--host", "127.0.0.1", "--port", str(port), "--project_id", project,
             "--single_project_mode", "true", "--single_project_mode_error", "true",
             "--rules", str(rules)],
            cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        client = None

        def stop():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and proc.poll() is None:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Owned Firestore emulator did not start")
            client = firestore.Client(project=project, credentials=AnonymousCredentials())
            yield client, endpoint, stop
        finally:
            if client is not None:
                client.close()
            stop()


def shadow_rehearsal(access, projection, members):
    shadow = FirestoreAccess(access.client, project=access.project, tenant=access.tenant,
                             shadow=True)

    def approved(member):
        return projection.lookup_current(tenant_id=member.tenant_id, uid=member.uid) == member

    try:
        QualificationMembershipBridge(shadow, projection)
    except ValueError:
        pass
    else:
        raise RuntimeError("Shadow membership could authorize a request")
    plan = plan_snapshot(shadow, members, approved_binding=approved)
    require(not shadow.root.collection("memberships").limit(1).get(retry=None, timeout=5),
            "Shadow dry run performed a write")
    for rows in ([members[0], members[0]], [members[0].model_copy(update={"uid": uuid4().hex})]):
        try:
            plan_snapshot(shadow, rows, approved_binding=approved)
        except AccessConflict:
            pass
        else:
            raise RuntimeError("Duplicate or orphaned source mapping was accepted")
    # Simulate losing the worker after a record commit but before its checkpoint.
    shadow.seed_snapshot(plan.members[0])
    with ThreadPoolExecutor(max_workers=2) as pool:
        replays = list(pool.map(lambda _: resume_batch(shadow, plan, batch_size=1), range(2)))
    require(sorted(replays) in ([1, 1], [1, 2]), "Concurrent shadow replay skipped a batch")
    require(resume_batch(shadow, plan, batch_size=1) == len(members), "Shadow resume failed")
    require(resume_batch(shadow, plan, batch_size=1) == len(members), "Completed replay changed")
    return compare_snapshot(shadow, plan)


def qualify_faculty(client, access, *, admin_headers, student_headers, teacher_headers,
                    teacher_email, faculty, secondary_admin, actor_uid):
    invitations = "/api/v1/auth/faculty-invitations"
    records = client.get("/api/v1/auth/faculty-records", headers=admin_headers)
    require(records.status_code == 200 and records.json()["data"] == [{"id": faculty}],
            "Administrator did not get the canonical faculty record")
    body = {"faculty_id": faculty, "email": teacher_email, "expires_in_hours": 1}
    require(client.post(invitations, headers=student_headers, json=body).status_code == 403,
            "Student could issue a faculty invitation")

    def issue(issuer_headers=admin_headers):
        response = client.post(invitations, headers=issuer_headers, json=body)
        require(response.status_code == 201, "Firestore invitation issuance failed")
        return response.json()["data"]

    def accept(invitation, headers):
        return client.post(invitations + "/accept", headers=headers,
                           json={"token": invitation["token"]}).status_code

    old_issuer = issue({"Authorization": "Bearer " + secondary_admin["idToken"]})
    access.revoke(uid=secondary_admin["localId"], expected_revision=1,
                  operation_id="issuer-revoke", actor_uid=actor_uid)
    require(accept(old_issuer, teacher_headers) == 403, "Revoked issuer's invite accepted")
    replaced, revoked = issue(), issue()
    outcome = accept(replaced, teacher_headers)
    require(outcome == 403, f"Replaced invite expected 403, got {outcome}")
    require(client.delete(invitations + "/" + revoked["id"], headers=admin_headers)
            .status_code == 200 and accept(revoked, teacher_headers) == 403,
            "Revoked invite accepted")
    expired = issue()
    # Controlled expiry fixture; never use real email or wait on a long-lived token.
    access.root.collection("facultyInvitations").document(expired["id"]).update(
        {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}, retry=None, timeout=5
    )
    require(accept(expired, teacher_headers) == 403, "Expired invite accepted")
    valid = issue()
    require(accept(valid, student_headers) == 403, "Wrong verified email accepted an invite")
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(lambda _: accept(valid, teacher_headers), range(2)))
    require(outcomes == [200, 403], f"Concurrent invitation acceptance: {outcomes}")
    require(accept(valid, teacher_headers) == 403, "Used invite could replay")
    return {"concurrent_accept": outcomes, "wrong_email_expired_replaced_revoked_denied": True,
            "revoked_issuer_denied": True}


def run(
    connection, patch, verifier, *, project, student, teacher, administrator, secondary_admin,
    fixture, owner, runtime,
):
    from services.gateway.app import main as gateway
    from services.scheduling.app import authorization
    from services.scheduling.app import main as scheduling

    uid = student["localId"]
    actor_uid = administrator["localId"]
    with transaction(owner) as db:
        db.execute(text(
            "INSERT INTO classsync_identity.people VALUES ('tenant-a','browser-issuer')"
        ))
        for subject, person, student_id, faculty_id, role in (
            (uid, "browser-student", fixture["student"], None, "student"),
            (teacher["localId"], "browser-faculty", None, fixture["faculty"], "teacher"),
            (secondary_admin["localId"], "browser-issuer", None, None, "administrator"),
        ):
            identity_context(db, tenant_id="tenant-a", uid=subject)
            audit_actor(db, VerifiedPrincipal(uid=actor_uid))
            db.execute(text("""
                INSERT INTO classsync_identity.memberships
                VALUES ('tenant-a',:uid,:person,:student,:faculty,ARRAY[:role]::text[],'active',1)
            """), {"uid": subject, "person": person, "student": student_id,
                   "faculty": faculty_id, "role": role})
        for schema in ("classsync_identity", "classsync_academic", "classsync_scheduling"):
            db.execute(text(
                f"REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} "
                f"FROM {connection.runtime}"
            ))
        db.execute(text(
            "REVOKE UPDATE(revision) ON classsync_academic.period_metadata "
            f"FROM {connection.runtime}"
        ))

    def no_sqlite(*_args, **_kwargs):
        raise RuntimeError("Firestore access qualification cannot open SQLite")

    patch.setattr(sqlite3, "connect", no_sqlite)
    projection = PostgresMembershipLookup(runtime, firebase_project_id=project)
    member = projection.lookup_current(tenant_id="tenant-a", uid=uid)
    require(member is not None and member.state == MembershipState.ACTIVE, "SQL fixture missing")
    url = URL.create("postgresql+psycopg", username=connection.runtime, host="127.0.0.1",
                     port=connection.port, database="postgres")
    patch.setattr(scheduling, "settings", scheduling.Settings(
        _env_file=None, classsync_env="test", firebase_project_id=project,
        institutional_tenant_id="tenant-a", enable_test_identity_adapters=True,
        scheduling_database_url=SecretStr(url.render_as_string()),
        scheduling_database_transport="loopback-sspi-test", database_pool_size=2,
        enable_scheduling_sandbox=False,
    ))
    patch.setattr(authorization, "FirebaseTokenVerifier", lambda _: verifier)
    calendar = "/api/v1/timetables/calendar/" + fixture["period"]
    query = {"start": "2026-10-01", "end": "2026-10-31"}
    headers = {"Authorization": "Bearer " + student["idToken"], "X-ClassSync-Role": "student"}
    admin_headers = {"Authorization": "Bearer " + administrator["idToken"]}
    teacher_headers = {"Authorization": "Bearer " + teacher["idToken"],
                       "X-ClassSync-Role": "teacher"}
    status_path = "/api/v1/auth/onboarding"
    claim_path = "/api/v1/auth/student-claims"
    decision_path = claim_path + "/" + uid
    allowed = {
        ("GET", calendar), ("GET", status_path), ("GET", claim_path),
        ("POST", claim_path), ("PATCH", decision_path),
        ("GET", "/api/v1/auth/me"), ("GET", "/api/v1/auth/faculty-records"),
        ("POST", "/api/v1/auth/faculty-invitations"),
        ("POST", "/api/v1/auth/faculty-invitations/accept"),
    }
    active = False

    async def guarded(scope, receive, send):
        if scope["type"] == "http" and (
            not active or scope["method"] != "GET" or scope["path"] != calendar
            or scheduling.app.state.authorization_adapters.memberships is not bridge
        ):
            await JSONResponse({"detail": "Qualification read boundary"}, 403)(scope, receive, send)
            return
        await scheduling.app(scope, receive, send)

    async def guarded_gateway(scope, receive, send):
        if scope["type"] == "http" and (scope["method"], scope["path"]) not in allowed and not (
            scope["method"] == "DELETE" and re.fullmatch(
                r"/api/v1/auth/faculty-invitations/[a-f0-9-]{36}", scope["path"]
            )
        ):
            await JSONResponse({"detail": "Qualification access boundary"}, 403)(
                scope, receive, send
            )
            return
        await gateway.app(scope, receive, send)

    with owned_firestore(patch, project) as (client, endpoint, stop_firestore):
        access = FirestoreAccess(client, project=project, tenant="tenant-a")
        bridge = QualificationMembershipBridge(access, projection)

        def resolve_binding(subject, student_record):
            if subject == uid and student_record == fixture["student"]:
                return projection.lookup_current(tenant_id="tenant-a", uid=subject)
            return None

        def resolve_faculty(subject, faculty_id):
            if subject == teacher["localId"] and faculty_id == fixture["faculty"]:
                return projection.lookup_current(tenant_id="tenant-a", uid=subject)
            return None

        patch.setattr(gateway.app.state, "authorization_adapters",
                      AuthorizationAdapters(verifier, bridge))
        patch.setattr(gateway.app.state, "onboarding_repository",
                      FirestoreOnboarding(access, bridge, resolve_binding,
                                          list_faculty=lambda: [fixture["faculty"]],
                                          resolve_faculty=resolve_faculty))
        with server(guarded) as schedule_url, patch.context() as schedule_patch:
            # Lifespan built the real PostgreSQL provider; admit requests only after
            # the local-only Firestore intersection is installed.
            schedule_patch.setattr(scheduling.app.state, "authorization_adapters",
                                   AuthorizationAdapters(verifier, bridge))
            patch.setattr(gateway.settings, "scheduling_service_url", schedule_url)
            active = True
            with (
                TestClient(guarded_gateway) as gateway_client,
                httpx.Client(timeout=10, trust_env=False) as direct,
            ):
                checks = {}

                def pair(name, status, identity_headers=headers):
                    via = gateway_client.get(calendar, params=query, headers=identity_headers)
                    downstream = direct.get(schedule_url + calendar, params=query,
                                            headers=identity_headers)
                    checks[name] = [via.status_code, downstream.status_code]
                    require(checks[name] == [status, status], f"{name}: {checks[name]}")
                    return via, downstream

                pair("sql_only_denied", 403)
                pair("teacher_sql_only_denied", 403, teacher_headers)
                response = gateway_client.get(status_path, headers=headers)
                require(response.status_code == 200 and response.json()["data"]["status"]
                        == "unlinked", "Firestore onboarding must ignore the SQL-only grant")
                claim = {"student_id": fixture["student"]}
                require(gateway_client.post(claim_path, headers=headers, json=claim).status_code
                        == 201, "Verified Student claim did not reach Firestore")
                pair("pending_claim_denied", 403)
                decision = {"approve": True, "verification_reference": "Disposable roster review"}
                for denied_headers in (headers, admin_headers):
                    require(gateway_client.patch(decision_path, headers=denied_headers,
                                                 json=decision).status_code == 403,
                            "Claim review accepted without a current Firestore Admin grant")
                admin = projection.lookup_current(tenant_id="tenant-a", uid=actor_uid)
                require(admin is not None, "Fixture Administrator projection missing")
                shadow_receipt = shadow_rehearsal(access, projection, (member, admin))
                pair("shadow_cannot_grant", 403)
                access.seed_snapshot(admin)
                secondary = projection.lookup_current(
                    tenant_id="tenant-a", uid=secondary_admin["localId"]
                )
                require(secondary is not None, "Secondary issuer projection missing")
                access.seed_snapshot(secondary)
                listed = gateway_client.get(claim_path, headers=admin_headers)
                require(listed.status_code == 200 and listed.json()["data"] == [
                    {"uid": uid, **claim, "state": "pending"},
                ], "Administrator could not retrieve the bounded pending claim")
                for _ in range(2):
                    approved = gateway_client.patch(decision_path, headers=admin_headers,
                                                    json=decision)
                    require(approved.status_code == 200 and approved.json()["data"]["status"]
                            == "approved", "Firestore claim approval or exact replay failed")
                recreated = firestore.Client(project=project, credentials=AnonymousCredentials())
                try:
                    readback = FirestoreAccess(recreated, project=project, tenant="tenant-a")
                    require(readback.lookup_current(tenant_id="tenant-a", uid=uid) == member,
                            "Firestore activation missing after client recreation")
                finally:
                    recreated.close()
                access.seed_snapshot(member)
                try:
                    access.seed_snapshot(member.model_copy(update={"uid": uuid4().hex}))
                except AccessConflict:
                    pass
                else:
                    raise RuntimeError("Duplicate student binding accepted")
                require(access.lookup_current(tenant_id="tenant-b", uid=uid) is None,
                        "Cross-tenant Firestore access")
                via, downstream = pair("published_calendar", 200)
                payload = downstream.json()
                require(payload["occurrences"] and via.json()["data"] == payload,
                        "Official PostgreSQL calendar projections disagree")
                teacher_receipt = qualify_faculty(
                    gateway_client, access, admin_headers=admin_headers, student_headers=headers,
                    teacher_headers=teacher_headers, teacher_email=teacher["email"],
                    faculty=fixture["faculty"], secondary_admin=secondary_admin,
                    actor_uid=actor_uid,
                )
                via, downstream = pair("teacher_published_calendar", 200, teacher_headers)
                require(
                    downstream.json()["occurrences"] and via.json()["data"] == downstream.json(),
                    "Teacher publication projections disagree",
                )
                for identity_headers, role in ((headers, "student"), (teacher_headers, "teacher"),
                                               (admin_headers, "administrator")):
                    identity = gateway_client.get("/api/v1/auth/me", headers=identity_headers)
                    require(identity.status_code == 200 and identity.json()["data"]["role"] == role,
                            "Verified workspace resolution failed")
                require(direct.post(schedule_url + "/api/v1/timetables/publish",
                                    headers=headers).status_code == 403,
                        "Read-only bridge accepted a write")
                ref = access._member(uid)
                document = (
                    f"http://{endpoint}/v1/projects/{project}/databases/(default)/documents/{ref.path}"
                )
                rule_statuses = [
                    direct.get(document).status_code,
                    direct.get(document, headers=headers).status_code,
                    direct.patch(document, headers=headers, json={"fields": {
                        "schema_version": {"integerValue": "99"},
                    }}).status_code,
                ]
                require(
                    rule_statuses == [403, 403, 403], f"Direct Firestore rules: {rule_statuses}"
                )
                # Deliberate fixture corruption to prove stale/inconsistent state
                # cannot admit either path. Restoration is not a supported API.
                ref.update({"membership.revision": 2}, retry=None, timeout=5)
                pair("contradictory_projection", 503)
                ref.update({"membership.revision": 1}, retry=None, timeout=5)
                pair("matching_projection_recovery", 200)
                try:
                    access.revoke(uid=uid, expected_revision=2, operation_id="stale",
                                  actor_uid=actor_uid)
                except AccessConflict:
                    pass
                else:
                    raise RuntimeError("Stale grant mutation accepted")
                operation = dict(uid=uid, expected_revision=1, operation_id="revoke",
                                 actor_uid=actor_uid)
                require(access.revoke(**operation) == access.revoke(**operation) == 2,
                        "Revocation or exact replay failed")
                require(projection.lookup_current(tenant_id="tenant-a", uid=uid) == member,
                        "Firestore write changed the SQL projection")
                pair("revoked_with_active_sql", 403)
                stop_firestore()
                pair("owned_firestore_stopped", 503)
                pair("active_teacher_firestore_stopped", 503, teacher_headers)
                return {"checks": checks, "direct_rules_statuses": rule_statuses,
                        "occurrences": len(payload["occurrences"]), "revocation_revision": 2,
                        "claim_approval_and_replay": True, "grant_readback_new_client": True,
                        "shadow_rehearsal": shadow_receipt,
                        "teacher_invitation": teacher_receipt,
                        "disposable_only": True, "hosted_qualified": False}


if __name__ == "__main__":
    main(scanner=True, firestore_probe=run)
