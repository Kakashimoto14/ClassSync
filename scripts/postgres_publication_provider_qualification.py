"""Actual local Auth SDK/current-PG publication HTTP composition; no cloud or originals."""

import argparse
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path

import httpx
import pytest
from classync_contracts.academic import CalendarWrite
from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import URL

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_publication_repository_qualification import (
    FixtureCalls,
    academic_store,
    authorize_grants,
    complete,
    enrolled_projection_fixture,
    prepare_source,
    projection_membership_fixture,
    publish_command,
    repository,
    saved_draft,
)
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.tests.test_calendar import configuration
from services.testing.emulator_firebase import emulator_firebase


def exercise(connection, project, endpoint):
    from services.scheduling.app import authorization, main

    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    statuses = []
    try:
        _base, _other, migrator = prepare_source(connection, owner, runtime)
        authorize_grants(connection, owner, migrator)
        with pytest.MonkeyPatch.context() as patch, emulator_firebase(
            patch, project=project, endpoint=endpoint,
        ) as (verifier, _sdk):
            with httpx.Client(base_url=f"http://{endpoint}", trust_env=False, timeout=5) as auth:
                identities = []
                for _ in range(5):
                    response = auth.post("/identitytoolkit.googleapis.com/v1/accounts:signUp",
                        params={"key": "synthetic-emulator-key"}, json={"returnSecureToken": True})
                    require(response.status_code == 200, "Owned Auth signup failed")
                    identities.append(response.json())
            admin, student, teacher, unassigned, unbound = identities

            def link(identity, template):
                with transaction(owner) as db:
                    identity_context(db, tenant_id="tenant-a", uid=identity["localId"])
                    audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                    db.execute(text("INSERT INTO classsync_identity.memberships "
                        "SELECT tenant_id,:uid,person_id,student_id,faculty_id,roles,'active',1 "
                        "FROM classsync_identity.memberships WHERE tenant_id='tenant-a' "
                        "AND uid=:template"), {"uid": identity["localId"], "template": template})

            link(admin, "uid-admin")
            academic = academic_store(runtime, uid=admin["localId"])
            snapshot = complete(FixtureCalls(academic))
            snapshot = academic.save_calendar(snapshot.period.id, CalendarWrite(
                expected_revision=snapshot.period.revision, calendar=configuration().calendar))
            snapshot = enrolled_projection_fixture(academic, snapshot)
            draft = saved_draft(runtime, snapshot, uid=admin["localId"])
            teacher_id = draft.generation_result.assignments[0].teacher_id
            projection_membership_fixture(owner, teacher_id)
            for identity, template in ((student, "uid-student"), (teacher, "uid-teacher"),
                                       (unassigned, "uid-student-unassigned")):
                link(identity, template)
            require(not draft.input_snapshot.synthetic, "Institutional HTTP fixture required")
            command = publish_command(draft, snapshot)
            with transaction(owner) as db:
                db.execute(text("UPDATE classsync_identity.tenants "
                                "SET firebase_project_id=:project "
                                "WHERE id='tenant-a'"), {"project": project})
            url = URL.create("postgresql+psycopg", username=connection.runtime, host="127.0.0.1",
                             port=connection.port, database="postgres")
            settings = main.Settings(_env_file=None, classsync_env="test",
                firebase_project_id=project, institutional_tenant_id="tenant-a",
                enable_test_identity_adapters=True,
                scheduling_database_url=SecretStr(url.render_as_string(hide_password=False)),
                scheduling_database_transport="loopback-sspi-test",
                scheduling_database_path=str(connection.root / "never-open.sqlite3"),
                firebase_service_account_json=None, firebase_client_email=None,
                firebase_private_key=None)
            patch.setattr(main, "settings", settings)
            patch.setattr(authorization, "FirebaseTokenVerifier", lambda _settings: verifier)
            patch.setattr(main, "repository", lambda: (_ for _ in ()).throw(
                AssertionError("PostgreSQL HTTP attempted SQLite fallback")))

            def request(client, method, path, identity, status=200, body=None, role=None):
                headers = {"Authorization": "Bearer " + identity["idToken"]}
                if role:
                    headers["X-ClassSync-Role"] = role
                response = client.request(method, "/api/v1/timetables" + path,
                                          headers=headers, json=body)
                statuses.append({"method": method, "path": path, "status": response.status_code})
                require(response.status_code == status,
                        f"Publication HTTP {method} {path}: {response.status_code} {response.text}")
                return response.json()

            period = snapshot.period.id
            calendar = f"/calendar/{period}?start=2026-10-01&end=2026-10-31"
            with TestClient(main.app) as client:
                pool = main.app.state.scheduling_engine
                require(pool.pool.size() == 5 and pool.pool._max_overflow == 0,
                        "Publication provider pool differs from owned bounded configuration")
                body = command.model_dump(mode="json")
                request(client, "POST", "/review", admin, body=body)
                receipt = request(client, "POST", "/publish", admin, body=body)
                require(request(client, "POST", "/publish", admin, body=body) == receipt,
                        "HTTP publication exact replay differs")
                for identity, role, field, record in (
                        (admin, "administrator", "uid", admin["localId"]),
                        (student, "student", "student_id", "student-a"),
                        (teacher, "teacher", "faculty_id", teacher_id)):
                    actual = request(client, "GET", calendar, identity, role=role)
                    expected_repo = repository(runtime, uid=identity["localId"], project=project)
                    expected = expected_repo.calendar(
                        "tenant-a", "institutional", period, date(2026, 10, 1), date(2026, 10, 31),
                        {"role": role, "uid": identity["localId"], field: record})
                    require(actual["occurrences"], "Authorized HTTP calendar empty")
                    require(expected == actual,
                            "HTTP calendar differs from authorized PG projection")
                    periods = request(client, "GET", "/periods", identity, role=role)
                    require(any(row["id"] == period for row in periods["periods"]),
                            "Authorized period absent from HTTP projection")
                request(client, "GET", f"/history/{period}", admin)
                request(client, "GET", calendar, unassigned, 403, role="student")
                request(client, "GET", calendar, unbound, 403, role="student")
                request(client, "GET", f"/history/{period}", student, 403, role="student")
                request(client, "POST", "/publish", teacher, 403, body=body, role="teacher")
                request(client, "GET", calendar, student, 403, role="administrator")
                with transaction(owner) as db:
                    identity_context(db, tenant_id="tenant-a", uid=student["localId"])
                    audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                    db.execute(text("UPDATE classsync_identity.memberships SET state='revoked', "
                        "revision=revision+1 WHERE tenant_id='tenant-a' AND uid=:uid"),
                        {"uid": student["localId"]})
                request(client, "GET", calendar, student, 403, role="student")
                require(not (connection.root / "never-open.sqlite3").exists(),
                        "HTTP created SQLite fallback storage")
            require(not hasattr(main.app.state, "scheduling_engine")
                    and not hasattr(main.app.state, "authorization_adapters"),
                    "Owned provider lifecycle state leaked")
            return {"actual_auth_sdk_current_pg_http": True, "review_publish_exact_replay": True,
                "admin_student_teacher_calendars_periods": True,
                "unassigned_unbound_wrong_role_revoked_denied": True,
                "no_sqlite_fallback": True, "owned_pool_and_lifecycle_cleanup": True,
                "statuses": statuses, "browser_tcp_acceptance": False,
                "production_acceptance": False}
    finally:
        runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and args.output.parent.is_dir(), "New output required")
    root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"]).resolve()
    require(root.parent == Path(tempfile.gettempdir()).resolve()
            and re.fullmatch(r"classsync-auth-run-[a-f0-9]{32}", root.name),
            "Owned Auth root required")
    marker_path = root / "owned-auth.json"
    require(marker_path.is_file() and not marker_path.is_symlink(), "Owned Auth marker required")
    marker = json.loads(marker_path.read_text())
    project, endpoint = marker.get("project", ""), marker.get("endpoint", "")
    require(marker.get("authOnly") is True and re.fullmatch(r"demo-[a-z0-9-]{1,40}", project)
            and re.fullmatch(r"127\.0\.0\.1:[0-9]{4,5}", endpoint)
            and os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == endpoint,
            "Owned demo Auth endpoint mismatch")
    write_new_evidence(args.output, qualify(args.bin, lambda connection:
                                           exercise(connection, project, endpoint)))
    print("Publication Auth/PG HTTP qualification passed; owned cluster stopped")


if __name__ == "__main__":
    main()
