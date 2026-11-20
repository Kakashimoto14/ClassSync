"""Private transactional email delivery boundary for ClassSync."""

import hmac
import re
from typing import Literal
from urllib.parse import parse_qs, urlsplit

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


class PasswordResetEmail(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    reset_url: str = Field(min_length=1, max_length=2048)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Student email address is invalid")
        return value

    @field_validator("reset_url")
    @classmethod
    def same_origin_action_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        origin = urlsplit(settings.classsync_web_url)
        query = parse_qs(parsed.query)
        if (
            parsed.scheme != origin.scheme
            or parsed.netloc != origin.netloc
            or parsed.path != "/auth/reset-password"
            or parsed.fragment
            or set(query) != {"oobCode"}
            or len(query["oobCode"]) != 1
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,2048}={0,2}", query["oobCode"][0])
        ):
            raise ValueError("Password reset action link is invalid")
        return value


settings = Settings()
app = FastAPI(title="ClassSync Notification Service", version="1.0.0")


async def deliver_email(email: str, subject: str, text: str, html: str) -> None:
    if settings.email_provider == "resend":
        if not settings.resend_api_key or not settings.resend_from_email:
            raise HTTPException(503, "Email delivery is unavailable")
        endpoint = "https://api.resend.com/emails"
        payload = {
            "from": settings.resend_from_email,
            "to": [email],
            "subject": subject,
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
            "to": [{"email": email}],
            "subject": subject,
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
            result = await client.post(endpoint, json=payload, headers=headers)
            result.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(503, "Email delivery is unavailable") from error


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
    await deliver_email(body.email, "Your ClassSync verification code", text, html)
    return {"data": {"accepted": True}}


@app.post("/internal/v1/password-reset-email", status_code=202)
async def password_reset_email(
    body: PasswordResetEmail,
    x_classsync_service_token: str | None = Header(default=None),
):
    token = settings.notification_service_token
    if token is None or not x_classsync_service_token or not hmac.compare_digest(
        token.get_secret_value(), x_classsync_service_token
    ):
        raise HTTPException(403, "Service authorization required")
    from .email_templates import render_password_reset_email

    html, text = render_password_reset_email(body.reset_url)
    await deliver_email(body.email, "Reset your ClassSync password", text, html)
    return {"data": {"accepted": True}}
