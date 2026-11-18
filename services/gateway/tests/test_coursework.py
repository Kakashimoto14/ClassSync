"""Offline contract/authorization tests. These do not qualify any cloud integration."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from services.gateway.app import coursework, coursework_cloud, main
from services.gateway.app.coursework_cloud import GoogleCoursework, owner_key
from services.gateway.app.coursework_schema import PreferencePatch

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}


@pytest.fixture
def client(monkeypatch, identity_adapters):
    identity_adapters(main, role="student", uid="synthetic-course-" + uuid4().hex)
    for name, value in {
        "firebase_project_id": "demo-classsync-course",
        "course_cloud_enabled": True,
        "course_storage_bucket": "synthetic-private-bucket",
        "course_gemini_model": "synthetic-model",
        "gemini_api_key": SecretStr("synthetic-key"),
    }.items():
        monkeypatch.setattr(main.settings, name, value)
    return TestClient(main.app)


def test_authentication_precedes_optional_provider_and_disabled_is_not_success(client, monkeypatch):
    provider = Mock()
    monkeypatch.setattr(coursework, "GoogleCoursework", provider)
    assert client.get("/api/v1/coursework/preferences").status_code == 401
    monkeypatch.setattr(main.settings, "course_cloud_enabled", False)
    response = client.get("/api/v1/coursework/preferences", headers=HEADERS)
    assert response.status_code == 503 and response.headers["cache-control"] == "no-store"
    provider.assert_not_called()


@pytest.mark.parametrize(
    "path,body",
    [
        ("preferences", {"role": "administrator"}),
        ("preferences", {"student_id": "other", "calendar_view": "week"}),
        ("advisory", {"topic": "approve-enrollment"}),
        ("advisory", {"topic": "study-planning", "prompt": "private academic data"}),
        ("files", {"text": "x", "purpose": "registration-form"}),
    ],
)
def test_untrusted_authority_and_sensitive_workflows_are_not_provider_inputs(
    client, monkeypatch, path, body
):
    provider = Mock()
    monkeypatch.setattr(coursework, "GoogleCoursework", provider)
    assert client.post("/api/v1/coursework/" + path, headers=HEADERS, json=body).status_code == 422
    provider.assert_not_called()


def test_actual_body_limit_precedes_provider_and_not_just_content_length(client, monkeypatch):
    provider = Mock()
    monkeypatch.setattr(coursework, "GoogleCoursework", provider)
    response = client.post(
        "/api/v1/coursework/files",
        headers={**HEADERS, "Content-Type": "application/json"},
        content=(b" " * 34000) + b"{}",
    )
    assert response.status_code == 413
    provider.assert_not_called()


def test_owner_namespace_and_uuid_download_are_server_controlled(
    client, monkeypatch, identity_adapters
):
    provider = Mock()
    provider.preference.return_value = {
        "preferences": {"calendar_view": "week", "compact": False},
        "revision": 1,
        "generation": str(uuid4()),
    }
    provider.file.return_value = b"Synthetic course file"
    monkeypatch.setattr(coursework, "GoogleCoursework", lambda _: provider)
    assert client.get("/api/v1/coursework/preferences", headers=HEADERS).status_code == 200
    first_owner = provider.preference.call_args.args[0]
    identity_adapters(main, role="teacher", uid="different-synthetic-user")
    monkeypatch.setattr(main.settings, "firebase_project_id", "demo-classsync-course")
    assert client.get("/api/v1/coursework/preferences", headers=HEADERS).status_code == 200
    assert provider.preference.call_args.args[0] != first_owner
    assert owner_key("project-a", "tenant-a", "uid") != owner_key("project-b", "tenant-a", "uid")
    assert owner_key("project-a", "tenant-a", "uid") != owner_key("project-a", "tenant-b", "uid")
    response = client.get("/api/v1/coursework/files/" + str(uuid4()), headers=HEADERS)
    assert response.status_code == 200 and response.content == b"Synthetic course file"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith('attachment; filename="')
    assert client.get("/api/v1/coursework/files/not-a-uuid", headers=HEADERS).status_code == 422


def test_course_provider_error_is_private_and_never_becomes_success(client, monkeypatch):
    provider = Mock()
    provider.preference.side_effect = RuntimeError("PRIVATE-CREDENTIAL-AND-CONTENT")
    monkeypatch.setattr(coursework, "GoogleCoursework", lambda _: provider)
    response = client.get("/api/v1/coursework/preferences", headers=HEADERS)
    assert response.status_code == 503
    assert "PRIVATE" not in response.text


def test_advisory_daily_instance_limit_precedes_provider(client, monkeypatch):
    provider = Mock()
    provider.advisory.return_value = {"text": "Synthetic advisory", "advisory_only": True}
    monkeypatch.setattr(coursework, "GoogleCoursework", lambda _: provider)
    for _ in range(6):
        assert (
            client.post(
                "/api/v1/coursework/advisory", headers=HEADERS, json={"topic": "study-planning"}
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/api/v1/coursework/advisory", headers=HEADERS, json={"topic": "study-planning"}
        ).status_code
        == 429
    )
    assert provider.advisory.call_count == 6


def test_firestore_generation_prevents_old_client_overwriting_recreated_preferences(monkeypatch):
    old_generation, generation = uuid4(), uuid4()
    document, cloud = Mock(), Mock()
    cloud.collection.return_value.document.return_value = document
    document.get.return_value = SimpleNamespace(
        exists=True,
        update_time="synthetic-update-time",
        to_dict=lambda: {
            "preferences": {"calendar_view": "week", "compact": False},
            "revision": 1,
            "generation": str(generation),
        },
    )
    provider = GoogleCoursework(SimpleNamespace())
    monkeypatch.setattr(provider, "preferences", lambda: cloud)
    patch = PreferencePatch(expected_revision=1, expected_generation=old_generation, compact=True)
    with pytest.raises(HTTPException) as rejected:
        provider.preference("owned-document", "update", patch, 1, old_generation)
    assert rejected.value.status_code == 409
    document.update.assert_not_called()
    patch.expected_generation = generation
    result = provider.preference("owned-document", "update", patch, 1, generation)
    assert result["revision"] == 2 and result["generation"] == str(generation)
    assert document.update.call_args.kwargs["timeout"] == 5
    assert document.update.call_args.kwargs["retry"] is None
    assert document.update.call_args.kwargs["option"] is not None
    assert cloud.collection.call_args.args == ("classsync_course_preferences",)


@pytest.mark.parametrize("public,uniform", [("inherited", True), ("enforced", False)])
def test_storage_refuses_unqualified_bucket_before_upload(public, uniform):
    client = Mock()
    client.bucket.return_value.iam_configuration = SimpleNamespace(
        public_access_prevention=public, uniform_bucket_level_access_enabled=uniform
    )
    provider = GoogleCoursework(SimpleNamespace(course_storage_bucket="synthetic-private-bucket"))
    with pytest.raises(HTTPException) as denied:
        provider.private_bucket(client)
    assert denied.value.status_code == 503
    client.bucket.return_value.blob.assert_not_called()


def test_advisory_absolute_deadline_cancels_slow_chunks(monkeypatch):
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(1000):
                await asyncio.sleep(0.01)
                yield b" "

    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowStream()))
    monkeypatch.setattr(
        coursework_cloud.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=transport, **kwargs),
    )
    monkeypatch.setattr(coursework_cloud, "ADVISORY_DEADLINE_SECONDS", 0.04)
    provider = GoogleCoursework(
        SimpleNamespace(
            course_gemini_model="synthetic-model", gemini_api_key=SecretStr("synthetic-key")
        )
    )
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        provider.advisory("study-planning")
    assert time.monotonic() - started < 1


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.invalid",
        "http://example.invalid",
        "https://user:password@example.invalid",
        "https://example.invalid/path",
    ],
)
def test_cors_rejects_non_origin_and_wildcard_configuration(origin):
    with pytest.raises(ValidationError):
        main.Settings(_env_file=None, cors_origins=[origin])


def test_cors_allowed_origins_environment_name_is_supported(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", '["https://class-sync-bhiv.vercel.app"]'
    )
    settings = main.Settings(_env_file=None)
    assert settings.cors_origins == ["https://class-sync-bhiv.vercel.app"]


def test_coursework_openapi_has_all_verbs_and_validated_inputs():
    schema = main.app.openapi()
    assert set(schema["paths"]["/api/v1/coursework/preferences"]) == {
        "get",
        "post",
        "patch",
        "delete",
    }
    assert "requestBody" in schema["paths"]["/api/v1/coursework/advisory"]["post"]
    identifiers = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if "operationId" in operation
    ]
    assert len(identifiers) == len(set(identifiers))
    assert schema["components"]["securitySchemes"]["FirebaseBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/api/v1/coursework/preferences"]["get"]["security"]
