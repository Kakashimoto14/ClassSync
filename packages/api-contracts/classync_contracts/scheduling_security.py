"""Scheduling privilege never comes from the browser's role-preview selection."""

from fastapi import HTTPException, Request
from firebase_admin import auth

from .firebase import FirebaseSettings, initialize_firebase


class SchedulingSecuritySettings(FirebaseSettings):
    classsync_env: str = "production"
    enable_scheduling_sandbox: bool = False


def require_sandbox(settings):
    if settings.classsync_env != "development" or not settings.enable_scheduling_sandbox:
        raise HTTPException(403, "Scheduling sandbox is disabled outside explicit development mode")


def require_administrator(request: Request, settings):
    claims = require_identity(request, settings)
    if claims.get("role") != "administrator":
        raise HTTPException(403, "Administrator authorization is required")
    return claims


def require_identity(request: Request, settings):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "A verified Administrator token is required")
    try:
        initialize_firebase(settings)
        claims = auth.verify_id_token(header.removeprefix("Bearer "), check_revoked=True)
    except Exception as error:
        raise HTTPException(401, "Invalid authentication token") from error
    if not claims.get("uid") or claims.get("role") not in {"administrator", "teacher", "student"}:
        raise HTTPException(403, "A verified role and identity are required")
    return claims
