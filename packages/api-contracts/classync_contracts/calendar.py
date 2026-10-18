"""Effective-dated Manila academic calendars. Semester phases never multiply workload."""

from datetime import date
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .scheduling import Contract


class SemesterPhase(Contract):
    model_config = ConfigDict(extra="forbid", strict=False)
    name: Literal["midterm", "final"]
    start: date
    end: date


class CalendarException(Contract):
    model_config = ConfigDict(extra="forbid", strict=False)
    date: date
    reason: str = Field(min_length=1, max_length=200)
    assignment_id: str | None = None
    cancelled: bool = True
    moved_to: date | None = None
    room_id: str | None = None
    start: int | None = Field(default=None, ge=0, le=1410, multiple_of=30)

    @model_validator(mode="after")
    def consistent(self):
        if self.moved_to and (not self.assignment_id or self.cancelled):
            raise ValueError("A move needs an assignment and cancelled=false")
        if (self.room_id or self.start is not None) and not self.moved_to:
            raise ValueError("Room/time changes require a moved occurrence")
        return self


class AcademicCalendar(Contract):
    model_config = ConfigDict(extra="forbid", strict=False)
    academic_year: str = Field(pattern=r"^\d{4}-\d{4}$")
    semester: Literal["first", "second"]
    effective_start: date
    effective_end: date
    timezone: Literal["Asia/Manila"] = "Asia/Manila"
    instructional_days: list[int] = Field(default_factory=lambda: list(range(5)), min_length=1)
    phases: list[SemesterPhase] = Field(default_factory=list, max_length=2)
    exceptions: list[CalendarException] = Field(default_factory=list, max_length=400)
    published_version: str | None = None

    @model_validator(mode="after")
    def ranges(self):
        years = [int(y) for y in self.academic_year.split("-")]
        if years[1] != years[0] + 1 or self.effective_end < self.effective_start:
            raise ValueError("Invalid academic year or effective dates")
        if not years[0] <= self.effective_start.year <= self.effective_end.year <= years[1]:
            raise ValueError("Effective dates must belong to the academic year")
        if (self.effective_end - self.effective_start).days > 370:
            raise ValueError("Calendar is limited to one academic year")
        if len(set(self.instructional_days)) != len(self.instructional_days) or any(
            d not in range(7) for d in self.instructional_days
        ):
            raise ValueError("Use unique instructional weekdays 0–6")
        phases = sorted(self.phases, key=lambda p: p.start)
        if len({p.name for p in phases}) != len(phases):
            raise ValueError("Semester phases must be unique")
        for p in phases:
            if not self.effective_start <= p.start <= p.end <= self.effective_end:
                raise ValueError("Phase dates must fall inside the semester")
        if len(phases) == 2 and phases[0].end >= phases[1].start:
            raise ValueError("Semester phases cannot overlap")
        if len(phases) == 2 and phases[0].name != "midterm":
            raise ValueError("Midterm must precede Final Term")
        keys = [(e.date, e.assignment_id) for e in self.exceptions]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate occurrence exceptions")
        if any(
            not self.effective_start <= e.date <= self.effective_end
            or (e.moved_to and not self.effective_start <= e.moved_to <= self.effective_end)
            for e in self.exceptions
        ):
            raise ValueError("Exceptions must fall within effective dates")
        return self
