import pytest

from scripts.render_entrypoint import (
    deployment_plan,
    deployment_port,
    forwarded_allowlist,
    start_internal_services,
)


@pytest.mark.parametrize("value", ["", "zero", "0", "65536", "8001", "8002", "8003"])
def test_render_entrypoint_rejects_invalid_or_reserved_public_port(value):
    with pytest.raises(ValueError):
        deployment_port({"PORT": value})


def test_render_entrypoint_uses_platform_port_and_loopback_for_internal_services():
    plan = deployment_plan(deployment_port({"PORT": "10000"}))
    assert [(name, port) for name, _command, port in plan] == [
        ("academic", 8001),
        ("scheduling", 8002),
        ("notification", 8003),
        ("gateway", 10000),
    ]
    assert all(command[command.index("--host") + 1] == "127.0.0.1" for _, command, _ in plan[:3])
    assert plan[3][1][plan[3][1].index("--host") + 1] == "0.0.0.0"
    assert all("--no-access-log" in command for _, command, _ in plan)


def test_proxy_headers_are_disabled_unless_trusted_ips_are_explicit():
    default_plan = deployment_plan(10000)
    gateway_command = default_plan[-1][1]
    assert "--no-proxy-headers" in gateway_command

    trusted = forwarded_allowlist("10.0.0.0/8,2001:db8::/32")
    trusted_plan = deployment_plan(10000, trusted)
    gateway_command = trusted_plan[-1][1]
    assert "--no-proxy-headers" not in gateway_command
    assert "--forwarded-allow-ips" in gateway_command
    assert gateway_command[gateway_command.index("--forwarded-allow-ips") + 1] == (
        "10.0.0.0/8,2001:db8::/32"
    )


@pytest.mark.parametrize(
    "value", ["*", "0.0.0.0/0", "::/0", "proxy.example.com", "10.0.0.1,not-an-ip"]
)
def test_proxy_header_opt_in_rejects_unbounded_or_unparseable_trust(value):
    with pytest.raises(ValueError):
        forwarded_allowlist(value)


def test_starts_all_internal_services_before_waiting_for_health_in_parallel():
    from threading import Barrier, Lock

    events = []
    event_lock = Lock()
    health_barrier = Barrier(3)

    class Process:
        def __init__(self, port):
            self.port = port

        def poll(self):
            return None

    def popen(command, *, env):
        port = int(command[command.index("--port") + 1])
        with event_lock:
            events.append(("spawn", port))
        return Process(port)

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def opener(url, *, timeout):
        port = int(url.rsplit(":", 1)[1].split("/", 1)[0])
        with event_lock:
            events.append(("health", port))
            assert len([event for event in events if event[0] == "spawn"]) == 3
        health_barrier.wait(timeout=2)
        return Response()

    plan = deployment_plan(10000)
    children = start_internal_services(
        plan, {}, popen=popen, opener=opener, sleep=lambda _delay: None
    )

    assert [child.port for child in children] == [8001, 8002, 8003]
    assert {port for event, port in events if event == "health"} == {8001, 8002, 8003}
