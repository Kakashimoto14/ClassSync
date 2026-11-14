"""Real frontend browser -> owned demo Auth -> Gateway -> disposable PostgreSQL."""

import argparse
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import uvicorn
from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_contracts.models import UserRole
from classync_persistence.database import transaction
from classync_persistence.membership_changes import (
    audit_actor,
    change_membership_grants,
    change_membership_state,
)
from classync_persistence.memberships import identity_context
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import URL

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from scripts.registration_connected_qualification import server as service_server
from services.testing.emulator_firebase import emulator_firebase


def write_new_evidence(path, evidence):
    """Never replace evidence created while a qualification was running."""
    with path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")


def exercise(connection, root, marker):
    foundation = identity_exercise(connection)
    from services.academic.app import authorization as academic_auth
    from services.academic.app import main as academic
    from services.gateway.app import authorization as providers
    from services.gateway.app import main as gateway
    from services.scheduling.app import authorization as scheduling_auth
    from services.scheduling.app import main as scheduling

    project, endpoint = marker["project"], marker["endpoint"]
    owner = engine_for(connection, bootstrap=True)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    gateway_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    nonce = uuid4().hex
    server = control = worker = control_worker = None
    actor = VerifiedPrincipal(uid="synthetic-browser-operator")

    def stop_services():
        if control is not None:
            control.shutdown()
            control.server_close()
        if control_worker is not None:
            control_worker.join(5)
        if server is not None:
            server.should_exit = True
        if worker is not None:
            worker.join(15)
        listener.close()
        require(worker is None or not worker.is_alive(), "Owned Gateway did not shut down")

    try:
        with transaction(owner) as session:
            session.execute(text(
                "UPDATE classsync_identity.tenants SET firebase_project_id=:project "
                "WHERE id='tenant-a'"
            ), {"project": project})
            # Dashboard reads use real providers, without granting runtime data writes.
            for namespace in ("classsync_academic", "classsync_scheduling"):
                session.execute(text(f"GRANT USAGE ON SCHEMA {namespace} TO {connection.runtime}"))
                session.execute(text(
                    f"GRANT SELECT ON ALL TABLES IN SCHEMA {namespace} TO {connection.runtime}"
                ))
            session.execute(text(
                f"GRANT SELECT ON classsync_identity.account_claims TO {connection.runtime}"
            ))
            privileges = session.execute(text("""
                SELECT has_table_privilege(:runtime, 'classsync_identity.account_claims', 'SELECT'),
                       has_table_privilege(:runtime, 'classsync_identity.account_claims', 'INSERT'),
                       has_table_privilege(:runtime, 'classsync_identity.account_claims', 'UPDATE'),
                       has_table_privilege(:runtime, 'classsync_identity.account_claims', 'DELETE')
            """), {"runtime": connection.runtime}).one()
            require(tuple(privileges) == (True, False, False, False),
                    "Session onboarding status must have SELECT-only runtime access")
            policy = session.execute(text("""
                SELECT relrowsecurity, relforcerowsecurity FROM pg_class
                WHERE oid = 'classsync_identity.account_claims'::regclass
            """)).one()
            require(all(policy), "Session onboarding status must retain ENABLE/FORCE RLS")
        with pytest.MonkeyPatch.context() as patch, emulator_firebase(
            patch, project=project, endpoint=endpoint,
        ) as sdk, ExitStack() as teardown:
            verifier, _ = sdk
            parameters = connection.parameters()
            url = URL.create("postgresql+psycopg", username=parameters["user"],
                             host=parameters["host"], port=parameters["port"],
                             database=parameters["dbname"])
            patch.setattr(gateway, "settings", gateway.Settings(
                _env_file=None, classsync_env="test", institutional_tenant_id="tenant-a",
                firebase_project_id=project, firebase_service_account_json=None,
                firebase_client_email=None, firebase_private_key=None,
                enable_test_identity_adapters=True,
                identity_database_url=SecretStr(url.render_as_string(hide_password=False)),
                identity_database_transport="loopback-sspi-test",
                database_pool_size=2,
                course_cloud_enabled=False, course_storage_bucket="", course_gemini_model="",
                gemini_api_key=None,
            ))
            patch.setattr(providers, "FirebaseTokenVerifier", lambda _: verifier)
            patch.setattr(academic_auth, "FirebaseTokenVerifier", lambda _: verifier)
            patch.setattr(scheduling_auth, "FirebaseTokenVerifier", lambda _: verifier)
            common = dict(
                _env_file=None, classsync_env="test", institutional_tenant_id="tenant-a",
                firebase_project_id=project, enable_test_identity_adapters=True,
                database_pool_size=2,
            )
            database_url = SecretStr(url.render_as_string(hide_password=False))
            patch.setattr(academic, "settings", academic.Settings(
                **common, academic_database_url=database_url,
                academic_database_transport="loopback-sspi-test",
            ))
            patch.setattr(scheduling, "settings", scheduling.Settings(
                **common, scheduling_database_url=database_url,
                scheduling_database_transport="loopback-sspi-test",
            ))

            def no_sqlite(*_args, **_kwargs):
                raise RuntimeError("SQLite fallback attempted by session qualification")

            patch.setattr(sqlite3, "connect", no_sqlite)
            academic_url = teardown.enter_context(service_server(academic.app))
            patch.setattr(scheduling.settings, "academic_service_url", academic_url)
            scheduling_url = teardown.enter_context(service_server(scheduling.app))
            patch.setattr(gateway.settings, "academic_service_url", academic_url)
            patch.setattr(gateway.settings, "scheduling_service_url", scheduling_url)
            patch.setattr(gateway, "SERVICES", {
                "academic": academic_url, "scheduling": scheduling_url,
            })
            teardown.callback(stop_services)

            class Control(BaseHTTPRequestHandler):
                """Fixture-only control socket; never mounted in the product API."""

                def log_message(self, *args):
                    pass

                def do_POST(self):
                    if self.path != "/fixture" or self.headers.get("X-Owned-Fixture") != nonce:
                        self.send_error(403)
                        return
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        require(0 < length < 1024, "Invalid fixture command")
                        command = json.loads(self.rfile.read(length))
                        action, uid = command["action"], command.get("uid")
                        if action in {"outage", "recover"}:
                            verb = "REVOKE" if action == "outage" else "GRANT"
                            direction = "FROM" if action == "outage" else "TO"
                            with transaction(owner) as session:
                                session.execute(text(
                                    f"{verb} SELECT ON classsync_identity.tenants "
                                    f"{direction} {connection.runtime}"
                                ))
                        elif action == "stop-auth":
                            print("CLASSSYNC_OWNED_AUTH_STOP", flush=True)
                            ack = root / "auth-stopped.json"
                            deadline = time.monotonic() + 10
                            while not ack.exists() and time.monotonic() < deadline:
                                time.sleep(0.05)
                            require(ack.exists(), "Owned Auth stop not acknowledged")
                        else:
                            require(isinstance(uid, str) and 0 < len(uid) <= 128,
                                    "Synthetic UID required")
                            with transaction(owner) as session:
                                identity_context(session, tenant_id="tenant-a", uid=uid)
                                revision = session.scalar(text(
                                    "SELECT revision FROM classsync_identity.memberships "
                                    "WHERE tenant_id='tenant-a' AND uid=:uid"
                                ), {"uid": uid})
                                if action in {"register", "administrator"}:
                                    require(revision is None, "Fixture UID already registered")
                                    roles = ["administrator"] if action == "administrator" else [
                                        "student", "teacher",
                                    ]
                                    # Each emulator account gets its own disposable records.
                                    # Foundation records already belong to other verified UIDs.
                                    record = "synthetic-session-" + uuid4().hex
                                    bindings = {
                                        "uid": uid, "roles": roles, "person": record + "-person",
                                        "student": record + "-student" if action == "register"
                                        else None,
                                        "faculty": record + "-faculty" if action == "register"
                                        else None,
                                    }
                                    session.execute(text("""
                                        INSERT INTO classsync_identity.people VALUES
                                        ('tenant-a', :person)
                                    """), bindings)
                                    if action == "register":
                                        session.execute(text("""
                                            INSERT INTO classsync_identity.students VALUES
                                            ('tenant-a', :student, :person)
                                        """), bindings)
                                        session.execute(text("""
                                            INSERT INTO classsync_identity.faculty VALUES
                                            ('tenant-a', :faculty, :person)
                                        """), bindings)
                                    audit_actor(session, actor)
                                    session.execute(text("""
                                        INSERT INTO classsync_identity.memberships
                                        (tenant_id, uid, person_id, student_id, faculty_id,
                                         roles, state, revision)
                                        VALUES ('tenant-a', :uid, :person, :student, :faculty,
                                         CAST(:roles AS text[]), 'active', 1)
                                    """), bindings)
                                elif action == "student-only":
                                    change_membership_grants(
                                        session, tenant_id="tenant-a", uid=uid,
                                        expected_revision=revision,
                                        roles=frozenset({UserRole.STUDENT}), actor=actor,
                                    )
                                elif action in {"revoke", "activate"}:
                                    change_membership_state(
                                        session, tenant_id="tenant-a", uid=uid,
                                        expected_revision=revision,
                                        state=MembershipState.REVOKED if action == "revoke"
                                        else MembershipState.ACTIVE, actor=actor,
                                    )
                                else:
                                    raise ValueError("Unknown fixture command")
                        body = b'{"ok":true}'
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    except Exception:
                        self.send_error(400, "Fixture command failed")

            control = ThreadingHTTPServer(("127.0.0.1", 0), Control)
            control_worker = threading.Thread(target=control.serve_forever, daemon=True)
            control_worker.start()
            server = uvicorn.Server(uvicorn.Config(gateway.app, log_level="error", lifespan="on"))
            worker = threading.Thread(
                target=server.run, kwargs={"sockets": [listener]}, daemon=True,
            )
            worker.start()
            deadline = time.monotonic() + 15
            while not server.started and worker.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
            require(server.started, "Owned Gateway startup failed")
            with httpx.Client(timeout=5, trust_env=False) as client:
                for service_url in (academic_url, scheduling_url, gateway_url):
                    require(client.get(service_url + "/health").status_code == 200,
                            "Owned session service health check failed")
                require(client.get(gateway_url + "/api/v1/auth/me").status_code == 401,
                        "Gateway must deny unauthenticated identity requests")
            config = root / "browser-fixture.json"
            write_new_evidence(config, {"root": str(root), "project": project,
                              "authEndpoint": endpoint, "gateway": gateway_url,
                              "control": f"http://127.0.0.1:{control.server_port}/fixture",
                              "nonce": nonce})
            node = shutil.which("node")
            require(node is not None, "Qualified Node runtime unavailable")
            result = subprocess.run([node, "scripts/web_session_browser.cjs", str(config)],
                                    check=False)
            require(result.returncode == 0, "Actual browser session qualification failed")
            browser = json.loads((root / "browser-result.json").read_text(encoding="utf-8"))
            return {"foundation": foundation, "browser": browser,
                    "onboarding_read_only_privileges": True, "production_acceptance": False}
    finally:
        try:
            stop_services()
        finally:
            owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and args.output.parent.is_dir(), "New output required")
    root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"]).resolve()
    require(root.parent == Path(tempfile.gettempdir()).resolve()
            and re.fullmatch(r"classsync-auth-run-[a-f0-9]{32}", root.name), "Owned root required")
    marker = json.loads((root / "owned-auth.json").read_text(encoding="utf-8"))
    require(os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == marker["endpoint"],
            "Owned endpoint mismatch")
    evidence = qualify(args.bin, lambda connection: exercise(connection, root, marker))
    write_new_evidence(args.output, evidence)
    print("Actual browser/Auth/Gateway/PostgreSQL qualification passed; owned servers stopped")


if __name__ == "__main__":
    main()
