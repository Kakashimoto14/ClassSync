"""Versioned weekly generation contracts. All times are local integer minutes.

These are administrator-supplied constraints, not verified institutional policy.
The contract never accepts a role or a publication instruction.
"""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Window(Contract):
    day: int = Field(ge=0, le=6, description="Monday=0 through Sunday=6")
    start: int = Field(ge=0, lt=1440)
    end: int = Field(gt=0, le=1440)

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start >= self.end or self.start % 30 or self.end % 30:
            raise ValueError("Intervals must be increasing and aligned to 30-minute boundaries")
        return self


class Program(Contract):
    id: str = Field(min_length=1, max_length=80)
    acronym: str = Field(min_length=1)
    name: str
    institute: str
    aliases: list[str] = Field(default_factory=list)
    section_policy: Literal["degree", "custom"] = "degree"
    allowed_year_levels: list[int] | None = None


class Section(Contract):
    id: str = Field(min_length=1, max_length=80)
    program_id: str
    year_level: int | None = Field(default=None, ge=1, le=20)
    section_letter: str | None = Field(default=None, pattern=r"^[A-Z]{1,3}$")
    custom_label: str | None = None
    preferred_days: list[int] = Field(default_factory=list)


class Teacher(Contract):
    id: str = Field(min_length=1, max_length=80)
    name: str
    availability: list[Window] = Field(default_factory=list)
    unavailable: list[Window] = Field(default_factory=list)
    preferred_days: list[int] = Field(default_factory=list)
    max_weekly_minutes: int | None = Field(default=None, ge=0, le=10080, multiple_of=30)
    max_daily_minutes: int | None = Field(default=None, ge=0, le=1440, multiple_of=30)


class Room(Contract):
    id: str = Field(min_length=1, max_length=80)
    name: str
    building: str
    floor: str | None = None
    location: str | None = None
    source: Literal["synthetic", "cdm-provisional", "administrator-supplied"]
    schedulable: bool = False
    condition: Literal["unknown", "operational", "maintenance"] = "unknown"
    room_type: str | None = None
    type_verified: bool = False
    capacity: int | None = Field(default=None, gt=0)
    capacity_verified: bool = False
    equipment: list[str] = Field(default_factory=list)
    equipment_verified: bool = False
    allowed_program_ids: list[str] | None = None
    availability: list[Window] = Field(default_factory=list)
    blocked: list[Window] = Field(default_factory=list)


class SessionPattern(Contract):
    id: str = Field(min_length=1)
    durations: list[int] = Field(min_length=1, max_length=7)
    distinct_days: bool = True

    @model_validator(mode="after")
    def valid_durations(self):
        if any(d <= 0 or d > 1440 or d % 30 for d in self.durations):
            raise ValueError("Session durations must be positive multiples of 30 minutes")
        if self.durations == [90, 90] and not self.distinct_days:
            raise ValueError("The two-90-minute pattern requires distinct teaching days")
        return self


class Offering(Contract):
    id: str = Field(min_length=1, max_length=80)
    subject_id: str = Field(min_length=1)
    subject_name: str = Field(min_length=1)
    section_id: str
    eligible_teacher_ids: list[str] = Field(default_factory=list)
    eligible_room_ids: list[str] = Field(default_factory=list)
    required_weekly_minutes: int = Field(default=180, gt=0, le=10080)
    patterns: list[SessionPattern] = Field(
        default_factory=lambda: [
            SessionPattern(id="one-180", durations=[180]),
            SessionPattern(id="two-90", durations=[90, 90]),
        ],
        min_length=1,
        max_length=5,
    )
    required_room_type: str | None = None
    required_equipment: list[str] = Field(default_factory=list)
    minimum_capacity: int | None = Field(default=None, gt=0)
    allowed_buildings: list[str] | None = None

    @model_validator(mode="after")
    def exact_minutes(self):
        if any(sum(p.durations) != self.required_weekly_minutes for p in self.patterns):
            raise ValueError(
                "Every permitted pattern must allocate exactly required_weekly_minutes"
            )
        if len({p.id for p in self.patterns}) != len(self.patterns):
            raise ValueError("Pattern IDs must be unique within an offering")
        return self


class Enrollment(Contract):
    student_id: str = Field(min_length=1)
    offering_ids: list[str] = Field(min_length=1)


class Assignment(Contract):
    id: str = Field(min_length=1)
    offering_id: str
    day: int = Field(ge=0, le=6)
    start: int = Field(ge=0, lt=1440)
    end: int = Field(gt=0, le=1440)
    room_id: str
    teacher_id: str
    section_id: str
    subject_id: str

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start >= self.end or self.start % 30 or self.end % 30:
            raise ValueError("Assignments must use increasing, 30-minute aligned intervals")
        return self


class ObjectiveWeights(Contract):
    idle_gaps: int = Field(default=2, ge=0, le=100)
    daily_balance: int = Field(default=1, ge=0, le=100)
    preferences: int = Field(default=3, ge=0, le=100)
    building_changes: int = Field(default=2, ge=0, le=100)
    disruption: int = Field(default=5, ge=0, le=100)
    room_balance: int = Field(default=1, ge=0, le=100)


class SolverOptions(Contract):
    time_limit_seconds: float = Field(default=5.0, gt=0, le=30)
    seed: int = Field(default=42, ge=0, le=2147483647)
    weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)


class GenerationInput(Contract):
    contract_version: Literal["v1"] = "v1"
    period_id: str = Field(min_length=1, max_length=120)
    data_version: str = Field(min_length=1, max_length=120)
    scope_description: str = Field(min_length=1, max_length=500)
    all_intended_offerings_supplied: bool = False
    synthetic: bool = False
    operating_windows: list[Window] = Field(default_factory=list, max_length=70)
    transition_buffer_minutes: int = Field(default=0, ge=0, le=120, multiple_of=30)
    programs: list[Program] = Field(default_factory=list, max_length=50)
    sections: list[Section] = Field(default_factory=list, max_length=500)
    teachers: list[Teacher] = Field(default_factory=list, max_length=500)
    rooms: list[Room] = Field(default_factory=list, max_length=200)
    offerings: list[Offering] = Field(default_factory=list, max_length=1000)
    enrollments: list[Enrollment] = Field(default_factory=list, max_length=10000)
    locked_assignments: list[Assignment] = Field(default_factory=list, max_length=7000)
    previous_assignments: list[Assignment] = Field(default_factory=list, max_length=7000)
    options: SolverOptions = Field(default_factory=SolverOptions)


class Diagnostic(Contract):
    code: str
    message: str
    offering_id: str | None = None
    assignment_ids: list[str] = Field(default_factory=list)


class Coverage(Contract):
    offering_id: str
    required_minutes: int
    allocated_minutes: int


class ValidationResult(Contract):
    valid: bool
    hard_conflict_count: int
    conflicts: list[Diagnostic]
    coverage: list[Coverage]


class ValidationInput(Contract):
    inputs: GenerationInput
    assignments: list[Assignment] = Field(max_length=7000)


class ReadinessResult(Contract):
    inputs: GenerationInput
    diagnostics: list[Diagnostic]


class RunMetadata(Contract):
    solver: str = "OR-Tools CP-SAT"
    solver_version: str
    seed: int
    wall_time_seconds: float
    time_limit_seconds: float
    objective: float | None = None
    best_bound: float | None = None


class GenerationResult(Contract):
    contract_version: Literal["v1"] = "v1"
    run_id: str
    period_id: str
    input_hash: str
    data_version: str
    solver_status: Literal[
        "optimal",
        "feasible",
        "infeasible",
        "invalid_input",
        "invalid_model",
        "unknown",
        "validation_failed",
    ]
    result_kind: Literal["generated_preview"] = "generated_preview"
    persisted: Literal[False] = False
    assignments: list[Assignment]
    total_offerings_requested: int
    total_offerings_scheduled: int
    coverage: list[Coverage]
    hard_conflict_count: int | None
    diagnostics: list[Diagnostic]
    validation: ValidationResult | None
    metadata: RunMetadata


class SaveDraftRequest(Contract):
    run_id: str = Field(min_length=1, max_length=100)
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    title: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=100)

    @model_validator(mode="after")
    def meaningful_title(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Supply a draft title")
        return self


class DraftSummary(Contract):
    schema_version: Literal[1] = 1
    id: str
    title: str
    period_id: str
    created_at: str
    creator: str
    status: Literal["draft"] = "draft"
    published: Literal[False] = False
    source: Literal["synthetic-preview", "development-entered", "institutional"]
    run_id: str
    input_hash: str
    data_version: str
    solver_status: Literal["feasible", "optimal"]
    session_count: int
    offerings_requested: int
    offerings_scheduled: int
    required_minutes: int
    allocated_minutes: int
    hard_conflict_count: Literal[0] = 0
    validated: Literal[True] = True


class DraftDetail(DraftSummary):
    input_snapshot: GenerationInput
    generation_result: GenerationResult
    validation: ValidationResult


class DraftList(Contract):
    drafts: list[DraftSummary]
    limit: int
    offset: int
    has_more: bool


def scheduling_input_hash(inputs: GenerationInput):
    """Preserve S1 hashes when optional S2B workload constraints are absent."""
    value = inputs.model_dump(mode="json")
    for teacher in value["teachers"]:
        for key in ("max_weekly_minutes", "max_daily_minutes"):
            if teacher.get(key) is None:
                teacher.pop(key, None)
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
