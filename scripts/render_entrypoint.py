"""Run the internal APIs behind a single Render gateway process.

This entrypoint is a constrained preview/qualification option. Services bind only to
loopback except the Gateway, and it performs no migrations, seeding, or database writes.
"""

import ipaddress
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def forwarded_allowlist(value):
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if not entries:
        return None
    canonical = []
    for entry in entries:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError as error:
            raise ValueError(
                "Trusted proxy entries must be IP addresses or CIDR networks"
            ) from error
        if network.prefixlen == 0:
            raise ValueError("A default-route CIDR cannot be trusted as a proxy range")
        canonical.append(str(network))
    return ",".join(canonical)


def service_command(module, port, host, forwarded_allow_ips=None):
    command = [
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
    ]
    if host == "0.0.0.0" and forwarded_allow_ips:
        command.extend(
            ["--proxy-headers", "--forwarded-allow-ips", forwarded_allow_ips]
        )
    else:
        command.append("--no-proxy-headers")
    return command


def deployment_plan(port, forwarded_allow_ips=None):
    plan = [
        (name, service_command(module, service_port, "127.0.0.1"), service_port)
        for name, service_port, module in INTERNAL_SERVICES
    ]
    plan.append(
        (
            "gateway",
            service_command(
                "services.gateway.app.main:app", port, "0.0.0.0", forwarded_allow_ips
            ),
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


def start_internal_services(plan, environ, *, popen=subprocess.Popen, opener=urlopen,
                            sleep=time.sleep):
    """Start every private API before polling health checks concurrently."""
    internal_services = plan[:-1]
    children = []
    try:
        for _name, command, _port in internal_services:
            children.append(popen(command, env=environ))

        with ThreadPoolExecutor(max_workers=len(internal_services)) as executor:
            checks = {
                executor.submit(
                    wait_for_health, child, name, port, opener=opener, sleep=sleep
                ): name
                for (name, _command, port), child in zip(
                    internal_services, children, strict=True
                )
            }
            for check in as_completed(checks):
                check.result()
    except Exception:
        stop_children(children)
        raise
    return children


def main(environ=os.environ, *, popen=subprocess.Popen, opener=urlopen, sleep=time.sleep):
    port = deployment_port(environ)
    trusted_proxies = forwarded_allowlist(environ.get("TRUSTED_PROXY_IPS", ""))
    shutdown = Event()
    children = []
    prior_handlers = {}

    def request_shutdown(_signum, _frame):
        shutdown.set()

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            prior_handlers[signum] = signal.signal(signum, request_shutdown)

        plan = deployment_plan(port, trusted_proxies)
        children.extend(
            start_internal_services(plan, environ, popen=popen, opener=opener, sleep=sleep)
        )
        _name, gateway_command, _gateway_port = plan[-1]
        children.append(popen(gateway_command, env=environ))

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
