import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from services.gateway.app import main


def test_public_error_filter_preserves_safe_identity_message_and_masks_internals():
    safe = (
        "No matching active student record was found. "
        "Scan your Registration Form or contact the Registrar."
    )
    assert main.safe_public_error_message(safe) == safe
    assert main.safe_public_error_message(
        "relation classsync_identity.memberships does not exist"
    ) == "The request could not be completed. Please try again."
    assert main.safe_public_error_message({"detail": "raw database JSON"}) == (
        "The request could not be completed. Please try again."
    )


def test_request_validation_envelope_does_not_echo_raw_request_or_schema_details():
    response = TestClient(main.app).post(
        "/api/v1/auth/verify-turnstile",
        json={"token": "sentinel-token", "classsync_identity": "private"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["message"] == (
        "The request could not be validated. Check the provided fields."
    )
    assert "sentinel-token" not in response.text
    assert "classsync_identity" not in response.text
    assert body["error"]["requestId"]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"error": {"code": "bad_request", "message": "Choose an eligible room."}},
            "Choose an eligible room.",
        ),
        (
            {
                "error": {
                    "code": "database_error",
                    "message": "relation classsync_identity.memberships does not exist",
                }
            },
            "The request could not be completed. Please try again.",
        ),
        (
            {"error": "unrecognized downstream format"},
            "The request could not be completed. Please try again.",
        ),
        (
            ["unrecognized downstream payload"],
            "The request could not be completed. Please try again.",
        ),
    ],
)
def test_service_proxy_sanitizes_downstream_errors(payload, expected, monkeypatch):
    class UpstreamResponse:
        status_code = 503
        is_error = True

        def json(self):
            return payload

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, *_args, **_kwargs):
            return UpstreamResponse()

    async def body():
        return b"{}"

    monkeypatch.setattr(
        main,
        "settings",
        SimpleNamespace(
            scheduling_service_url="http://scheduling.internal",
            cloud_run_iam_enabled=False,
        ),
    )
    monkeypatch.setattr(main, "service_headers", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **_kwargs: Client())
    request = SimpleNamespace(
        body=body,
        method="POST",
        query_params={},
        headers={},
        state=SimpleNamespace(request_id="request-1"),
    )

    response = asyncio.run(main.service_proxy("scheduling", "/api/v1/scheduling/generate", request))

    assert response.status_code == 503
    assert json.loads(response.body)["error"]["message"] == expected
