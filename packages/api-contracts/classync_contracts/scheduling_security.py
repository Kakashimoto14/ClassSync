"""Scheduling privilege never comes from the browser's role-preview selection."""

from fastapi import HTTPException, Request

from .firebase import FirebaseSettings
from .models import UserRole
from .request_authorization import request_identity


class SchedulingSecuritySettings(FirebaseSettings):
    classsync_env: str = "production"
    enable_scheduling_sandbox: bool = False
    institutional_tenant_id: str | None = None
    enable_test_identity_adapters: bool = False


def require_sandbox(settings):
    if settings.classsync_env != "development" or not settings.enable_scheduling_sandbox:
        raise HTTPException(403, "Scheduling sandbox is disabled outside explicit development mode")


def require_administrator(request: Request, settings):
    return request_identity(request, settings, UserRole.ADMINISTRATOR)


def require_identity(request: Request, settings):
    return request_identity(request, settings)
