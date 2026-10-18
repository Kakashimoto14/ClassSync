"""Publication commands carry concurrency expectations, never client validation results."""

from typing import Literal

from pydantic import Field

from .calendar import AcademicCalendar
from .scheduling import Contract


class PublicationCommand(Contract):
    draft_id: str = Field(min_length=1, max_length=80)
    source: Literal["administrator", "academic-sandbox"] = "administrator"
    dataset: Literal["institutional", "synthetic"] = "institutional"
    expected_version: int = Field(ge=0)
    expected_academic_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=120)
    calendar: AcademicCalendar


class PublicationReview(Contract):
    draft_id: str
    source: Literal["administrator", "academic-sandbox"] = "administrator"
    dataset: Literal["institutional", "synthetic"] = "institutional"
    calendar: AcademicCalendar


class RoomRestriction(Contract):
    id: str = Field(min_length=1, max_length=80)
    room_id: str = Field(min_length=1, max_length=80)
    dataset: Literal["institutional", "synthetic"] = "institutional"
    starts_at: str
    ends_at: str
    kind: Literal["operational", "reservation"]
    reason: str = Field(min_length=1, max_length=200)
    expected_revision: int = Field(ge=0)
