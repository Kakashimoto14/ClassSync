"""Throwaway loopback PostgreSQL cluster for tests that need real SQL, RLS and triggers.

Starts a new cluster in a temporary directory with a non-superuser migrator (table owner), a
data operator and a runtime role; it never connects to a configured or hosted database.
"""

import os
import re
import secrets
import shutil
import socket
import subprocess
import time
from glob import glob
from pathlib import Path
from types import SimpleNamespace

import pytest
from classync_persistence import schema
from classync_persistence.database import postgres_engine, transaction
from sqlalchemy import text
from sqlalchemy.engine import URL

SCHEMAS = ("classsync_identity", "classsync_academic", "classsync_scheduling")
BINARIES = ("initdb", "postgres", "pg_ctl")
# Debian/Ubuntu (including GitHub-hosted runners) keep server binaries off PATH.
INSTALL_ROOTS = ("/usr/lib/postgresql/*/bin", r"C:\Program Files\PostgreSQL\*\bin")


def server_binaries():
    """Locate initdb/postgres/pg_ctl from an override, PATH or the standard install roots."""
    suffix = ".exe" if os.name == "nt" else ""
    on_path = shutil.which("initdb")
    installed = [item for pattern in INSTALL_ROOTS for item in glob(pattern)]
    installed.sort(key=lambda item: [int(n) for n in re.findall(r"\d+", item)], reverse=True)
    for candidate in (
        os.environ.get("CLASSSYNC_TEST_PG_BIN"),
        str(Path(on_path).parent) if on_path else None,
        *installed,
    ):
        if candidate and all((Path(candidate) / (name + suffix)).is_file() for name in BINARIES):
            return {name: str(Path(candidate) / (name + suffix)) for name in BINARIES}
    return None


def unavailable(reason):
    # CI runners ship PostgreSQL, so being unable to run it there is a failure, not a skip.
    if os.environ.get("GITHUB_ACTIONS"):
        pytest.fail(reason)
    pytest.skip(reason)


@pytest.fixture(scope="module")
def cluster(tmp_path_factory):
    binaries = server_binaries()
    if binaries is None:
        unavailable("PostgreSQL server binaries are not installed (set CLASSSYNC_TEST_PG_BIN)")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        unavailable("initdb refuses to run as root; run the tests as an unprivileged user")
    import psycopg

    root = tmp_path_factory.mktemp("pg")
    data, password = root / "data", secrets.token_hex(24)
    (root / "pw").write_text(password)
    # Ambient libpq settings must never redirect this disposable target.
    environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
    subprocess.run(
        [binaries["initdb"], "-D", str(data), "-U", "boot", "--auth-host=scram-sha-256",
         "--auth-local=reject", f"--pwfile={root / 'pw'}", "--encoding=UTF8", "--no-locale"],
        env=environment, stdin=subprocess.DEVNULL, capture_output=True, timeout=180, check=True,
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    log = (root / "server.log").open("w")
    # No unix socket: the Linux default directory is not writable by an unprivileged user.
    server = subprocess.Popen(
        [binaries["postgres"], "-D", str(data), "-p", str(port), "-c",
         "listen_addresses=127.0.0.1", "-c", "unix_socket_directories=", "-c", "fsync=off"],
        env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 60
        while True:
            try:
                psycopg.connect(
                    host="127.0.0.1", port=port, user="boot", password=password,
                    dbname="postgres", connect_timeout=2,
                ).close()
                break
            except psycopg.OperationalError:
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError((root / "server.log").read_text()[-2000:]) from None
                time.sleep(0.2)
        yield SimpleNamespace(port=port, password=password)
    finally:
        subprocess.run(
            [binaries["pg_ctl"], "-D", str(data), "-m", "immediate", "-w", "stop"],
            env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=60, check=False,
        )
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()


def execute(session, statement, **params):
    return session.execute(text(statement), params)


def provision(cluster):
    """Create roles, migrate as the non-superuser owner and apply the shared base grants.

    Returns a cached `engine(user)` factory and its engine registry. The runtime role gets
    read-only identity and scheduling plus academic DML; callers add anything further.
    """
    engines = {}

    def engine(user):
        engines.setdefault(user, postgres_engine(URL.create(
            "postgresql+psycopg", username=user, password=cluster.password,
            host="127.0.0.1", port=cluster.port, database="postgres",
        )))
        return engines[user]

    with transaction(engine("boot")) as db:
        for role in ("migrator", "operator", "runtime"):
            execute(db, f"CREATE ROLE {role} LOGIN PASSWORD '{cluster.password}' "
                        "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS")
        execute(db, "GRANT CREATE ON DATABASE postgres TO migrator")
        execute(db, "GRANT USAGE,CREATE ON SCHEMA public TO migrator")
    with transaction(engine("migrator")) as db:
        schema.migrate(db)
    with transaction(engine("boot")) as db:
        for name in SCHEMAS:
            execute(db, f"GRANT USAGE ON SCHEMA {name} TO operator, runtime")
            execute(db, f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {name} "
                        "TO operator")
        # Least privilege: identity and scheduling are read-only for the runtime role, so
        # roster identity writes must go through the SECURITY DEFINER functions.
        execute(db, "GRANT SELECT ON ALL TABLES IN SCHEMA classsync_identity TO runtime")
        execute(db, "GRANT SELECT ON ALL TABLES IN SCHEMA classsync_scheduling TO runtime")
        execute(db, "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "
                    "classsync_academic TO runtime")
    return SimpleNamespace(engine=engine, engines=engines)
