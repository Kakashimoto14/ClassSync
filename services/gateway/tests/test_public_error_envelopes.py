from fastapi.testclient import TestClient

from services.gateway.app import main


def test_public_error_filter_preserves_safe_identity_message_and_masks_internals():
    safe = (
        "Unable to sign in wth Google. Use the email registered in your student record. "
        "If you need assistance, contact the Registrar"
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
