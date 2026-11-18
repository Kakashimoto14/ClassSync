"""Non-authoritative course demonstrations; no academic, identity or schedule fields."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calendar_view: Literal["day", "week", "month"] = "week"
    compact: bool = Field(default=False, strict=True)


class PreferencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(strict=True, ge=1)
    expected_generation: UUID
    calendar_view: Literal["day", "week", "month"] | None = None
    compact: bool | None = Field(default=None, strict=True)


class DemoUpload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=8000)
    purpose: Literal["synthetic-course-demo"]


class AdvisoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Literal["study-planning", "classroom-request-etiquette"]
