"""Qualify a new disposable Windows PostgreSQL cluster; never attach to an existing one.

No passwords or trust-host authentication. This is local SSPI test infrastructure,
not institutional identity, a production database or permission to migrate originals.
"""

import argparse
import json
import os
import re
import socket
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

MARKER = "classsync-disposable-postgres-v1"


@dataclass(frozen=True)
class DisposableConnection:
    root: Path
    port: int
    owner: str
    runtime: str
    run_tool: Callable | None = None

    def parameters(self, *, bootstrap: bool = False) -> dict:
        # In-process libpq also reads PGHOSTADDR/service/credential variables.
        # Reject every ambient PG option before building a driver connection;
        # never print values, and never let a service file redirect this target.
        if any(key.upper().startswith("PG") for key in os.environ):
            raise ValueError("Ambient PostgreSQL settings prohibited in driver qualification")
        checked_root(self.root, Path(tempfile.gettempdir()))
        return {
            "host": "127.0.0.1",
            "port": self.port,
            "dbname": "postgres",
            "user": self.owner if bootstrap else self.runtime,
            "passfile": str(self.root / "nonexistent.pgpass"),
            "sslmode": "disable",
            "gssencmode": "disable",
            "require_auth": "sspi",
            "connect_timeout": 5,
            "options": "",
            "application_name": "classsync-disposable-qualification",
        }


def run_exercise(exercise, connection, evidence):
    try:
        evidence["exercise"] = exercise(connection)
    except Exception as error:
        evidence["exercise_error"] = str(error)
        raise


def create_root(parent: Path) -> Path:
    parent = parent.resolve()
    root = parent / ("classsync-pg-" + uuid4().hex)
    root.mkdir(exist_ok=False)
    (root / "classsync-marker.json").write_text(json.dumps({"kind": MARKER, "root": str(root)}))
    return checked_root(root, parent)


def checked_root(root: Path, parent: Path) -> Path:
    root, parent = root.resolve(), parent.resolve()
    if root.parent != parent or not re.fullmatch(r"classsync-pg-[a-f0-9]{32}", root.name):
        raise ValueError("Only a new direct disposable-cluster child is permitted")
    if not (root / "classsync-marker.json").is_file():
        raise ValueError("Disposable-cluster marker required")
    marker = json.loads((root / "classsync-marker.json").read_text())
    if marker != {"kind": MARKER, "root": str(root)}:
        raise ValueError("Disposable-cluster marker mismatch")
    if (root / "data").is_symlink() or (root / "data").resolve().parent != root:
        raise ValueError("Cluster data must remain under disposable root")
    return root


def finish_cluster(root: Path, parent: Path, run, started: bool, evidence: dict):
    try:
        checked_root(root, parent)
        if started or (root / "data" / "postmaster.pid").exists():
            run("pg_ctl.exe", "-D", root / "data", "-w", "-t", "20", "stop", "-m", "fast")
            evidence.update(stopped=True, server_state="stopped")
        else:
            evidence["server_state"] = "not_running_at_cleanup"
    except Exception as error:
        evidence.update(cleanup_error=str(error), server_state="stop_failed")
        raise
    finally:
        # Revalidate before writing; never follow a changed marker/junction outside
        # the disposable root, even while preserving shutdown failure evidence.
        checked_root(root, parent)
        with (root / "qualification.json").open("x") as output:
            output.write(json.dumps(evidence, indent=2) + "\n")


def qualify(
    binary_directory: Path,
    exercise: Callable[[DisposableConnection], dict] | None = None,
) -> dict:
    if os.name != "nt":
        raise RuntimeError("This qualification slice requires Windows SSPI")
    binary_directory = binary_directory.resolve(strict=True)
    for name in ("initdb.exe", "pg_ctl.exe", "psql.exe", "pg_dump.exe", "pg_restore.exe"):
        if not (binary_directory / name).is_file():
            raise ValueError("Explicit installed PostgreSQL binaries required")
    parent = Path(tempfile.gettempdir()).resolve()
    root = create_root(parent)
    print(f"New disposable PostgreSQL root: {root}", flush=True)
    owner = "classsync_qa_" + uuid4().hex
    username, realm = os.environ.get("USERNAME", ""), os.environ.get("USERDOMAIN", "")
    if not username or not realm or any(c in username + realm for c in '\n\r"\\'):
        raise ValueError("An explicit local Windows SSPI principal is required")
    principal = username + "@" + realm
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    env.update(
        PGPASSFILE=str(root / "nonexistent.pgpass"),
        PGSSLMODE="disable",
        PGGSSENCMODE="disable",
        PGCONNECT_TIMEOUT="5",
    )
    evidence = {"root": str(root), "authentication": "sspi", "stopped": False}

    def run(executable, *arguments, timeout=45):
        checked_root(root, parent)
        if executable not in {"initdb.exe", "pg_ctl.exe", "psql.exe",
                              "pg_dump.exe", "pg_restore.exe"}:
            raise ValueError("Only explicit PostgreSQL qualification tools permitted")
        command_id = uuid4().hex
        stdout_path, stderr_path = root / (command_id + ".out"), root / (command_id + ".err")
        # A Windows postmaster may inherit pg_ctl's output handles. Pipes can
        # indefinitely delay communicate() even after pg_ctl exits; files cannot.
        with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
            result = subprocess.run(
                [str(binary_directory / executable), *map(str, arguments)],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        out = stdout_path.read_text(errors="replace")
        err = stderr_path.read_text(errors="replace")
        if result.returncode:
            raise RuntimeError(f"{executable} failed: {out}\n{err}")
        return out.strip()

    started = False
    try:
        evidence["initdb"] = run(
            "initdb.exe",
            "-D",
            root / "data",
            "-U",
            owner,
            "--auth-host=sspi",
            "--auth-local=reject",
            "--encoding=UTF8",
            "--no-locale",
        )
        with socket.socket() as allocation:
            allocation.bind(("127.0.0.1", 0))
            port = allocation.getsockname()[1]
        if port == 5432:
            raise RuntimeError("Default PostgreSQL port is prohibited")
        (root / "data" / "pg_hba.conf").write_text(
            "host all all 127.0.0.1/32 sspi include_realm=1 map=classsync_qa\n"
            "host all all 0.0.0.0/0 reject\nhost all all ::0/0 reject\n"
        )
        (root / "data" / "pg_ident.conf").write_text(f'classsync_qa "{principal}" {owner}\n')
        with (root / "data" / "postgresql.conf").open("a") as config:
            config.write(
                f"\nlisten_addresses='127.0.0.1'\nport={port}\n"
                "unix_socket_directories=''\nmax_connections=10\n"
            )
        run("pg_ctl.exe", "-D", root / "data", "-l", root / "server.log", "-w", "-t", "20", "start")
        started = True
        evidence["port"] = port
        answer = run(
            "psql.exe",
            "-X",
            "--no-password",
            "-h",
            "127.0.0.1",
            "-p",
            port,
            "-U",
            owner,
            "-d",
            "postgres",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "SELECT json_build_object('version',current_setting('server_version'),"
            "'data_directory',current_setting('data_directory'),'user',current_user,"
            "'port',inet_server_port(),'smoke',1+1)",
        )
        observed = json.loads(answer)
        if (
            Path(observed["data_directory"]).resolve() != (root / "data").resolve()
            or observed["port"] != port
            or observed["user"] != owner
            or observed["smoke"] != 2
        ):
            raise RuntimeError("Connected server does not match the new disposable cluster")
        evidence["server"] = observed
        # No mapping exists for this role; OS authentication alone must not grant it.
        try:
            run(
                "psql.exe",
                "-X",
                "--no-password",
                "-h",
                "127.0.0.1",
                "-p",
                port,
                "-U",
                "classsync_unmapped",
                "-d",
                "postgres",
                "-c",
                "SELECT 1",
            )
        except RuntimeError as error:
            if "SSPI authentication failed" not in str(error):
                raise
            evidence["unmapped_role_denied"] = True
        else:
            raise RuntimeError("Unmapped database role unexpectedly authenticated")
        if exercise is not None:
            runtime = "classsync_runtime_" + uuid4().hex
            run(
                "psql.exe", "-X", "--no-password", "-h", "127.0.0.1", "-p", port,
                "-U", owner, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
                f"CREATE ROLE {runtime} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS; "
                "REVOKE ALL ON DATABASE postgres FROM PUBLIC; "
                f"GRANT CONNECT ON DATABASE postgres TO {runtime}; "
                "REVOKE ALL ON SCHEMA public FROM PUBLIC;",
            )
            with (root / "data" / "pg_ident.conf").open("a") as mapping:
                mapping.write(f'classsync_qa "{principal}" {runtime}\n')
            run("pg_ctl.exe", "-D", root / "data", "reload")
            run_exercise(exercise, DisposableConnection(root, port, owner, runtime, run), evidence)
        return evidence
    finally:
        # A failed pg_ctl start may still have left this specific postmaster live.
        # Check only the new marked cluster; never a service or arbitrary PID.
        finish_cluster(root, parent, run, started, evidence)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("Qualification output must be a new file in an existing directory")
    evidence = qualify(args.bin)
    with args.output.open("x") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
