"""Private transactional email delivery boundary for ClassSync."""

import hmac
import re

import httpx
from classync_contracts.models import HealthResponse
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    classsync_env: str = "production"
    notification_service_token: SecretStr | None = None
    resend_api_key: SecretStr | None = None
    resend_from_email: str = ""


class VerificationEmail(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


settings = Settings()
app = FastAPI(title="ClassSync Notification Service", version="1.0.0")


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    return HealthResponse(service="notification")


@app.post("/internal/v1/verification-email", status_code=202)
async def verification_email(
    body: VerificationEmail,
    x_classsync_service_token: str | None = Header(default=None),
):
    token = settings.notification_service_token
    if token is None or not x_classsync_service_token or not hmac.compare_digest(
        token.get_secret_value(), x_classsync_service_token
    ):
        raise HTTPException(403, "Service authorization required")
    if not re.fullmatch(r"[a-z]+(?:\.[a-z]+)*@student\.pnm\.edu\.ph", body.email):
        raise HTTPException(422, "Student email address is invalid")
    if not settings.resend_api_key or not settings.resend_from_email:
        raise HTTPException(503, "Email delivery is unavailable")
    payload = {
        "from": settings.resend_from_email,
        "to": [body.email],
        "subject": "Your ClassSync verification code",
        "text": (
            f"Your ClassSync verification code is {body.code}. "
            "It expires in 5 minutes and can only be used once."
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            result = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
                         "Content-Type": "application/json"},
            )
            result.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(503, "Email delivery is unavailable") from error
    return {"data": {"accepted": True}}
