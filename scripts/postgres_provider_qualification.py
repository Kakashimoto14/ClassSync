"""Actual Gateway-owned configured membership lifecycle on a new PostgreSQL cluster."""

import argparse
import json
import time
from contextlib import ExitStack
from pathlib import Path

import pytest
from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import change_membership_state
from classync_persistence.memberships import identity_context
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event, text
from sqlalchemy.engine import URL

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_identity_qualification import exercise as identity_exercise
from services.testing.offline_firebase import offline_firebase


def exercise(connection):
    foundation = identity_exercise(connection)
    from services.gateway.app import authorization as providers
    from services.gateway.app import main as gateway

    owner = engine_for(connection, bootstrap=True)
    parameters = connection.parameters()
    url = URL.create(
        "postgresql+psycopg", username=parameters["user"], host=parameters["host"],
        port=parameters["port"], database=parameters["dbname"],
    )

    def state(expected, value):
        with transaction(owner) as session:
            identity_context(session, tenant_id="tenant-a", uid="uid-a")
            return change_membership_state(
                session, tenant_id="tenant-a", uid="uid-a", expected_revision=expected,
                state=value, actor=VerifiedPrincipal(uid="uid-admin"),
            )

    def no_owned_connections(engine):
        require(engine.pool.checkedout() == 0 and engine.pool.checkedin() == 0,
                "Disposed provider retained pooled connections")
        with transaction(owner) as session:
            require(session.scalar(text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE usename=:runtime AND application_name='classsync-gateway-identity'
            """), {"runtime": connection.runtime}) == 0,
                "Provider shutdown left a database session")
        require(not hasattr(gateway.app.state, "authorization_adapters"),
                "Provider shutdown left authorization adapters")

    try:
        require(state(2, MembershipState.ACTIVE) == 3, "Synthetic activation failed")
        require(not hasattr(gateway.app.state, "authorization_adapters"),
                "Qualification must not overwrite an existing provider")
        with pytest.MonkeyPatch.context() as patch, offline_firebase(patch) as sdk:
            verifier, encoded, _, _ = sdk
            settings = gateway.Settings(
                _env_file=None, classsync_env="test", institutional_tenant_id="tenant-a",
                enable_test_identity_adapters=False, firebase_project_id="synthetic-project",
                firebase_service_account_json=None, firebase_client_email=None,
                firebase_private_key=None,
                identity_database_url=SecretStr(url.render_as_string(hide_password=False)),
                identity_database_transport="loopback-sspi-test",
            )
            patch.setattr(gateway, "settings", settings)
            # Keep actual offline SDK crypto; do not inject membership adapters.
            patch.setattr(providers, "FirebaseTokenVerifier", lambda _: verifier)
            headers = {"Authorization": "Bearer " + encoded(sub="uid-a"),
                       "X-ClassSync-Role": "student"}

            def request(client, status, code=None):
                response = client.get("/api/v1/auth/me", headers=headers)
                require(response.status_code == status, f"Provider HTTP expected{status}")
                if code:
                    require(response.json()["error"]["code"] == code, "Wrong provider failure")
                return response.json()

            with TestClient(gateway.app) as client:
                adapters = gateway.app.state.authorization_adapters
                engine = adapters.memberships.engine
                require(adapters.verifier is verifier, "Actual SDK verifier not composed")
                with transaction(engine) as session:
                    require(session.scalar(text("SHOW statement_timeout")) == "5s"
                            and session.scalar(text("SHOW lock_timeout")) == "1500ms",
                            "Configured query/lock deadlines not applied by PostgreSQL")
                    role = session.execute(text("""
                        SELECT current_user, rolsuper, rolcreatedb, rolcreaterole,
                               rolreplication, rolbypassrls
                        FROM pg_roles WHERE rolname=current_user
                    """)).one()
                    require(tuple(role) == (connection.runtime, False, False, False, False, False),
                            "Configured provider did not use least-privilege runtime")
                require(request(client, 200)["data"]["student_id"] == "student-a",
                        "Configured provider lost explicit academic record binding")
                require(engine.pool.timeout() == 3, "Identity pool wait is not bounded")
                errors = []

                def record_failure(context):
                    errors.append(getattr(context.original_exception, "sqlstate", None))

                event.listen(engine, "handle_error", record_failure)
                try:
                    with transaction(owner) as blocker:
                        blocker.execute(text(
                            "LOCK TABLE classsync_identity.memberships IN ACCESS EXCLUSIVE MODE"
                        ))
                        started = time.monotonic()
                        request(client, 503, "membership_unavailable")
                        require(time.monotonic() - started < 8,
                                "Membership lock failure exceeded bounded wait")
                    require(errors == ["55P03"], "Expected actual PostgreSQL lock_timeout")
                finally:
                    event.remove(engine, "handle_error", record_failure)
                request(client, 200)
                # Gateway's explicit five-slot cap does not allocate overflow.
                # Hold all actual owned connections and exercise checkout timeout.
                with ExitStack() as held:
                    for _ in range(5):
                        held.enter_context(engine.connect())
                    require(engine.pool.checkedout() == 5, "Pool not actually exhausted")
                    started = time.monotonic()
                    request(client, 503, "membership_unavailable")
                    require(2.5 <= time.monotonic() - started < 8,
                            "Pool exhaustion did not use bounded checkout deadline")
                request(client, 200)
                require(state(3, MembershipState.REVOKED) == 4, "Revoke failed")
                request(client, 403, "membership_denied")
                with transaction(owner) as session:
                    session.execute(text(
                        f"REVOKE SELECT ON classsync_identity.tenants FROM {connection.runtime}"
                    ))
                try:
                    request(client, 503, "membership_unavailable")
                finally:
                    with transaction(owner) as session:
                        session.execute(text(
                            f"GRANT SELECT ON classsync_identity.tenants TO {connection.runtime}"
                        ))
                require(state(4, MembershipState.ACTIVE) == 5, "Reactivate failed")
                require(request(client, 200)["data"]["membership_revision"] == 5,
                        "Configured provider cached stale membership")
            no_owned_connections(engine)
            # A second actual lifespan gets a new pool and current committed state.
            with TestClient(gateway.app) as client:
                restarted = gateway.app.state.authorization_adapters.memberships.engine
                require(restarted is not engine, "Restart reused disposed pool")
                require(request(client, 200)["data"]["membership_revision"] == 5,
                        "Restart did not read persisted membership")
            no_owned_connections(restarted)
            try:
                with TestClient(gateway.app) as client:
                    exceptional = gateway.app.state.authorization_adapters.memberships.engine
                    request(client, 200)
                    raise RuntimeError("synthetic caller failure")
            except RuntimeError as error:
                require(str(error) == "synthetic caller failure", "Unexpected lifecycle failure")
            no_owned_connections(exceptional)
        return {"foundation": foundation, "configured_gateway_lifespan": True,
                "real_sdk_current_pg_record_binding": True,
                "least_privilege_current_revocation_outage": True,
                "normal_exceptional_shutdown_and_restart": True,
                "actual_lock_and_pool_timeout_recovery": True,
                "production_tls_transport_qualified": False}
    finally:
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("New output file required")
    evidence = qualify(args.bin, exercise)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")
    print("Configured Gateway provider qualification passed; owned PostgreSQL stopped")


if __name__ == "__main__":
    main()
