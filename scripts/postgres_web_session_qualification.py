"""Real frontend browser -> owned demo Auth -> Gateway -> disposable PostgreSQL."""

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
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

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
from services.testing.emulator_firebase import emulator_firebase


def write_new_evidence(path, evidence):
    """Never replace evidence created while a qualification was running."""
    with path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")


def exercise(connection, root, marker):
    foundation = identity_exercise(connection)
    from services.gateway.app import authorization as providers
    from services.gateway.app import main as gateway

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
        with pytest.MonkeyPatch.context() as patch, emulator_firebase(
            patch, project=project, endpoint=endpoint,
        ) as sdk, ExitStack() as teardown:
            teardown.callback(stop_services)
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
            ))
            patch.setattr(providers, "FirebaseTokenVerifier", lambda _: verifier)

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
                                    audit_actor(session, actor)
                                    session.execute(text("""
                                        INSERT INTO classsync_identity.memberships VALUES
                                        ('tenant-a', :uid, 'person-a', 'student-a', 'faculty-a',
                                         CAST(:roles AS text[]), 'active', 1)
                                    """), {"uid": uid, "roles": roles})
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
            return {"foundation": foundation, "browser": browser, "production_acceptance": False}
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
