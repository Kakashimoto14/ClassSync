import pytest

from scripts.container_entrypoint import configuration


@pytest.mark.parametrize("service", ["gateway", "academic", "scheduling"])
def test_cloud_run_port_and_existing_service_entry(service):
    assert configuration({"CLASSSYNC_SERVICE": service, "PORT": "8181"}) == (
        f"services.{service}.app.main:app",
        8181,
    )


@pytest.mark.parametrize(
    "values",
    [
        {"CLASSSYNC_SERVICE": "other.module"},
        {"PORT": "0"},
        {"PORT": "65536"},
        {"PORT": "not-a-port"},
    ],
)
def test_container_refuses_unknown_code_or_invalid_port(values):
    with pytest.raises(ValueError):
        configuration(values)
