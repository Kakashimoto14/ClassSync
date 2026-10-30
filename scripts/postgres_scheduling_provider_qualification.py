"""Owned Auth Emulator/current PostgreSQL Scheduling HTTP qualification, no originals."""

import argparse
import json
import os
import re
import tempfile
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_contracts.scheduling import Window
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor, change_membership_state
from classync_persistence.memberships import identity_context
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import URL

from scripts.postgres_disposable import checked_root, qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.app.draft_rules import digest, encode, now
from services.scheduling.tests.test_calendar import configuration
from services.scheduling.tests.test_engine import tiny
from services.testing.emulator_firebase import emulator_firebase


def publication_cases():
    dates = "start=2026-10-01&end=2026-10-31"
    times = ("room_id=room-a&start=2026-10-01T08:00:00%2B08:00"
             "&end=2026-10-01T09:00:00%2B08:00")
    command = PublicationCommand(
        draft_id="synthetic-draft", expected_version=0, expected_academic_revision=1,
        idempotency_key="synthetic-publication-key", calendar=configuration().calendar,
    ).model_dump(mode="json")
    restriction = RoomRestriction(
        id="synthetic-restriction", room_id="room-a", dataset="institutional",
        starts_at="2026-10-01T08:00:00+08:00", ends_at="2026-10-01T09:00:00+08:00",
        kind="reservation", reason="Disposable qualification only", expected_revision=0,
    ).model_dump(mode="json")
    return [
        ("GET", "/periods", None), ("GET", "/history/synthetic-period", None),
        ("GET", "/calendar/synthetic-period?" + dates, None),
        ("GET", "/events/synthetic-period?" + dates, None),
        ("GET", "/availability?" + times, None),
        ("POST", "/review", command), ("POST", "/publish", command),
        ("PUT", "/restrictions/synthetic-restriction", restriction),
    ]


def exercise(connection, project, endpoint):
    foundation = identity_exercise(connection)
    from services.scheduling.app import authorization as providers
    from services.scheduling.app import main as scheduling

    root = checked_root(connection.root, Path(tempfile.gettempdir()))
    owner = engine_for(connection, bootstrap=True)
    url = URL.create("postgresql+psycopg", username=connection.runtime,
                     host="127.0.0.1", port=connection.port, database="postgres")
    statuses = []
    engines = []
    try:
        with transaction(owner) as db:
            require(db.scalar(text("SELECT version_num FROM public.alembic_version"))
                    == "0006_scheduling_drafts", "Scheduling provider migration scope drift")
            require(Path(db.scalar(text("SHOW data_directory"))).resolve() == root / "data",
                    "Scheduling provider target differs from owned marked cluster")
        with pytest.MonkeyPatch.context() as patch, emulator_firebase(
            patch, project=project, endpoint=endpoint,
        ) as sdk:
            verifier, _ = sdk
            identities = []
            with httpx.Client(base_url=f"http://{endpoint}", trust_env=False, timeout=5) as auth:
                for _ in range(5):
                    response = auth.post(
                        "/identitytoolkit.googleapis.com/v1/accounts:signUp",
                        params={"key": "synthetic-emulator-key"}, json={"returnSecureToken": True},
                    )
                    require(response.status_code == 200, "Owned Auth anonymous signup failed")
                    identities.append(response.json())
            admin, other, student, teacher, unbound = identities
            uid = admin["localId"]
            settings = scheduling.Settings(
                _env_file=None, classsync_env="test", firebase_project_id=project,
                institutional_tenant_id="tenant-a", enable_test_identity_adapters=True,
                scheduling_database_url=SecretStr(url.render_as_string(hide_password=False)),
                scheduling_database_transport="loopback-sspi-test",
                scheduling_database_path=str(root / "never-open.sqlite3"),
                firebase_service_account_json=None, firebase_client_email=None,
                firebase_private_key=None,
            )
            patch.setattr(scheduling, "settings", settings)
            # Actual owned SDK verification; membership adapters are constructed by source lifespan.
            patch.setattr(providers, "FirebaseTokenVerifier", lambda _: verifier)

            def no_sqlite():
                raise RuntimeError("Configured Scheduling HTTP attempted SQLite fallback")

            patch.setattr(scheduling, "repository", no_sqlite)
            with transaction(owner) as db:
                db.execute(text("GRANT USAGE ON SCHEMA classsync_scheduling "
                                f"TO {connection.runtime}"))
                db.execute(text("GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA classsync_scheduling "
                                f"TO {connection.runtime}"))
                db.execute(text("UPDATE classsync_identity.tenants "
                                "SET firebase_project_id=:project "
                                "WHERE id='tenant-a'"), {"project": project})

            def request(client, method, path, expected, body=None, identity=admin, extra=None,
                        prefix="/api/v1/scheduling", code=None):
                response = client.request(method, prefix + path, json=body, headers={
                    "Authorization": "Bearer " + identity["idToken"], **(extra or {}),
                })
                statuses.append({"method": method, "path": prefix + path,
                                 "status": response.status_code})
                require(response.status_code == expected,
                        f"Scheduling HTTP {method} {path} expected{expected} "
                        f"got{response.status_code}: {response.text[:300]}")
                if code:
                    require(response.json()["error"]["code"] == code,
                            "Scheduling HTTP returned wrong typed failure")
                require("text/event-stream" not in response.headers.get("content-type", ""),
                        "Unqualified publication stream was opened")
                return response.json()

            def no_sessions(engine):
                require(engine.pool.checkedout() == engine.pool.checkedin() == 0,
                        "Scheduling disposed pool retained physical connections")
                require(not hasattr(scheduling.app.state, "scheduling_engine")
                        and not hasattr(scheduling.app.state, "authorization_adapters"),
                        "Scheduling shutdown retained owned application state")
                with transaction(owner) as db:
                    require(db.scalar(text("SELECT count(*) FROM pg_stat_activity "
                                           "WHERE usename=:role "
                                           "AND application_name='classsync-scheduling'"),
                                      {"role": connection.runtime}) == 0,
                            "Scheduling shutdown left runtime server sessions")

            def run_count():
                with transaction(owner) as db:
                    return db.scalar(text("SELECT count(*) FROM classsync_scheduling.solver_runs"))

            def change_state(expected, state):
                with transaction(owner) as db:
                    identity_context(db, tenant_id="tenant-a", uid=uid)
                    return change_membership_state(
                        db, tenant_id="tenant-a", uid=uid, expected_revision=expected, state=state,
                        actor=VerifiedPrincipal(uid="synthetic-operator"),
                    )

            with TestClient(scheduling.app) as client:
                first_engine = scheduling.app.state.scheduling_engine
                engines.append(first_engine)
                require(scheduling.app.state.authorization_adapters.verifier is verifier,
                        "Actual SDK verifier was not bound by source-owned lifespan")
                require(scheduling.app.state.authorization_adapters.memberships.engine
                        is first_engine, "Identity and draft operations use different owned pools")
                with first_engine.connect() as db:
                    first_backend = db.scalar(text("SELECT pg_backend_pid()"))
                    require(db.scalar(text("SHOW statement_timeout")) == "5s"
                            and db.scalar(text("SHOW lock_timeout")) == "1500ms",
                            "Scheduling SQL deadlines differ from source limits")
                    observed_role = db.execute(text("""
                        SELECT current_user,rolsuper,rolcreatedb,rolcreaterole,rolreplication,
                            rolbypassrls FROM pg_roles WHERE rolname=current_user
                    """)).one()
                    require(tuple(observed_role) == (
                        connection.runtime, False, False, False, False, False,
                    ), "Scheduling provider runtime exceeds least privilege")
                require(first_engine.pool.size() == 5 and first_engine.pool.timeout() == 3,
                        "Scheduling pool capacity/wait differs from source bounds")
                request(client, "GET", "/drafts", 403, identity=unbound, code="membership_denied")
                require(client.get("/api/v1/scheduling/drafts").status_code == 401,
                        "Missing token reached Scheduling storage")
                request(client, "GET", "/drafts", 401,
                        extra={"Authorization": "Bearer malformed"})
                with transaction(owner) as db:
                    for identity, roles, person, student_id, faculty_id in (
                        (admin, ["administrator"], "person-other", None, None),
                        (other, ["administrator"], "person-other", None, None),
                        (student, ["student"], "person-a", "student-a", None),
                        (teacher, ["teacher"], "person-a", None, "faculty-a"),
                    ):
                        identity_context(db, tenant_id="tenant-a", uid=identity["localId"])
                        audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                        db.execute(text("""
                            INSERT INTO classsync_identity.memberships VALUES
                              ('tenant-a',:uid,:person,:student,:faculty,
                               CAST(:roles AS text[]),'active',1)
                        """), {"uid": identity["localId"], "person": person,
                               "student": student_id, "faculty": faculty_id, "roles": roles})
                for identity in (student, teacher):
                    request(client, "GET", "/drafts", 403, identity=identity,
                            extra={"X-ClassSync-Role": "administrator", "X-Tenant-ID": "tenant-a"})
                inputs = tiny()  # Existing explicit synthetic fixture; no institutional assertions.
                generated = request(client, "POST", "/generate", 200,
                                    inputs.model_dump(mode="json"))
                require(generated["solver_status"] in {"optimal", "feasible"}
                        and generated["validation"]["valid"]
                        and generated["hard_conflict_count"] == 0,
                        "Actual solver did not return an independently validated candidate")
                body = {"run_id": generated["run_id"], "input_hash": generated["input_hash"],
                        "title": "Synthetic Scheduling provider qualification",
                        "idempotency_key": "scheduling-provider-save-key"}
                request(client, "POST", "/drafts", 409, body | {"input_hash": "0" * 64},
                        code="input_version_conflict")
                request(client, "POST", "/drafts", 422,
                        body | {"generation_result": generated})
                request(client, "POST", "/drafts", 404,
                        body | {"run_id": "absent", "idempotency_key": "missing-run-save-key"},
                        code="run_not_found")
                draft = request(client, "POST", "/drafts", 201, body)
                draft_id = draft["id"]
                require(draft["generation_result"] == generated
                        and draft["input_snapshot"] == inputs.model_dump(mode="json")
                        and draft["creator"] == uid,
                        "HTTP save changed the server-held input/result or verified creator")
                require(request(client, "POST", "/drafts", 200, body) == draft,
                        "Identical HTTP replay changed the saved draft")
                for changes in ({"idempotency_key": "changed-save-key"}, {"title": "Changed title"},
                                {"input_hash": "0" * 64}, {"run_id": "changed-run-id"}):
                    request(client, "POST", "/drafts", 409, body | changes,
                            code="idempotency_conflict")
                require(request(client, "GET", "/drafts/" + draft_id, 200) == draft,
                        "Conflicting HTTP replay changed the original")
                listing = request(client, "GET", "/drafts?tenant_id=tenant-b&owner=forged", 200,
                                  extra={"X-Tenant-ID": "tenant-b", "X-Owner-ID": other["localId"]})
                require([entry["id"] for entry in listing["drafts"]] == [draft_id],
                        "Client tenant/owner selection escaped server binding")
                request(client, "GET", "/drafts/" + draft_id, 404, identity=other,
                        code="draft_not_found")
                require(request(client, "GET", "/drafts", 200, identity=other)["drafts"] == [],
                        "Second active Administrator read the first owner's drafts")
                request(client, "POST", "/drafts", 404, body, identity=other, code="run_not_found")
                for identity in (student, teacher):
                    request(client, "GET", "/drafts/" + draft_id, 403, identity=identity)
                    request(client, "POST", "/drafts", 403, body, identity=identity)
                # Corruption fixture: direct INSERT is confined to the new owned database.
                # A checksum-consistent forged candidate must still fail independent validation.
                forged_id = str(uuid4())
                forged = json.loads(encode({"inputs": inputs.model_dump(mode="json"),
                                           "result": generated}))
                forged["result"].update(run_id=forged_id, assignments=[])
                payload = encode(forged)
                with transaction(owner) as db:
                    db.execute(text("""
                        INSERT INTO classsync_scheduling.solver_runs
                          (tenant_id,owner_uid,id,created_at,payload,checksum)
                        VALUES ('tenant-a',:uid,:id,:created,:payload,:checksum)
                    """), {"uid": uid, "id": forged_id, "created": now(),
                           "payload": payload, "checksum": digest(payload)})
                request(client, "POST", "/drafts", 422,
                        body | {"run_id": forged_id, "idempotency_key": "forged-server-run-key"},
                        code="invalid_generated_run")
                with transaction(owner) as db:
                    require(db.scalar(text(
                        "SELECT count(*) FROM classsync_scheduling.drafts")) == 1,
                            "Rejected forged candidate produced a saved draft")
                real_guard = scheduling.require_administrator

                def revoke_after_guard(*arguments):
                    claims = real_guard(*arguments)
                    change_state(1, MembershipState.REVOKED)
                    return claims

                with pytest.MonkeyPatch.context() as race:
                    race.setattr(scheduling, "require_administrator", revoke_after_guard)
                    request(client, "GET", "/drafts", 403, code="membership_denied")
                change_state(2, MembershipState.ACTIVE)
                require(request(client, "GET", "/drafts/" + draft_id, 200) == draft,
                        "Current revocation/reactivation changed saved state")
                with transaction(owner) as db:
                    db.execute(text("REVOKE SELECT ON classsync_scheduling.drafts "
                                    f"FROM {connection.runtime}"))
                try:
                    request(client, "GET", "/drafts/" + draft_id, 503,
                            code="persistence_unavailable")
                finally:
                    with transaction(owner) as db:
                        db.execute(text("GRANT SELECT ON classsync_scheduling.drafts "
                                        f"TO {connection.runtime}"))
                require(request(client, "GET", "/drafts/" + draft_id, 200) == draft,
                        "Scheduling permission outage recovery changed saved state")
                runs_before = run_count()
                with transaction(owner) as db:
                    db.execute(text("REVOKE INSERT ON classsync_scheduling.solver_runs "
                                    f"FROM {connection.runtime}"))
                try:
                    request(client, "POST", "/generate", 503, inputs.model_dump(mode="json"),
                            code="persistence_unavailable")
                finally:
                    with transaction(owner) as db:
                        db.execute(text("GRANT INSERT ON classsync_scheduling.solver_runs "
                                        f"TO {connection.runtime}"))
                require(run_count() == runs_before,
                        "Failed candidate persistence left an unconfirmed server run")
                recovered = request(client, "POST", "/generate", 200,
                                    inputs.model_dump(mode="json"), identity=other)
                require(recovered["solver_status"] in {"optimal", "feasible"},
                        "Generation INSERT grant did not recover")
                other_body = body | {"run_id": recovered["run_id"],
                                     "input_hash": recovered["input_hash"],
                                     "title": "Synthetic second owner draft"}
                other_draft = request(client, "POST", "/drafts", 201, other_body, identity=other)
                require(other_draft["id"] != draft_id
                        and other_draft["creator"] == other["localId"],
                        "Second active Administrator did not receive a separate owned draft")
                request(client, "GET", "/drafts/" + other_draft["id"], 404,
                        code="draft_not_found")
                require(request(client, "GET", "/drafts", 200, identity=other)["drafts"][0]["id"]
                        == other_draft["id"], "Second Administrator lost own draft access")
                recovered_runs = run_count()
                require(recovered_runs == runs_before + 1,
                        "INSERT recovery did not commit exactly one new run")
                impossible = tiny(count=2)
                impossible.operating_windows = [Window(day=0, start=480, end=660)]
                infeasible = request(client, "POST", "/generate", 200,
                                     impossible.model_dump(mode="json"))
                require(infeasible["solver_status"] == "infeasible"
                        and infeasible["assignments"] == [] and infeasible["validation"] is None,
                        "Impossible fixture was not reported as infeasible")
                require(run_count() == recovered_runs, "Infeasible run was persisted as success")
                with ExitStack() as occupied:
                    for _ in range(5):
                        occupied.enter_context(first_engine.connect())
                    require(first_engine.pool.checkedout() == 5,
                            "Five pool slots not actually held")
                    request(client, "GET", "/drafts/" + draft_id, 503)
                require(request(client, "GET", "/drafts/" + draft_id, 200) == draft,
                        "Scheduling exhausted pool did not recover")
                for method, path, command in publication_cases():
                    request(client, method, path, 503, command, prefix="/api/v1/timetables")
                for identity in (student, teacher):
                    request(client, "GET", "/periods", 503, identity=identity,
                            prefix="/api/v1/timetables")
                with first_engine.connect() as db:
                    require(not db.scalar(text("SELECT current_setting('classsync.uid',true)"))
                            and not db.scalar(text(
                                "SELECT current_setting('classsync.tenant_id',true)")),
                            "Scheduling pool retained previous caller identity")
            no_sessions(first_engine)
            for field, invalid in (("institutional_tenant_id", "tenant-b"),
                                   ("firebase_project_id", "wrong-project")):
                with pytest.MonkeyPatch.context() as binding:
                    binding.setattr(scheduling, "settings",
                                    settings.model_copy(update={field: invalid}))
                    with TestClient(scheduling.app) as mismatch:
                        engines.append(scheduling.app.state.scheduling_engine)
                        request(mismatch, "GET", "/drafts/" + draft_id, 403,
                                code="membership_denied")
                    no_sessions(engines[-1])
            # Real owned PostgreSQL postmaster restart; never an arbitrary database target.
            require(connection.run_tool is not None, "Owned tool runner required for restart")
            with transaction(owner) as db:
                postmaster_before = db.scalar(text("SELECT pg_postmaster_start_time()"))
            owner.dispose()
            checked_root(root, Path(tempfile.gettempdir()))
            connection.run_tool("pg_ctl.exe", "-D", root / "data", "-l", root / "server.log",
                                "-w", "-t", "20", "restart", "-m", "fast")
            with transaction(owner) as db:
                postmaster_after = db.scalar(text("SELECT pg_postmaster_start_time()"))
                require(postmaster_after > postmaster_before,
                        "Owned PostgreSQL server did not actually restart")
            with TestClient(scheduling.app) as restarted:
                restarted_engine = scheduling.app.state.scheduling_engine
                engines.append(restarted_engine)
                require(restarted_engine is not first_engine,
                        "Provider did not create a fresh pool")
                with restarted_engine.connect() as db:
                    restarted_backend = db.scalar(text("SELECT pg_backend_pid()"))
                    require(restarted_backend != first_backend,
                            "Provider restart reused the old physical backend")
                require(request(restarted, "GET", "/drafts/" + draft_id, 200) == draft,
                        "PostgreSQL/provider restart lost exact committed draft")
                require(request(restarted, "POST", "/drafts", 200, body) == draft,
                        "Restart lost saved idempotency binding")
                require(request(restarted, "GET", "/drafts/" + other_draft["id"], 200,
                                identity=other) == other_draft,
                        "Restart lost second owner's exact saved draft")
            no_sessions(restarted_engine)
            try:
                with TestClient(scheduling.app):
                    exceptional_engine = scheduling.app.state.scheduling_engine
                    engines.append(exceptional_engine)
                    raise RuntimeError("synthetic exceptional caller")
            except RuntimeError as error:
                require(str(error) == "synthetic exceptional caller", "Unexpected lifecycle error")
            no_sessions(exceptional_engine)
            require(not (root / "never-open.sqlite3").exists(), "SQLite fallback file created")
            return {
                "foundation": foundation, "actual_auth_sdk_current_pg_asgi_http": True,
                "generation_save_replay_list_get": True,
                "changed_key_title_run_hash_rejected": True,
                "client_result_and_forged_stored_candidate_rejected": True,
                "two_active_administrator_owner_isolation": True,
                "separate_student_teacher_no_membership_and_bad_tokens_denied": True,
                "client_tenant_owner_headers_ignored": True,
                "guard_to_storage_current_revocation": True,
                "actual_select_and_insert_permission_outage_recovery": True,
                "failed_generation_persistence_no_false_success": True,
                "actual_five_connection_exhaustion_recovery": True,
                "actual_infeasible_not_persisted": True,
                "unknown_solver_status": "not forced; portable control-flow coverage only",
                "all_institutional_publication_routes_unavailable": True,
                "server_tenant_project_denied": True,
                "actual_postmaster_and_provider_restart_durable": True,
                "physical_restart": {"postmaster_before": postmaster_before.isoformat(),
                                     "postmaster_after": postmaster_after.isoformat(),
                                     "runtime_backend_before": first_backend,
                                     "runtime_backend_after": restarted_backend},
                "normal_exceptional_shutdown_zero_runtime_sessions": True,
                "no_sqlite_fallback": True, "http_statuses": statuses,
                "academic_service_forwarding": "not composed by this bounded qualifier",
                "tcp_browser_workflows": "not performed; HTTP uses FastAPI ASGI TestClient",
                "production_acceptance": False,
            }
    finally:
        for engine in engines:
            engine.dispose()
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
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    project, endpoint = marker.get("project", ""), marker.get("endpoint", "")
    endpoint_match = re.fullmatch(r"127\.0\.0\.1:([0-9]{4,5})", endpoint)
    require(marker.get("authOnly") is True and re.fullmatch(r"demo-[a-z0-9-]{1,40}", project)
            and endpoint_match and 1024 < int(endpoint_match[1]) < 65536
            and os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == endpoint,
            "Owned demo Auth endpoint mismatch")
    evidence = qualify(args.bin, lambda connection: exercise(connection, project, endpoint))
    write_new_evidence(args.output, evidence)
    print("Scheduling actual Auth/HTTP/PG provider qualification passed; owned PG stopped")


if __name__ == "__main__":
    main()
