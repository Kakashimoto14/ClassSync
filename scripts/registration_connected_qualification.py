"""Actual owned Gateway/Scheduling providers for a synthetic scanner browser flow."""

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

import httpx
import uvicorn
from pydantic import SecretStr
from sqlalchemy.engine import URL

from scripts.postgres_driver_qualification import require
from scripts.registration_local_qualification import fixture_images
from services.gateway.tests.registration_fixtures import pdf_bytes


@contextmanager
def server(application):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    service = uvicorn.Server(uvicorn.Config(application, log_level="error", lifespan="on"))
    worker = threading.Thread(target=service.run, kwargs={"sockets": [listener]}, daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 15
        while not service.started and worker.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        require(service.started, "Owned scanner service did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        service.should_exit = True
        worker.join(timeout=15)
        listener.close()
        require(not worker.is_alive(), "Owned scanner service did not stop")


def run(
    connection,
    patch,
    verifier,
    *,
    project,
    endpoint,
    admin_email,
    fixture,
    owner,
    runtime,
    connected=False,
    postman_only=False,
    preview=False,
):
    from services.academic.app import authorization as academic_auth
    from services.academic.app import main as academic
    from services.gateway.app import authorization as gateway_auth
    from services.gateway.app import main as gateway
    from services.scheduling.app import authorization as scheduling_auth
    from services.scheduling.app import main as scheduling

    require(not preview or (connected and not postman_only), "Full connected preview required")
    persistent = preview and os.environ.get("CLASSSYNC_PERSISTENT_DEV") == "true"
    root = Path(os.environ["CLASSSYNC_AUTH_RUN_ROOT"])
    root.joinpath("synthetic-registration.pdf").write_bytes(pdf_bytes())
    fixture_images(root)
    url = SecretStr(
        URL.create(
            "postgresql+psycopg",
            username=connection.runtime,
            host="127.0.0.1",
            port=connection.port,
            database="postgres",
        ).render_as_string()
    )
    patch.setattr(gateway_auth, "FirebaseTokenVerifier", lambda _: verifier)
    patch.setattr(scheduling_auth, "FirebaseTokenVerifier", lambda _: verifier)
    if connected:
        patch.setattr(academic_auth, "FirebaseTokenVerifier", lambda _: verifier)
        patch.setattr(
            academic,
            "settings",
            academic.Settings(
                _env_file=None,
                classsync_env="test",
                firebase_project_id=project,
                institutional_tenant_id="tenant-a",
                enable_test_identity_adapters=True,
                academic_database_url=url,
                academic_database_transport="loopback-sspi-test",
                database_pool_size=2,
            ),
        )
    patch.setattr(
        scheduling,
        "settings",
        scheduling.Settings(
            _env_file=None,
            classsync_env="test",
            firebase_project_id=project,
            institutional_tenant_id="tenant-a",
            enable_test_identity_adapters=True,
            scheduling_database_url=url,
            scheduling_database_transport="loopback-sspi-test",
            database_pool_size=2 if connected else 5,
        ),
    )
    patch.setattr(gateway.settings, "identity_database_url", url)
    patch.setattr(gateway.settings, "identity_database_transport", "loopback-sspi-test")
    if connected:
        patch.setattr(gateway.settings, "database_pool_size", 2)
    patch.delattr(gateway.app.state, "authorization_adapters")
    patch.delattr(gateway.app.state, "onboarding_repository")

    def no_sqlite(*_args, **_kwargs):
        raise RuntimeError("SQLite fallback attempted by connected scanner")

    patch.setattr(sqlite3, "connect", no_sqlite)
    # Release setup-only idle connections before handing off to owned provider pools.
    runtime.dispose()
    owner.dispose()
    with ExitStack() as services:
        if connected:
            academic_url = services.enter_context(server(academic.app))
            patch.setattr(scheduling.settings, "academic_service_url", academic_url)
            patch.setattr(gateway.settings, "academic_service_url", academic_url)
        schedule_url = services.enter_context(server(scheduling.app))
        patch.setattr(gateway.settings, "scheduling_service_url", schedule_url)
        patch.setattr(
            gateway,
            "SERVICES",
            {
                "academic": academic_url if connected else "http://127.0.0.1:0",
                "scheduling": schedule_url,
            },
        )
        with server(gateway.app) as gateway_url:
            if persistent:
                with httpx.Client(timeout=5, trust_env=False) as client:
                    for service_name, service_url in {
                        "Gateway": gateway_url,
                        "Academic": academic_url,
                        "Scheduling": schedule_url,
                    }.items():
                        require(
                            client.get(service_url + "/health").status_code == 200,
                            f"{service_name} health check failed",
                        )
                        print(f"{service_name}: {service_url}/health", flush=True)
                    require(
                        client.get(gateway_url + "/api/v1/auth/me").status_code == 401,
                        "Gateway auth boundary not ready",
                    )
            postman = None
            if not preview and (
                postman_only or os.environ.get("CLASSSYNC_QUALIFY_POSTMAN") == "true"
            ):
                from scripts.postman_local_qualification import qualify as qualify_postman

                postman = qualify_postman(
                    root,
                    gateway=gateway_url,
                    endpoint=endpoint,
                    admin_email=admin_email,
                    fixture=fixture,
                    project=project,
                    complete=postman_only,
                )
            if postman_only:
                return {
                    "postman": postman,
                    "browser_executed": False,
                    "scope": "focused HTTP acceptance; prior browser evidence separate",
                }
            config = root / "registration-browser-config.json"
            config.write_text(
                json.dumps(
                    {
                        "root": str(root),
                        "project": project,
                        "authEndpoint": endpoint,
                        "gateway": gateway_url,
                        "fixture": fixture,
                        "adminEmail": admin_email,
                        "imageRoot": str(root),
                        "preview": preview,
                        "persistent": persistent,
                    }
                )
            )
            result = subprocess.run(
                [
                    shutil.which("node"),
                    (
                        "scripts/onboarding_browser.cjs"
                        if preview
                        else "scripts/connected_browser.cjs"
                        if connected
                        else "scripts/registration_browser.cjs"
                    ),
                    str(config),
                ],
                check=False,
                timeout=None if persistent else 630 if preview else 180,
            )
            require(result.returncode == 0, "Connected scanner browser qualification failed")
            evidence = json.loads(
                (
                    root
                    / (
                        "onboarding-browser-result.json"
                        if preview
                        else "connected-browser-result.json"
                        if connected
                        else "registration-browser-result.json"
                    )
                ).read_text()
            )
            if postman:
                evidence["postman"] = postman
    if connected and not preview:
        from scripts.classroom_request_qualification import qualify as qualify_requests

        evidence["request_database"] = qualify_requests(
            owner, runtime, project=project, request_id=evidence["classroomRequest"]["id"]
        )
    return evidence
