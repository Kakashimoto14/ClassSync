import pytest

from scripts.render_entrypoint import deployment_plan, deployment_port


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
