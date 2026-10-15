from enum import StrEnum
from pydantic import BaseModel, Field

class UserRole(StrEnum):
    ADMINISTRATOR = "administrator"
    TEACHER = "teacher"
    STUDENT = "student"

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str = "v1"

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str = Field(alias="requestId")

class ApiErrorResponse(BaseModel):
    error: ErrorDetail
