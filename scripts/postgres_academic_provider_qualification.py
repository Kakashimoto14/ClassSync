"""Source-owned Academic HTTP/Auth Emulator/current PostgreSQL provider qualification."""

import argparse
import json
import os
import re
import tempfile
from contextlib import ExitStack
from pathlib import Path

import httpx
import pytest
from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor, change_membership_state
from classync_persistence.memberships import identity_context
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import URL

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.tests.test_calendar import configuration
from services.testing.emulator_firebase import emulator_firebase


def exercise(connection, project, endpoint):
    foundation = identity_exercise(connection)
    from services.academic.app import authorization as providers
    from services.academic.app import main as academic

    owner = engine_for(connection, bootstrap=True)
    url = URL.create(
        "postgresql+psycopg",
        username=connection.runtime,
        host="127.0.0.1",
        port=connection.port,
        database="postgres",
    )
    try:
        with (
            pytest.MonkeyPatch.context() as patch,
            emulator_firebase(
                patch,
                project=project,
                endpoint=endpoint,
            ) as sdk,
        ):
            verifier, _ = sdk
            identities = []
            with httpx.Client(base_url=f"http://{endpoint}", trust_env=False, timeout=5) as auth:
                for _ in range(3):
                    response = auth.post(
                        "/identitytoolkit.googleapis.com/v1/accounts:signUp",
                        params={"key": "synthetic-emulator-key"},
                        json={"returnSecureToken": True},
                    )
                    require(response.status_code == 200, "Owned Auth anonymous signup failed")
                    identities.append(response.json())
            admin, other, learner = identities
            uid = admin["localId"]
            settings = academic.Settings(
                _env_file=None,
                classsync_env="test",
                firebase_project_id=project,
                institutional_tenant_id="tenant-a",
                enable_test_identity_adapters=True,
                academic_database_url=SecretStr(url.render_as_string(hide_password=False)),
                academic_database_transport="loopback-sspi-test",
                academic_database_path=str(connection.root / "never-open.sqlite3"),
                firebase_service_account_json=None,
                firebase_client_email=None,
                firebase_private_key=None,
            )
            patch.setattr(academic, "settings", settings)
            patch.setattr(providers, "FirebaseTokenVerifier", lambda _: verifier)

            def no_sqlite():
                raise RuntimeError("Configured HTTP attempted SQLite fallback")

            patch.setattr(academic, "repository", no_sqlite)
            with transaction(owner) as db:
                db.execute(
                    text(f"GRANT USAGE ON SCHEMA classsync_academic TO {connection.runtime}")
                )
                db.execute(
                    text(
                        "GRANT SELECT,INSERT,UPDATE(revision) ON "
                        f"classsync_academic.period_metadata TO {connection.runtime}"
                    )
                )
                for table in ("records", "record_references", "calendars"):
                    db.execute(
                        text(
                            f"GRANT SELECT,INSERT,UPDATE ON classsync_academic.{table} "
                            f"TO {connection.runtime}"
                        )
                    )
                db.execute(
                    text(
                        "GRANT DELETE ON classsync_academic.record_references "
                        f"TO {connection.runtime}"
                    )
                )
                db.execute(
                    text(
                        "UPDATE classsync_identity.tenants SET firebase_project_id=:project "
                        "WHERE id='tenant-a'"
                    ),
                    {"project": project},
                )
            with TestClient(academic.app) as client:
                first_engine = academic.app.state.academic_engine
                with first_engine.connect() as observed:
                    require(
                        observed.scalar(text("SHOW statement_timeout")) == "5s"
                        and observed.scalar(text("SHOW lock_timeout")) == "1500ms",
                        "Configured SQL deadlines differ from source bounds",
                    )

                def request(method, path, expected, body=None, identity=admin, extra=None):
                    response = client.request(
                        method,
                        "/api/v1/academic" + path,
                        json=body,
                        headers={
                            "Authorization": "Bearer " + identity["idToken"],
                            **(extra or {}),
                        },
                    )
                    require(
                        response.status_code == expected,
                        f"Academic HTTP expected{expected} got{response.status_code}",
                    )
                    return response.json()

                request("GET", "/periods", 403)  # Actual SDK identity alone grants no records.
                require(
                    client.get("/api/v1/academic/periods").status_code == 401,
                    "Missing bearer token reached private academic storage",
                )
                request("GET", "/periods", 401, extra={"Authorization": "Bearer malformed"})
                with transaction(owner) as db:
                    for identity, roles, person, student, faculty in (
                        (admin, ["administrator"], "person-other", None, None),
                        (other, ["administrator"], "person-other", None, None),
                        (learner, ["student", "teacher"], "person-a", "student-a", "faculty-a"),
                    ):
                        identity_context(db, tenant_id="tenant-a", uid=identity["localId"])
                        audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                        db.execute(
                            text("""
                            INSERT INTO classsync_identity.memberships VALUES
                              ('tenant-a',:uid,:person,:student,:faculty,
                               CAST(:roles AS text[]),'active',1)
                        """),
                            {
                                "uid": identity["localId"],
                                "person": person,
                                "student": student,
                                "faculty": faculty,
                                "roles": roles,
                            },
                        )
                created = request(
                    "POST",
                    "/periods",
                    201,
                    {"title": "Synthetic HTTP period", "include_cdm_catalog": False},
                )
                pid = created["period"]["id"]
                require(
                    len(created["records"]) == 1 and created["period"]["revision"] == 2,
                    "HTTP create did not commit default constraints",
                )
                require(request("GET", "/periods/" + pid, 200) == created, "HTTP snapshot mismatch")
                body = {
                    "expected_revision": 0,
                    "record": {
                        "kind": "programs",
                        "id": "synthetic-p",
                        "acronym": "SYN",
                        "name": "Synthetic program",
                        "institute": "Synthetic",
                    },
                }
                updated = request("PUT", f"/periods/{pid}/records/programs/synthetic-p", 200, body)
                request("PUT", f"/periods/{pid}/records/programs/synthetic-p", 409, body)
                calendar_body = {
                    "expected_revision": updated["period"]["revision"],
                    "calendar": configuration().calendar.model_dump(mode="json"),
                }
                dated = request("PUT", f"/periods/{pid}/calendar", 200, calendar_body)
                request("PUT", f"/periods/{pid}/calendar", 409, calendar_body)
                request("GET", f"/periods/{pid}", 404, identity=other)
                request(
                    "PUT", f"/periods/{pid}/records/programs/synthetic-p", 404, body, identity=other
                )
                request(
                    "GET",
                    "/periods",
                    403,
                    identity=learner,
                    extra={"X-ClassSync-Role": "administrator", "X-Tenant-ID": "tenant-a"},
                )
                request("POST", "/periods", 403, {"title": "Forbidden"}, identity=learner)
                listing = request(
                    "GET",
                    "/periods?tenant_id=tenant-b&owner=forged",
                    200,
                    extra={"X-Tenant-ID": "tenant-b", "X-Owner-ID": other["localId"]},
                )
                require(
                    [period["id"] for period in listing["periods"]] == [pid],
                    "Spoofed owner/tenant escaped server binding",
                )

                def state(expected, value):
                    with transaction(owner) as db:
                        identity_context(db, tenant_id="tenant-a", uid=uid)
                        change_membership_state(
                            db,
                            tenant_id="tenant-a",
                            uid=uid,
                            expected_revision=expected,
                            state=value,
                            actor=VerifiedPrincipal(uid="synthetic-operator"),
                        )

                real_guard = academic.require_administrator

                def revoke_after_guard(*arguments):
                    claims = real_guard(*arguments)
                    state(1, MembershipState.REVOKED)
                    return claims

                with pytest.MonkeyPatch.context() as race:
                    race.setattr(academic, "require_administrator", revoke_after_guard)
                    result = request("GET", "/periods", 403)
                    require(
                        result["error"]["code"] == "membership_denied",
                        "Repository revocation race escaped typed HTTP denial",
                    )
                state(2, MembershipState.ACTIVE)
                require(
                    request("GET", "/periods/" + pid, 200) == dated,
                    "Revocation/recovery changed stored academic data",
                )
                with transaction(owner) as db:
                    db.execute(
                        text(
                            f"REVOKE SELECT ON classsync_academic.records FROM {connection.runtime}"
                        )
                    )
                try:
                    result = request("GET", "/periods/" + pid, 503)
                    require(
                        result["error"]["code"] == "academic_storage_unavailable",
                        "Actual DB outage did not remain unavailable",
                    )
                finally:
                    with transaction(owner) as db:
                        db.execute(
                            text(
                                "GRANT SELECT ON classsync_academic.records "
                                f"TO {connection.runtime}"
                            )
                        )
                require(
                    request("GET", "/periods/" + pid, 200) == dated, "HTTP outage recovery failed"
                )
                with ExitStack() as occupied:
                    for _ in range(5):
                        occupied.enter_context(first_engine.connect())
                    require(
                        first_engine.pool.checkedout() == 5,
                        "Five physical pool slots were not held",
                    )
                    request("GET", "/periods/" + pid, 503)
                require(
                    request("GET", "/periods/" + pid, 200) == dated, "Pool capacity recovery failed"
                )
            require(
                not hasattr(academic.app.state, "academic_engine")
                and not hasattr(academic.app.state, "authorization_adapters")
                and first_engine.pool.checkedout() == first_engine.pool.checkedin() == 0,
                "Academic normal shutdown retained provider/pool state",
            )
            for field, invalid in (
                ("institutional_tenant_id", "tenant-b"),
                ("firebase_project_id", "wrong-project"),
            ):
                with pytest.MonkeyPatch.context() as binding:
                    binding.setattr(
                        academic, "settings", settings.model_copy(update={field: invalid})
                    )
                    with TestClient(academic.app) as mismatched:
                        response = mismatched.get(
                            "/api/v1/academic/periods/" + pid,
                            headers={"Authorization": "Bearer " + admin["idToken"]},
                        )
                        require(
                            response.status_code == 403
                            and response.json()["error"]["code"] == "membership_denied",
                            "Wrong server tenant/project returned academic data",
                        )
            with TestClient(academic.app) as restarted:
                response = restarted.get(
                    "/api/v1/academic/periods/" + pid,
                    headers={"Authorization": "Bearer " + admin["idToken"]},
                )
                require(
                    response.status_code == 200 and response.json() == dated,
                    "HTTP restart lost committed academic state",
                )
            try:
                with TestClient(academic.app):
                    raise RuntimeError("synthetic exceptional caller")
            except RuntimeError as error:
                require(str(error) == "synthetic exceptional caller", "Unexpected caller error")
            with transaction(owner) as db:
                require(
                    db.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE usename=:role "
                            "AND application_name='classsync-academic'"
                        ),
                        {"role": connection.runtime},
                    )
                    == 0,
                    "Owned SQL sessions remained",
                )
            require(
                not (connection.root / "never-open.sqlite3").exists(),
                "SQLite fallback file created",
            )
            return {
                "foundation": foundation,
                "actual_auth_sdk_owned_current_pg_http": True,
                "create_list_snapshot_record_calendar": True,
                "owner_and_role_isolation": True,
                "stale_revision_conflicts": True,
                "guard_to_repository_revocation_403": True,
                "actual_database_outage_recovery": True,
                "actual_pool_capacity_failure_recovery": True,
                "wrong_server_tenant_project_denied": True,
                "normal_exceptional_restart_cleanup": True,
                "no_sqlite_fallback_or_startup_migration": True,
                "production_acceptance": False,
            }
    finally:
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and args.output.parent.is_dir(), "New output required")
    root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"]).resolve()
    require(
        root.parent == Path(tempfile.gettempdir()).resolve()
        and re.fullmatch(r"classsync-auth-run-[a-f0-9]{32}", root.name),
        "Owned Auth root required",
    )
    marker = json.loads((root / "owned-auth.json").read_text(encoding="utf-8"))
    require(
        marker["authOnly"] and os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == marker["endpoint"],
        "Owned Auth endpoint mismatch",
    )
    evidence = qualify(
        args.bin, lambda connection: exercise(connection, marker["project"], marker["endpoint"])
    )
    write_new_evidence(args.output, evidence)
    print("Academic service actual Auth/HTTP/PG provider qualification passed; owned PG stopped")


if __name__ == "__main__":
    main()
