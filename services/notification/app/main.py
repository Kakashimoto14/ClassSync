"""Private transactional email delivery boundary for ClassSync."""

import hmac
import logging
import re
from typing import Literal
from urllib.parse import parse_qs, urlsplit

import httpx
from classync_contracts.email_address import normalize_email
from classync_contracts.models import HealthResponse
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

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
    code: SecretStr = Field(min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email address is invalid")
        return normalized

    @field_validator("code")
    @classmethod
    def six_numeric_digits(cls, value: SecretStr) -> SecretStr:
        if not re.fullmatch(r"[0-9]{6}", value.get_secret_value()):
            raise ValueError("Verification code is invalid")
        return value


class PasswordResetEmail(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    reset_url: SecretStr = Field(min_length=1, max_length=2048)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email address is invalid")
        return normalized

    @field_validator("reset_url")
    @classmethod
    def same_origin_action_url(cls, value: SecretStr) -> SecretStr:
        value_text = value.get_secret_value()
        parsed = urlsplit(value_text)
        origin = urlsplit(settings.classsync_web_url)
        query = parse_qs(parsed.query)
        if (
            parsed.scheme != origin.scheme
            or parsed.netloc != origin.netloc
            or parsed.path != "/auth/action"
            or parsed.fragment
            or set(query) != {"mode", "oobCode"}
            or len(query["oobCode"]) != 1
            or query["mode"] != ["resetPassword"]
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,2048}={0,2}", query["oobCode"][0])
        ):
            raise ValueError("Password reset action link is invalid")
        return value


class EmailAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    mode: Literal["verifyEmail", "resetPassword"]
    action_url: SecretStr = Field(min_length=1, max_length=2048)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email address is invalid")
        return normalized

    @field_validator("action_url")
    @classmethod
    def same_origin_action_url(cls, value: SecretStr, info) -> SecretStr:
        parsed = urlsplit(value.get_secret_value())
        origin = urlsplit(settings.classsync_web_url)
        query = parse_qs(parsed.query)
        mode = info.data.get("mode")
        if (
            parsed.scheme != origin.scheme or parsed.netloc != origin.netloc
            or parsed.path != "/auth/action" or parsed.fragment
            or set(query) != {"mode", "oobCode"} or query.get("mode") != [mode]
            or len(query.get("oobCode", [])) != 1
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,2048}={0,2}", query["oobCode"][0])
        ):
            raise ValueError("Account action link is invalid")
        return value


class RequestDecisionEmail(BaseModel):
    """Teacher-only decision notice; never sent to student roster rows."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=320)
    decision: Literal["approved", "rejected"]
    subject_code: str = Field(min_length=1, max_length=40)
    section: str = Field(min_length=1, max_length=80)
    class_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_range: str = Field(min_length=1, max_length=40)
    from_room: str = Field(min_length=1, max_length=120)
    to_room: str = Field(min_length=1, max_length=120)
    note: str = Field(min_length=3, max_length=1000)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = normalize_email(value)
        if not normalized:
            raise ValueError("Email address is invalid")
        return normalized


settings = Settings()
app = FastAPI(title="ClassSync Notification Service", version="1.0.0")


async def deliver_email(email: str, subject: str, text: str, html: str) -> None:
    if settings.email_provider == "resend":
        if not settings.resend_api_key or not settings.resend_from_email:
            logger.error(
                "email_provider_not_configured",
                extra={"reason_code": "resend_not_configured"},
            )
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
            logger.error(
                "email_provider_not_configured",
                extra={"reason_code": "brevo_not_configured"},
            )
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
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            result = await client.post(endpoint, json=payload, headers=headers)
            result.raise_for_status()
    except httpx.HTTPStatusError as error:
        logger.error(
            "email_provider_rejected_delivery",
            extra={"reason_code": f"{settings.email_provider}_http_{error.response.status_code}"},
        )
        raise HTTPException(503, "Email delivery is unavailable") from error
    except httpx.TimeoutException as error:
        logger.error("email_provider_timeout", extra={"reason_code": "notification_timeout"})
        raise HTTPException(503, "Email delivery is unavailable") from error
    except httpx.HTTPError as error:
        logger.error(
            "email_provider_request_failed",
            extra={"reason_code": "email_provider_unavailable"},
        )
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
    from .email_templates import render_verification_email

    html, text = render_verification_email(
        body.code.get_secret_value(), settings.classsync_web_url
    )
    await deliver_email(body.email, "Your ClassSync verification code", text, html)
    return {"data": {"accepted": True}}


@app.post("/internal/v1/email-action", status_code=202)
async def email_action(
    body: EmailAction,
    x_classsync_service_token: str | None = Header(default=None),
):
    token = settings.notification_service_token
    if token is None or not x_classsync_service_token or not hmac.compare_digest(
        token.get_secret_value(), x_classsync_service_token
    ):
        raise HTTPException(403, "Service authorization required")
    from .email_templates import render_email_action_email

    html, text = render_email_action_email(body.mode, body.action_url.get_secret_value())
    subject = "Verify your ClassSync email" if body.mode == "verifyEmail" \
        else "Reset your ClassSync password"
    await deliver_email(body.email, subject, text, html)
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

    html, text = render_password_reset_email(body.reset_url.get_secret_value())
    await deliver_email(body.email, "Reset your ClassSync password", text, html)
    return {"data": {"accepted": True}}


@app.post("/internal/v1/request-decision-email", status_code=202)
async def request_decision_email(
    body: RequestDecisionEmail,
    x_classsync_service_token: str | None = Header(default=None),
):
    token = settings.notification_service_token
    if token is None or not x_classsync_service_token or not hmac.compare_digest(
        token.get_secret_value(), x_classsync_service_token
    ):
        raise HTTPException(403, "Service authorization required")
    from .email_templates import render_request_decision_email

    html, text = render_request_decision_email(
        decision=body.decision,
        subject_code=body.subject_code,
        section=body.section,
        class_date=body.class_date,
        time_range=body.time_range,
        from_room=body.from_room,
        to_room=body.to_room,
        note=body.note,
        app_url=settings.classsync_web_url,
    )
    subject = (
        "Classroom change approved" if body.decision == "approved"
        else "Classroom change declined"
    )
    await deliver_email(body.email, f"ClassSync · {subject}", text, html)
    return {"data": {"accepted": True}}
