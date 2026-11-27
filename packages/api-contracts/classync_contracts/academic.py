"""S2B typed period-scoped academic records. Catalogs are not curricula."""

from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_serializer, model_validator

from .calendar import AcademicCalendar
from .email_address import normalize_email
from .scheduling import (
    ActivityType,
    Assignment,
    Contract,
    DailyShapeRules,
    Enrollment,
    GenerationInput,
    PatternPolicy,
    Program,
    Room,
    Section,
    SessionPattern,
    SolverOptions,
    Teacher,
    Window,
    omit_none,
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
    curriculum_version_id: str | None = None
    curriculum_course_id: str | None = None
    curriculum_review_verified: bool = False
    curriculum_review_reference: str | None = Field(default=None, max_length=160)
    contact_minutes_verified: bool = False
    contact_minutes_reference: str | None = Field(default=None, max_length=160)
    year_level: int | None = Field(default=None, ge=1, le=4)
    semester: Literal["first", "second"] | None = None
    provenance: Literal["synthetic", "administrator-entered", "source-supplied"] = (
        "administrator-entered"
    )
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
    lec_hours: int | None = Field(default=None, ge=0, le=12)
    lab_hours: int | None = Field(default=None, ge=0, le=12)
    units: int | None = Field(default=None, ge=0, le=30)
    pattern_policy: PatternPolicy | None = None

    @model_serializer(mode="wrap")
    def omit_absent_policy(self, handler):
        return omit_none(handler(self), "pattern_policy")

    @model_validator(mode="after")
    def exact_patterns(self):
        if self.curriculum_version_id:
            if "required_weekly_minutes" not in self.model_fields_set:
                self.required_weekly_minutes = None
            if "patterns" not in self.model_fields_set:
                self.patterns = []
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
    entry_cohort_year: int | None = Field(default=None, ge=1900, le=2200)
    curriculum_version_id: str | None = None
    cohort_assignment_verified: bool = False
    identity_verified: bool = False
    population: int | None = Field(default=None, gt=0)
    capacity: int | None = Field(default=None, gt=0, le=500)
    population_verified: bool = False
    verification_reference: str | None = Field(default=None, max_length=160)

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
    eligibility_verified: bool = False
    availability_verified: bool = False
    workload_verified: bool = False
    verification_reference: str | None = Field(default=None, max_length=160)
    weekly_unit_cap: int | None = Field(default=None, ge=1, le=40)


class AcademicResource(Room):
    kind: Literal["resources"] = "resources"
    active: bool = True
    source: Literal["cdm-provisional", "administrator-supplied", "synthetic"] = (
        "administrator-supplied"
    )
    verification_note: str = Field(default="", max_length=1000)
    availability_verified: bool = False
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
    activity_type: ActivityType = ActivityType.ACADEMIC_INSTRUCTION
    teacher_ids: list[str] = Field(default_factory=list)
    room_ids: list[str] = Field(default_factory=list)
    weekly_minutes_override: int | None = Field(default=None, gt=0, le=10080, multiple_of=30)
    patterns_override: list[SessionPattern] | None = None
    pattern_policy: PatternPolicy | None = None
    required_room_type: str | None = None
    required_equipment: list[str] = Field(default_factory=list)
    minimum_capacity: int | None = Field(default=None, gt=0)

    @field_validator("activity_type", mode="before")
    @classmethod
    def validate_activity_type(cls, value):
        if isinstance(value, str) and not isinstance(value, ActivityType):
            try:
                return ActivityType(value)
            except ValueError:
                return value
        return value

    allowed_buildings: list[str] | None = None
    term_offering_verified: bool = False
    override_requirements_verified: bool = False
    verification_reference: str | None = Field(default=None, max_length=160)

    @model_serializer(mode="wrap")
    def omit_absent_policy(self, handler):
        return omit_none(handler(self), "pattern_policy")


class AcademicConstraints(Contract):
    kind: Literal["constraints"] = "constraints"
    id: Literal["rules"] = "rules"
    operating_windows: list[Window] = Field(default_factory=list, max_length=70)
    transition_buffer_minutes: int = Field(default=0, ge=0, le=120)
    locked_assignments: list[Assignment] = Field(default_factory=list)
    enrollments: list[Enrollment] = Field(default_factory=list)
    options: SolverOptions = Field(default_factory=SolverOptions)
    all_intended_offerings_supplied: bool = False
    operating_windows_verified: bool = False
    shared_scope_verified: bool = False
    shared_scope_reference: str | None = Field(default=None, max_length=160)
    verification_reference: str | None = Field(default=None, max_length=160)
    daily_shape: DailyShapeRules | None = None
    pattern_policy_180: PatternPolicy | None = None

    @model_serializer(mode="wrap")
    def omit_absent_rules(self, handler):
        return omit_none(handler(self), "daily_shape", "pattern_policy_180")


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


class RosterStudentWrite(Contract):
    expected_period_revision: int = Field(ge=1)
    student_id: str = Field(pattern=r"^[0-9]{2}-[0-9]{5}$")
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    year_level: int = Field(ge=1, le=4)
    section_id: str = Field(min_length=1, max_length=80)
    enrollment_status: Literal["active", "inactive", "unverified"] = "unverified"

    @field_validator("full_name", "section_id")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("Enter a value")
        return result

    @field_validator("email")
    @classmethod
    def normalize_roster_email(cls, value: str) -> str:
        normalized = normalize_email(value)
        if normalized is None:
            raise ValueError("Enter a valid email address")
        return normalized


class RosterBulkStatus(Contract):
    expected_period_revision: int = Field(ge=1)
    student_ids: list[Annotated[str, Field(pattern=r"^[0-9]{2}-[0-9]{5}$")]] = Field(
        min_length=1, max_length=500
    )
    enrollment_status: Literal["active", "inactive", "unverified"]

    @field_validator("student_ids")
    @classmethod
    def unique_students(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select each student once")
        return value


# 1 MB of CSV text; the repository also bounds the row count.
ROSTER_IMPORT_MAX_BYTES = 1_048_576


class RosterImportPreview(Contract):
    csv: str = Field(min_length=1, max_length=ROSTER_IMPORT_MAX_BYTES)

    @field_validator("csv")
    @classmethod
    def bounded_bytes(cls, value):
        if len(value.encode("utf-8", errors="replace")) > ROSTER_IMPORT_MAX_BYTES:
            raise ValueError("The CSV file exceeds 1 MB")
        return value


class RosterImportCommit(RosterImportPreview):
    rows_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_period_revision: int = Field(ge=1)


class PeriodClone(Contract):
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def meaningful_title(cls, value):
        result = value.strip()
        if not result or result.startswith("Archived invalid period"):
            raise ValueError("Enter an academic period title")
        return result


class PeriodArchive(Contract):
    expected_revision: int = Field(ge=1)


class CalendarWrite(Contract):
    expected_revision: int = Field(ge=1)
    calendar: AcademicCalendar


class RecordEnvelope(Contract):
    revision: int
    updated_at: str
    updated_by: str
    record: AcademicRecord


class PeriodCreate(Contract):
    title: str = Field(min_length=1, max_length=160)
    include_cdm_catalog: bool = True
    calendar: AcademicCalendar | None = None

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
    source: Literal["development-entered", "institutional", "synthetic-review"]
    calendar: AcademicCalendar | None = None
    archived_at: str | None = None

    @model_serializer(mode="wrap")
    def omit_absent_archive(self, handler):
        return omit_none(handler(self), "archived_at")


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
    # Administrator setup screen that resolves the issue, e.g. "/admin/teachers".
    action_path: str | None = Field(default=None, pattern=r"^/admin(/[a-z-]+)+$")

    @model_serializer(mode="wrap")
    def omit_absent_action(self, handler):
        value = handler(self)
        if value.get("action_path") is None:
            value.pop("action_path", None)
        return value


class AcademicReadiness(Contract):
    period: AcademicPeriod
    issues: list[ReadinessIssue]
    ready: bool
    programs: int
    subjects: int
    sections: int
    faculty: int
    assigned_faculty: int | None = None
    offerings: int
    eligible_resources: int
    inputs: GenerationInput | None


class AcademicGenerationRequest(Contract):
    expected_revision: int = Field(ge=1)
