"""Hosting output contract; provider metadata here is synthetic and never deployed."""

from copy import deepcopy

import pytest
from classync_contracts import cloud_run, firebase
from classync_persistence.configuration import postgres_configuration
from pydantic import SecretStr, ValidationError

from scripts import hosting_plan
from scripts.container_entrypoint import configuration
from scripts.hosting_plan import HostingMetadata, inventory, render
from services.academic.app.main import Settings as AcademicSettings
from services.gateway.app.main import Settings as GatewaySettings
from services.scheduling.app.main import Settings as SchedulingSettings


def synthetic_metadata():
    project = "classsync-hosting-probe"
    return {
        "profile": "preview", "cloud_project": project, "region": "asia-southeast1",
        "tenant": "synthetic", "network": "probe-network", "subnet": "probe-subnet",
        "vercel_project": "classsync-connected-probe",
        "vercel_origin": "https://classsync-connected-probe.vercel.app",
        "source_branch": "feature/auth-onboarding-saas", "production_branch": "main",
        "firebase_web": {
            "apiKey": "synthetic-browser-configuration-only",
            "projectId": project, "authDomain": project + ".firebaseapp.com",
            "appId": "1:1234:web:abcde",
        },
        "sql_root_ca": {"name": "synthetic-ca", "version": 1},
        "services": {
            role: {
                "name": role + "-probe", "origin": f"https://{role}-probe.run.app",
                "identity": f"{role}@{project}.iam.gserviceaccount.com",
                "image": f"asia-southeast1-docker.pkg.dev/{project}/probe/{role}@sha256:"
                + digit * 64,
                "database_secret": {"name": f"{role}-dsn", "version": 2},
            }
            for role, digit in zip(("academic", "scheduling", "gateway"), "abc", strict=True)
        },
    }


def test_rendered_environment_is_consumed_and_routes_are_isolated():
    metadata = HostingMetadata.model_validate(synthetic_metadata())
    result = render(metadata)
    config = result["vercel.connected.json"]
    assert config["buildCommand"] == "npm run build"
    assert config["rewrites"][0] == {
        "source": "/api/v1/:path*", "destination": "https://gateway-probe.run.app/api/v1/:path*",
    }
    assert not any("/dev" in rule["source"] for rule in config["rewrites"])
    web = result["vercel.variables.json"]
    assert web["target"] == "preview" and web["values"]["VITE_API_BASE_URL"] == "/api/v1"
    assert set(web["values"]) <= set(inventory()["web"])
    assert result["review.json"]["deploy_authorized"] is False
    for role, cls, prefix in (
        ("gateway", GatewaySettings, "IDENTITY"),
        ("academic", AcademicSettings, "ACADEMIC"),
        ("scheduling", SchedulingSettings, "SCHEDULING"),
    ):
        template = result[f"cloudrun.{role}.json"]["spec"]["template"]["spec"]
        env = template["containers"][0]["env"]
        assert {item["name"] for item in env} <= (
            {key.upper() for key in cls.model_fields} | {"CLASSSYNC_SERVICE"}
        )
        references = [item for item in env if "valueFrom" in item]
        assert references == [{"name": prefix + "_DATABASE_URL", "valueFrom": {
            "secretKeyRef": {"name": f"{role}-dsn", "key": "2"},
        }}]
        values = {item["name"]: item["value"] for item in env if "value" in item}
        values.update({"K_SERVICE": role, prefix + "_DATABASE_URL": "synthetic-preflight"})
        assert configuration(values) == (f"services.{role}.app.main:app", 8080)
        with pytest.raises(ValueError):
            configuration(values | {"FIREBASE_AUTH_EMULATOR_HOST": "127.0.0.1:9099"})
        with pytest.raises(ValueError):
            configuration(values | {"FIREBASE_USE_ADC": "false"})
        assert template["volumes"][0]["secret"]["items"][0]["key"] == "1"


@pytest.mark.parametrize("change", [
    {"vercel_project": "class-sync-bhiv"},
    {"vercel_origin": "https://class-sync-bhiv.vercel.app"},
    {"source_branch": "main"},
    {"firebase_web": {"projectId": "unrelated"}},
    {"services": {}},
    {"credential": "never-accepted"},
])
def test_rejects_unapproved_or_contradictory_metadata(change):
    with pytest.raises(ValidationError):
        HostingMetadata.model_validate(synthetic_metadata() | change)


def test_production_profile_has_separate_scope():
    metadata = deepcopy(synthetic_metadata())
    metadata.update(profile="production", source_branch="main")
    assert render(HostingMetadata.model_validate(metadata))["vercel.variables.json"][
        "target"
    ] == "production"


def test_metadata_refresh_preserves_reviewed_images_and_selects_safe_fields(monkeypatch):
    selected = synthetic_metadata()
    original = deepcopy(selected)

    def provider(tool, arguments):
        if tool == "firebase":
            assert arguments[:2] == ["apps:sdkconfig", "WEB"]
            return {"result": {"sdkConfig": original["firebase_web"] | {"measurementId": "old"}}}
        assert tool == "gcloud" and arguments[:3] == ["run", "services", "describe"]
        role = arguments[3].split("-")[0]
        remote = original["services"][role]
        return {"status": {"url": remote["origin"]}, "spec": {"template": {"spec": {
            "serviceAccountName": remote["identity"],
            "containers": [{"image": "unreviewed-old:tag"}],
        }}}}

    monkeypatch.setattr(hosting_plan, "provider_json", provider)
    refreshed = HostingMetadata.model_validate(hosting_plan.refresh_provider_values(selected))
    assert refreshed.firebase_web.model_dump(exclude_none=True) == original["firebase_web"]
    for role, service in refreshed.services.items():
        assert service.image == original["services"][role]["image"]


def test_adc_is_explicit_project_bound_and_rejects_legacy_keys(monkeypatch):
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    monkeypatch.setattr(firebase.firebase_admin, "_apps", {})
    calls = []

    class App:
        project_id = "classsync-hosting-probe"
        credential = firebase.credentials.ApplicationDefault()

    def initialize(**kwargs):
        calls.append(kwargs)
        return App()

    monkeypatch.setattr(firebase.firebase_admin, "initialize_app", initialize)
    settings = firebase.FirebaseSettings(_env_file=None, firebase_use_adc=True,
                                         firebase_project_id=App.project_id)
    assert firebase.initialize_firebase(settings).project_id == App.project_id
    assert calls == [{"options": {"projectId": App.project_id},
                      "name": "classsync-adc-" + App.project_id}]
    with pytest.raises(RuntimeError):
        firebase.initialize_firebase(settings.model_copy(update={"firebase_private_key": "test"}))
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    with pytest.raises(RuntimeError):
        firebase.initialize_firebase(settings)
    assert len(calls) == 1


def test_invoker_identity_never_comes_from_user_headers(monkeypatch):
    calls = []
    monkeypatch.setattr(cloud_run, "_metadata_token",
                        lambda origin: calls.append(origin) or "managed.fixture.token")
    browser = {"Authorization": "Bearer user.fixture.token",
               "x-serverless-authorization": "Bearer forged.fixture.token"}
    target = "https://scheduling-probe.run.app"
    assert cloud_run.service_headers(False, "http://127.0.0.1:8002", browser) == {
        "Authorization": "Bearer user.fixture.token",
    }
    assert cloud_run.service_headers(True, target, browser) == {
        "Authorization": "Bearer user.fixture.token",
        "X-Serverless-Authorization": "Bearer managed.fixture.token",
    }
    for origin in (target + "/path", target + ".example.org", "http://127.0.0.1:8002"):
        with pytest.raises(ValueError):
            cloud_run.service_headers(True, origin, browser)
    assert calls == [target]


def test_explicit_ca_retains_verify_full(tmp_path):
    cert = tmp_path / "server-ca.pem"
    cert.write_text("synthetic", encoding="utf-8")
    kwargs = dict(transport="verify-full", environment="production",
                  firebase_project_id="probe", tenant_id="synthetic", application_name="probe")
    dsn = SecretStr("postgresql+psycopg://test@private.invalid:5432/test")
    _, params = postgres_configuration(dsn, tls_root_cert=str(cert), **kwargs)
    assert params["sslmode"] == "verify-full" and params["sslrootcert"] == str(cert)
    with pytest.raises(ValueError):
        postgres_configuration(dsn, tls_root_cert="relative.pem", **kwargs)
