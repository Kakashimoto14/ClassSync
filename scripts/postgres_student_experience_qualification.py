"""Actual local Auth SDK/current-PG publication HTTP composition; no cloud or originals."""

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import uvicorn
from classync_contracts.academic import CalendarWrite, RecordWrite
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
    saved_draft,
)
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.tests.test_calendar import configuration
from services.testing.emulator_firebase import emulator_firebase


def exercise(connection, project, endpoint):
    from services.scheduling.app import authorization, main

    owner, runtime = engine_for(connection, bootstrap=True), engine_for(connection)
    try:
        _base, _other, migrator = prepare_source(connection, owner, runtime)
        authorize_grants(connection, owner, migrator)
        with (
            pytest.MonkeyPatch.context() as patch,
            emulator_firebase(
                patch,
                project=project,
                endpoint=endpoint,
            ) as (verifier, _sdk),
        ):
            with httpx.Client(base_url=f"http://{endpoint}", trust_env=False, timeout=5) as auth:
                identities = []
                for index in range(5):
                    response = auth.post(
                        "/identitytoolkit.googleapis.com/v1/accounts:signUp",
                        params={"key": "synthetic-emulator-key"},
                        json={
                            "returnSecureToken": True,
                            "email": f"student-{index}@synthetic.invalid",
                            "password": "Owned-local-fixture-42!",
                        },
                    )
                    require(response.status_code == 200, "Owned Auth signup failed")
                    identities.append(response.json())
            admin, student, teacher, unassigned, unbound = identities

            def link(identity, template):
                with transaction(owner) as db:
                    identity_context(db, tenant_id="tenant-a", uid=identity["localId"])
                    audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                    db.execute(
                        text(
                            "INSERT INTO classsync_identity.memberships "
                            "SELECT tenant_id,:uid,person_id,student_id,faculty_id,"
                            "roles,'active',1 "
                            "FROM classsync_identity.memberships WHERE tenant_id='tenant-a' "
                            "AND uid=:template"
                        ),
                        {"uid": identity["localId"], "template": template},
                    )

            link(admin, "uid-admin")
            academic = academic_store(runtime, uid=admin["localId"])
            snapshot = complete(FixtureCalls(academic))
            snapshot = academic.save_calendar(
                snapshot.period.id,
                CalendarWrite(
                    expected_revision=snapshot.period.revision, calendar=configuration().calendar
                ),
            )
            names = {
                "subject-a": "Advanced Database Systems",
                "subject-b": "Application Development",
                "teacher-a": "Maria Clara Santos",
                "teacher-b": "Carlo Mendoza",
                "room-a": "LAB-201",
                "room-b": "LAB-202",
            }
            for entry in list(snapshot.records):
                record = entry.record
                if record.id in names:
                    readable = record.model_copy(update={"name": names[record.id]})
                    snapshot = academic.save(
                        snapshot.period.id,
                        record.kind,
                        record.id,
                        RecordWrite(expected_revision=entry.revision, record=readable),
                    )
            snapshot = enrolled_projection_fixture(academic, snapshot)
            draft = saved_draft(runtime, snapshot, uid=admin["localId"])
            teacher_id = draft.generation_result.assignments[0].teacher_id
            projection_membership_fixture(owner, teacher_id)
            for identity, template in (
                (student, "uid-student"),
                (teacher, "uid-teacher"),
                (unassigned, "uid-student-unassigned"),
            ):
                link(identity, template)
            require(not draft.input_snapshot.synthetic, "Institutional HTTP fixture required")
            command = publish_command(draft, snapshot)
            with transaction(owner) as db:
                db.execute(
                    text(
                        "UPDATE classsync_identity.tenants "
                        "SET firebase_project_id=:project "
                        "WHERE id='tenant-a'"
                    ),
                    {"project": project},
                )
            url = URL.create(
                "postgresql+psycopg",
                username=connection.runtime,
                host="127.0.0.1",
                port=connection.port,
                database="postgres",
            )
            settings = main.Settings(
                _env_file=None,
                classsync_env="test",
                firebase_project_id=project,
                institutional_tenant_id="tenant-a",
                enable_test_identity_adapters=True,
                scheduling_database_url=SecretStr(url.render_as_string(hide_password=False)),
                scheduling_database_transport="loopback-sspi-test",
                scheduling_database_path=str(connection.root / "never-open.sqlite3"),
                firebase_service_account_json=None,
                firebase_client_email=None,
                firebase_private_key=None,
            )
            patch.setattr(main, "settings", settings)
            patch.setattr(authorization, "FirebaseTokenVerifier", lambda _settings: verifier)
            patch.setattr(
                main,
                "repository",
                lambda: (_ for _ in ()).throw(
                    AssertionError("PostgreSQL HTTP attempted SQLite fallback")
                ),
            )

            body = command.model_dump(mode="json")
            with TestClient(main.app) as client:
                headers = {"Authorization": "Bearer " + admin["idToken"]}
                for action in ("review", "publish"):
                    result = client.post("/api/v1/timetables/" + action, headers=headers, json=body)
                    require(result.status_code == 200, "Fixture publication failed: " + result.text)
            from services.gateway.app import authorization as gateway_auth
            from services.gateway.app import main as gateway

            # Setup-only engines must not compete with the two real service pools
            # in the guarded ten-connection cluster (three slots are reserved).
            fixture_pools = {
                "owner_idle": owner.pool.checkedin(),
                "runtime_idle": runtime.pool.checkedin(),
            }
            runtime.dispose()
            owner.dispose()
            require(
                runtime.pool.checkedin() == owner.pool.checkedin() == 0,
                "Setup connections survived handoff to HTTP services",
            )
            servers, workers, listeners = [], [], []
            timeline = []
            phase = {"value": "healthy"}
            control = None
            try:
                nonce = uuid4().hex

                class Control(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_POST(self):
                        if self.path != "/fixture" or self.headers.get("X-Owned-Fixture") != nonce:
                            self.send_error(403)
                            return
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length < 256:
                            self.send_error(400)
                            return
                        action = json.loads(self.rfile.read(length)).get("action")
                        if action in ("outage", "recover"):
                            phase["value"] = action
                            if action == "outage":
                                servers[0].should_exit = True
                                workers[0].join(15)
                                require(not workers[0].is_alive(), "Scheduling outage did not stop")
                            else:
                                gateway.settings.scheduling_service_url = start(
                                    main.app, "scheduling"
                                )
                                phase["value"] = "healthy"
                            self.send_response(200)
                            self.end_headers()
                            return
                        if action not in ("revoke", "activate", "unassign", "assign"):
                            self.send_error(400)
                            return
                        with transaction(owner) as db:
                            identity_context(db, tenant_id="tenant-a", uid=student["localId"])
                            audit_actor(db, VerifiedPrincipal(uid="synthetic-operator"))
                            if action in ("revoke", "activate"):
                                db.execute(
                                    text(
                                        "UPDATE classsync_identity.memberships SET "
                                        "state=:state,revision=revision+1 "
                                        "WHERE tenant_id='tenant-a' "
                                        "AND uid=:uid"
                                    ),
                                    {
                                        "state": "revoked" if action == "revoke" else "active",
                                        "uid": student["localId"],
                                    },
                                )
                            else:
                                template = (
                                    "uid-student-unassigned"
                                    if action == "unassign"
                                    else "uid-student"
                                )
                                db.execute(
                                    text(
                                        "UPDATE classsync_identity.memberships SET "
                                        "student_id=(SELECT student_id FROM "
                                        "classsync_identity.memberships "
                                        "WHERE tenant_id='tenant-a' AND uid=:template),"
                                        "revision=revision+1 "
                                        "WHERE tenant_id='tenant-a' AND uid=:uid"
                                    ),
                                    {"template": template, "uid": student["localId"]},
                                )
                        self.send_response(200)
                        self.end_headers()
                        owner.dispose()

                control = ThreadingHTTPServer(("127.0.0.1", 0), Control)
                control_worker = threading.Thread(target=control.serve_forever, daemon=True)
                control_worker.start()

                def start(app, name):
                    async def observe(scope, receive, send):
                        if scope["type"] != "http":
                            return await app(scope, receive, send)
                        begin = time.time()
                        status, response_headers = 0, {}

                        async def observed_send(message):
                            nonlocal status, response_headers
                            if message["type"] == "http.response.start":
                                status = message["status"]
                                response_headers = dict(message.get("headers", []))
                            await send(message)

                        await app(scope, receive, observed_send)
                        engine = getattr(app.state, "scheduling_engine", None)
                        headers = dict(scope.get("headers", []))
                        timeline.append(
                            {
                                "service": name,
                                "at": begin,
                                "method": scope["method"],
                                "path": scope["path"],
                                "query": scope["query_string"].decode(),
                                "status": status,
                                "phase": phase["value"],
                                "request_id": (
                                    headers.get(b"x-request-id")
                                    or response_headers.get(b"x-request-id", b"")
                                ).decode(),
                                "provider": hasattr(app.state, "authorization_adapters"),
                                "pool_checked_out": engine.pool.checkedout() if engine else None,
                                "pool_idle": engine.pool.checkedin() if engine else None,
                                "during_cleanup": server.should_exit,
                            }
                        )
                        return None

                    listener = socket.socket()
                    listener.bind(("127.0.0.1", 0))
                    listeners.append(listener)
                    server = uvicorn.Server(uvicorn.Config(observe, log_level="error"))
                    worker = threading.Thread(
                        target=server.run, kwargs={"sockets": [listener]}, daemon=True
                    )
                    servers.append(server)
                    workers.append(worker)
                    worker.start()
                    deadline = time.monotonic() + 20
                    while not server.started and worker.is_alive() and time.monotonic() < deadline:
                        time.sleep(0.05)
                    require(server.started, "Owned TCP service startup failed")
                    return f"http://127.0.0.1:{listener.getsockname()[1]}"

                scheduling_url = start(main.app, "scheduling")
                patch.setattr(
                    gateway,
                    "settings",
                    gateway.Settings(
                        _env_file=None,
                        classsync_env="test",
                        institutional_tenant_id="tenant-a",
                        firebase_project_id=project,
                        enable_test_identity_adapters=True,
                        identity_database_url=SecretStr(url.render_as_string(hide_password=False)),
                        identity_database_transport="loopback-sspi-test",
                        scheduling_service_url=scheduling_url,
                        firebase_service_account_json=None,
                        firebase_client_email=None,
                        firebase_private_key=None,
                    ),
                )
                patch.setattr(gateway_auth, "FirebaseTokenVerifier", lambda _: verifier)
                gateway_url = start(gateway.app, "gateway")
                root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"])
                config = root / "student-browser-fixture.json"
                write_new_evidence(
                    config,
                    {
                        "root": str(root),
                        "project": project,
                        "authEndpoint": endpoint,
                        "gateway": gateway_url,
                        "email": "student-1@synthetic.invalid",
                        "password": "Owned-local-fixture-42!",
                        "control": f"http://127.0.0.1:{control.server_port}/fixture",
                        "nonce": nonce,
                    },
                )
                node = shutil.which("node")
                require(node is not None, "Node unavailable")
                result = subprocess.run(
                    [node, "scripts/student_experience_browser.cjs", str(config)], check=False
                )
                write_new_evidence(
                    root / "student-service-timeline.json",
                    {
                        "fixture_idle_before_handoff": fixture_pools,
                        "fixture_idle_after_handoff": {
                            "owner": owner.pool.checkedin(),
                            "runtime": runtime.pool.checkedin(),
                        },
                        "events": timeline,
                    },
                )
                require(result.returncode == 0, "Student browser qualification failed")
                return json.loads((root / "student-browser-result.json").read_text())
            finally:
                if control is not None:
                    control.shutdown()
                    control.server_close()
                    control_worker.join(5)
                for server in servers:
                    server.should_exit = True
                for worker in workers:
                    worker.join(15)
                    require(not worker.is_alive(), "Owned TCP service did not stop")
                for listener in listeners:
                    listener.close()
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
    require(
        root.parent == Path(tempfile.gettempdir()).resolve()
        and re.fullmatch(r"classsync-auth-run-[a-f0-9]{32}", root.name),
        "Owned Auth root required",
    )
    marker_path = root / "owned-auth.json"
    require(marker_path.is_file() and not marker_path.is_symlink(), "Owned Auth marker required")
    marker = json.loads(marker_path.read_text())
    project, endpoint = marker.get("project", ""), marker.get("endpoint", "")
    require(
        marker.get("authOnly") is True
        and re.fullmatch(r"demo-[a-z0-9-]{1,40}", project)
        and re.fullmatch(r"127\.0\.0\.1:[0-9]{4,5}", endpoint)
        and os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == endpoint,
        "Owned demo Auth endpoint mismatch",
    )
    write_new_evidence(
        args.output, qualify(args.bin, lambda connection: exercise(connection, project, endpoint))
    )
    print("Publication Auth/PG HTTP qualification passed; owned cluster stopped")


if __name__ == "__main__":
    main()
