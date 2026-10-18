"""One-command local sandbox. No seeding, auth bypass, database resets or publication."""

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from threading import Event, Thread

ROOT = Path(__file__).resolve().parents[1]


def response(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as value:
            return value.status
    except (urllib.error.URLError, TimeoutError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=5173)
    args = parser.parse_args()
    children = []
    stopped = Event()

    def commands():
        if sys.stdin.readline().strip() == "stop":
            stopped.set()

    env = {
        **os.environ,
        "CLASSSYNC_ENV": "development",
        "ENABLE_SCHEDULING_SANDBOX": "true",
        "ACADEMIC_SERVICE_URL": f"http://127.0.0.1:{args.base_port + 1}",
        "SCHEDULING_SERVICE_URL": f"http://127.0.0.1:{args.base_port + 2}",
        "CLASSSYNC_GATEWAY_URL": f"http://127.0.0.1:{args.base_port}",
    }
    try:
        for service, port in [
            ("academic", args.base_port + 1),
            ("scheduling", args.base_port + 2),
            ("gateway", args.base_port),
        ]:
            url = f"http://127.0.0.1:{port}"
            if response(url + "/health") != 200:
                children.append(
                    subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            f"services.{service}.app.main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                        ],
                        cwd=ROOT,
                        env=env,
                        stdin=subprocess.DEVNULL,
                    )
                )
            for _ in range(80):
                if stopped.is_set():
                    raise KeyboardInterrupt
                if response(url + "/health") == 200:
                    break
                if any(p.poll() is not None for p in children):
                    raise RuntimeError(
                        f"{service} startup failed. Install requirements and check port {port}."
                    )
                time.sleep(0.25)
            else:
                raise RuntimeError(
                    f"{service} unavailable on {port}; inspect service output and retry."
                )
            print(f"{service}: healthy on {port}", flush=True)
        for port, path in [
            (args.base_port + 1, "/api/v1/academic/sandbox/periods"),
            (args.base_port + 2, "/api/v1/scheduling/sandbox/catalogs"),
            (args.base_port + 2, "/api/v1/scheduling/sandbox/calendar-samples"),
            (args.base_port + 2, "/api/v1/timetables/sandbox/periods"),
            (args.base_port, "/api/v1/academic/sandbox/periods"),
            (args.base_port, "/api/v1/timetables/sandbox/periods"),
            (args.base_port, "/api/v1/scheduling/sandbox/calendar-samples"),
        ]:
            if response(f"http://127.0.0.1:{port}{path}") != 200:
                raise RuntimeError(
                    f"Existing service on {port} is not a compatible enabled local sandbox. "
                    "Stop that service or use --base-port with three unused ports."
                )
        node = os.environ.get("CLASSSYNC_NODE_RUNTIME") or shutil.which("node")
        if not node:
            raise RuntimeError("Node.js is required to start the frontend.")
        if response(f"http://127.0.0.1:{args.web_port}/") is not None:
            raise RuntimeError("Frontend port already in use. Choose an unused --web-port.")
        children.append(
            subprocess.Popen(
                [
                    node,
                    str(ROOT / "node_modules/vite/bin/vite.js"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.web_port),
                    "--strictPort",
                ],
                cwd=ROOT / "apps/web",
                env=env,
                stdin=subprocess.PIPE,
            )
        )
        for _ in range(80):
            if stopped.is_set():
                raise KeyboardInterrupt
            if response(f"http://127.0.0.1:{args.web_port}/") == 200:
                break
            if children[-1].poll() is not None:
                raise RuntimeError("Frontend startup failed. Choose an unused --web-port.")
            time.sleep(0.25)
        else:
            raise RuntimeError("Frontend unavailable; inspect Vite output.")
        for port in range(args.base_port, args.base_port + 3):
            if response(f"http://127.0.0.1:{port}/health") != 200:
                raise RuntimeError(f"Service on {port} stopped during startup; retry the launcher.")
        print(
            f"Workspace ready: http://127.0.0.1:{args.web_port}/ "
            "(local sandbox; no automatic fixture import or publishing)",
            flush=True,
        )
        print(
            f"API: {env['CLASSSYNC_GATEWAY_URL']} · "
            f"Academic DB: {env.get('ACADEMIC_DATABASE_PATH', 'var/academic.sqlite3')} · "
            f"Scheduling DB: {env.get('SCHEDULING_DATABASE_PATH', 'var/scheduling.sqlite3')}",
            flush=True,
        )
        Thread(target=commands, daemon=True).start()
        while not stopped.is_set() and all(p.poll() is None for p in children):
            stopped.wait(1)
        if not stopped.is_set():
            raise RuntimeError("A workspace process exited; inspect its output and restart.")
    except KeyboardInterrupt:
        pass
    except (RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
