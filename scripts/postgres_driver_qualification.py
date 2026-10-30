"""Exercise the shared driver only in a newly created marked PostgreSQL cluster."""

import argparse
import json
from pathlib import Path

from classync_persistence.database import postgres_engine, transaction
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from scripts.postgres_disposable import DisposableConnection, qualify


def require(condition, description):
    if not condition:
        raise RuntimeError(description)


def engine_for(connection: DisposableConnection, *, bootstrap=False):
    parameters = connection.parameters(bootstrap=bootstrap)
    url = URL.create(
        "postgresql+psycopg", username=parameters["user"], host=parameters["host"],
        port=parameters["port"], database=parameters["dbname"],
    )
    return postgres_engine(url, connect_args=parameters)


def denied(engine, statement):
    try:
        with transaction(engine) as session:
            session.execute(text(statement))
    except DBAPIError as error:
        require(error.orig.sqlstate == "42501", "Expected insufficient_privilege SQLSTATE")
    else:
        raise RuntimeError("Forbidden runtime operation succeeded")


def exercise(connection: DisposableConnection) -> dict:
    owner = engine_for(connection, bootstrap=True)
    runtime = engine_for(connection)
    try:
        with transaction(owner) as session:
            observed = session.execute(text(
                "SELECT current_setting('data_directory'), current_user, inet_server_port(), "
                "host(inet_server_addr())"
            )).one()
            require(
                Path(observed[0]).resolve() == (connection.root / "data").resolve()
                and tuple(observed[1:]) == (connection.owner, connection.port, "127.0.0.1"),
                "Bootstrap driver target mismatch before first DDL",
            )
            session.execute(text("CREATE SCHEMA driver_probe"))
            session.execute(text("CREATE TABLE driver_probe.entries (id integer PRIMARY KEY)"))
            # Both names are generated internally, never request/client input.
            session.execute(text(f"GRANT USAGE ON SCHEMA driver_probe TO {connection.runtime}"))
            session.execute(text(
                f"GRANT SELECT, INSERT ON driver_probe.entries TO {connection.runtime}"
            ))
        with transaction(runtime) as session:
            role = session.execute(text(
                "SELECT current_user, rolsuper, rolcreatedb, rolcreaterole, rolreplication, "
                "rolbypassrls FROM pg_roles WHERE rolname = current_user"
            )).one()
            require(tuple(role) == (connection.runtime, False, False, False, False, False),
                    "Runtime role privileges differ from required least privilege")
            observed = session.execute(text(
                "SELECT host(inet_server_addr()), inet_server_port()"
            )).one()
            require(tuple(observed) == ("127.0.0.1", connection.port), "Driver target mismatch")
            session.execute(text("INSERT INTO driver_probe.entries VALUES (1)"))
            with transaction(owner) as observer:
                require(observer.scalar(text("SELECT count(*) FROM driver_probe.entries")) == 0,
                        "Uncommitted write leaked to another connection")
        with transaction(owner) as observer:
            require(observer.scalar(text("SELECT count(*) FROM driver_probe.entries")) == 1,
                    "Committed transaction not visible")
        try:
            with transaction(runtime) as session:
                session.execute(text("INSERT INTO driver_probe.entries VALUES (2)"))
                raise ValueError("synthetic application failure")
        except ValueError:
            pass
        with transaction(runtime) as session:
            require(session.scalar(text("SELECT count(*) FROM driver_probe.entries")) == 1,
                    "Failed transaction persisted a write")
            first_pid = session.scalar(text("SELECT pg_backend_pid()"))
            session.execute(text("SELECT set_config('classsync.tenant_id', :tenant, true)"),
                            {"tenant": "synthetic-tenant"})
            require(session.scalar(text("SELECT current_setting('classsync.tenant_id')"))
                    == "synthetic-tenant", "Transaction context not applied")
        with transaction(runtime) as session:
            require(session.scalar(text("SELECT pg_backend_pid()")) == first_pid,
                    "Pool reuse was not exercised")
            require(not session.scalar(text("SELECT current_setting('classsync.tenant_id', true)")),
                    "Transaction-local context leaked through pooled reuse")
        with runtime.connect() as session:
            session.execute(text("INSERT INTO driver_probe.entries VALUES (3)"))
        with transaction(runtime) as session:
            require(session.scalar(text("SELECT count(*) FROM driver_probe.entries")) == 1,
                    "Connection close failed to roll back")
        for statement in (
            "CREATE SCHEMA forbidden_schema",
            "CREATE TABLE public.forbidden_table (id int)",
            "CREATE TEMP TABLE forbidden_temp (id int)",
            f"SET ROLE {connection.owner}",
        ):
            denied(runtime, statement)
        return {
            "runtime": connection.runtime, "least_privilege": True,
            "commit_visibility": True, "exception_rollback": True,
            "pooled_context_reset": True, "connection_close_rollback": True,
            "ddl_and_owner_escalation_denied": True,
        }
    finally:
        runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("Output must be a new file in an existing directory")
    evidence = qualify(args.bin, exercise)
    with args.output.open("x") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
