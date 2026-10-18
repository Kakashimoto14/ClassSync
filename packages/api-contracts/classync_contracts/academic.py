"""S2B typed period-scoped academic records. Catalogs are not curricula."""

from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, model_validator

from .scheduling import (
    Assignment,
    Contract,
    Enrollment,
    GenerationInput,
    Program,
    Room,
    Section,
    SessionPattern,
    SolverOptions,
    Teacher,
    Window,
)


class Identity(Contract):
    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=80)
    active: bool = True


class AcademicProgram(Program):
    kind: Literal["programs"] = "programs"
    active: bool = True


class AcademicSubject(Identity):
    kind: Literal["subjects"] = "subjects"
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    program_ids: list[str] = Field(default_factory=list)
    required_weekly_minutes: int | None = Field(default=180, gt=0, le=10080, multiple_of=30)
    patterns: list[SessionPattern] = Field(
        default_factory=lambda: [
            SessionPattern(id="one-180", durations=[180]),
            SessionPattern(id="two-90", durations=[90, 90]),
        ],
        max_length=5,
    )
    required_room_type: str | None = None
    required_equipment: list[str] = Field(default_factory=list)
    minimum_capacity: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def exact_patterns(self):
        if self.required_weekly_minutes is not None and any(
            sum(p.durations) != self.required_weekly_minutes for p in self.patterns
        ):
            raise ValueError("Every subject pattern must total required weekly contact minutes")
        if len({p.id for p in self.patterns}) != len(self.patterns):
            raise ValueError("Pattern IDs must be unique")
        return self


class AcademicSection(Section):
    kind: Literal["sections"] = "sections"
    active: bool = True
    period_id: str
    population: int | None = Field(default=None, gt=0)
    population_verified: bool = False

    @model_validator(mode="after")
    def known_population(self):
        if self.population_verified and self.population is None:
            raise ValueError("Enter the verified section population")
        return self


class AcademicFaculty(Teacher):
    kind: Literal["faculty"] = "faculty"
    active: bool = True
    subject_ids: list[str] = Field(default_factory=list)
    institutional_id: str | None = None


class AcademicResource(Room):
    kind: Literal["resources"] = "resources"
    active: bool = True
    source: Literal["cdm-provisional", "administrator-supplied"] = "administrator-supplied"
    verification_note: str = Field(default="", max_length=1000)
    alias: str | None = None
    alias_unconfirmed: bool = False

    @model_validator(mode="after")
    def provenance(self):
        if (
            self.schedulable
            or self.condition != "unknown"
            or self.type_verified
            or self.capacity_verified
            or self.equipment_verified
        ) and len(self.verification_note.strip()) < 5:
            raise ValueError(
                "Supply a verification source/note for operational or verified resource metadata"
            )
        if self.capacity_verified and self.capacity is None:
            raise ValueError("Enter the verified capacity")
        if self.type_verified and not self.room_type:
            raise ValueError("Enter the verified room type")
        return self


class AcademicOffering(Identity):
    kind: Literal["offerings"] = "offerings"
    subject_id: str
    section_id: str
    teacher_ids: list[str] = Field(default_factory=list)
    room_ids: list[str] = Field(default_factory=list)
    weekly_minutes_override: int | None = Field(default=None, gt=0, le=10080, multiple_of=30)
    patterns_override: list[SessionPattern] | None = None
    required_room_type: str | None = None
    required_equipment: list[str] = Field(default_factory=list)
    minimum_capacity: int | None = Field(default=None, gt=0)
    allowed_buildings: list[str] | None = None


class AcademicConstraints(Contract):
    kind: Literal["constraints"] = "constraints"
    id: Literal["rules"] = "rules"
    operating_windows: list[Window] = Field(default_factory=list, max_length=70)
    transition_buffer_minutes: int = Field(default=0, ge=0, le=120, multiple_of=30)
    locked_assignments: list[Assignment] = Field(default_factory=list)
    enrollments: list[Enrollment] = Field(default_factory=list)
    options: SolverOptions = Field(default_factory=SolverOptions)
    all_intended_offerings_supplied: bool = False


AcademicRecord = Annotated[
    AcademicProgram
    | AcademicSubject
    | AcademicSection
    | AcademicFaculty
    | AcademicResource
    | AcademicOffering
    | AcademicConstraints,
    Field(discriminator="kind"),
]


class RecordWrite(Contract):
    expected_revision: int = Field(ge=0)
    record: AcademicRecord


class RecordEnvelope(Contract):
    revision: int
    updated_at: str
    updated_by: str
    record: AcademicRecord


class PeriodCreate(Contract):
    title: str = Field(min_length=1, max_length=160)
    include_cdm_catalog: bool = True

    @model_validator(mode="after")
    def meaningful_title(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("Enter an academic period title")
        return self


class AcademicPeriod(Contract):
    id: str
    title: str
    revision: int
    created_at: str
    source: Literal["development-entered", "institutional"]


class AcademicPeriodList(Contract):
    periods: list[AcademicPeriod]


class AcademicSnapshot(Contract):
    contract_version: Literal["v1"] = "v1"
    period: AcademicPeriod
    records: list[RecordEnvelope]


class ReadinessIssue(Contract):
    severity: Literal["blocking", "warning"]
    code: str
    message: str
    record_id: str | None = None


class AcademicReadiness(Contract):
    period: AcademicPeriod
    issues: list[ReadinessIssue]
    ready: bool
    programs: int
    subjects: int
    sections: int
    faculty: int
    offerings: int
    eligible_resources: int
    inputs: GenerationInput | None


class AcademicGenerationRequest(Contract):
    expected_revision: int = Field(ge=1)
