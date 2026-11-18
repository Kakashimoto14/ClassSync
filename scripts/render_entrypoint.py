"""Run the internal APIs behind a single Render gateway process.

This entrypoint is a constrained preview/qualification option. Services bind only to
loopback except the Gateway, and it performs no migrations, seeding, or database writes.
"""

import os
import signal
import subprocess
import sys
import time
from threading import Event
from urllib.error import URLError
from urllib.request import urlopen

INTERNAL_SERVICES = (
    ("academic", 8001, "services.academic.app.main:app"),
    ("scheduling", 8002, "services.scheduling.app.main:app"),
    ("notification", 8003, "services.notification.app.main:app"),
)


def deployment_port(environ):
    try:
        port = int(environ.get("PORT", "10000"))
    except (TypeError, ValueError) as error:
        raise ValueError("Render PORT must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("Render PORT must be between 1 and 65535")
    if port in {8001, 8002, 8003}:
        raise ValueError("Render PORT cannot overlap an internal service port")
    return port


def service_command(module, port, host):
    return [
        sys.executable,
        "-m",
        "uvicorn",
        module,
        "--host",
        host,
        "--port",
        str(port),
        "--workers",
        "1",
        "--no-access-log",
        "--no-proxy-headers",
    ]


def deployment_plan(port):
    plan = [
        (name, service_command(module, service_port, "127.0.0.1"), service_port)
        for name, service_port, module in INTERNAL_SERVICES
    ]
    plan.append(
        (
            "gateway",
            service_command("services.gateway.app.main:app", port, "0.0.0.0"),
            port,
        )
    )
    return plan


def wait_for_health(process, name, port, *, timeout=60, opener=urlopen, clock=time.monotonic,
                    sleep=time.sleep):
    deadline = clock() + timeout
    health_url = f"http://127.0.0.1:{port}/health"
    while clock() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Internal {name} service exited before health check")
        try:
            with opener(health_url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            pass
        sleep(0.25)
    raise RuntimeError(f"Internal {name} service did not become healthy")


def stop_children(children):
    for child in children:
        if child.poll() is None:
            child.terminate()
    for child in children:
        if child.poll() is None:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def main(environ=os.environ, *, popen=subprocess.Popen, opener=urlopen, sleep=time.sleep):
    port = deployment_port(environ)
    shutdown = Event()
    children = []
    prior_handlers = {}

    def request_shutdown(_signum, _frame):
        shutdown.set()

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            prior_handlers[signum] = signal.signal(signum, request_shutdown)

        for name, command, service_port in deployment_plan(port):
            child = popen(command, env=environ)
            children.append(child)
            if name != "gateway":
                wait_for_health(child, name, service_port, opener=opener, sleep=sleep)

        while not shutdown.wait(0.25):
            for _name, child in zip(
                [service[0] for service in deployment_plan(port)], children, strict=True
            ):
                result = child.poll()
                if result is not None:
                    # Fail the whole container if any service dies; the platform can
                    # restart a coherent set instead of routing to partial state.
                    return result or 1
        return 0
    finally:
        stop_children(children)
        for signum, handler in prior_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
