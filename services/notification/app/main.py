"""Private transactional email delivery boundary for ClassSync."""

import hmac
import re
from typing import Literal
from urllib.parse import urlsplit

import httpx
from classync_contracts.models import HealthResponse
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    classsync_env: str = "production"
    email_provider: Literal["resend", "brevo"] = "resend"
    notification_service_token: SecretStr | None = None
    resend_api_key: SecretStr | None = None
    resend_from_email: str = ""
    brevo_api_key: SecretStr | None = None
    brevo_sender_email: str = ""
    brevo_sender_name: str = Field(default="ClassSync", min_length=1, max_length=80)
    classsync_web_url: str = "https://class-sync-bhiv.vercel.app"

    @field_validator("classsync_web_url")
    @classmethod
    def validate_web_origin(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"})
        ):
            raise ValueError("Use an HTTPS application origin")
        return f"{parsed.scheme}://{parsed.netloc}"


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
    from .email_templates import render_verification_email

    html, text = render_verification_email(body.code, settings.classsync_web_url)
    if settings.email_provider == "resend":
        if not settings.resend_api_key or not settings.resend_from_email:
            raise HTTPException(503, "Email delivery is unavailable")
        endpoint = "https://api.resend.com/emails"
        payload = {
            "from": settings.resend_from_email,
            "to": [body.email],
            "subject": "Your ClassSync verification code",
            "text": text,
            "html": html,
        }
        headers = {
            "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
    else:
        if not settings.brevo_api_key or not settings.brevo_sender_email:
            raise HTTPException(503, "Email delivery is unavailable")
        endpoint = "https://api.brevo.com/v3/smtp/email"
        payload = {
            "sender": {"name": settings.brevo_sender_name, "email": settings.brevo_sender_email},
            "to": [{"email": body.email}],
            "subject": "Your ClassSync verification code",
            "textContent": text,
            "htmlContent": html,
        }
        headers = {
            "api-key": settings.brevo_api_key.get_secret_value(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    try:
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            result = await client.post(
                endpoint,
                json=payload,
                headers=headers,
            )
            result.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(503, "Email delivery is unavailable") from error
    return {"data": {"accepted": True}}
