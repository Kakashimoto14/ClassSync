"""Build the existing solver DTO exclusively from persisted academic records."""

from collections import defaultdict

from classync_contracts.academic import AcademicReadiness, AcademicSnapshot, ReadinessIssue
from classync_contracts.scheduling import GenerationInput, Offering, Program, Room, Section, Teacher
from pydantic import ValidationError

from .readiness import infeasibility_diagnostics, readiness


def solver_fields(record, model):
    return model.model_validate(record.model_dump(include=set(model.model_fields)))


def academic_readiness(snapshot: AcademicSnapshot):
    by_kind = defaultdict(dict)
    for envelope in snapshot.records:
        record = envelope.record
        by_kind[record.kind][record.id] = record
    programs, subjects, sections, faculty, rooms, offerings = (
        by_kind[k]
        for k in ("programs", "subjects", "sections", "faculty", "resources", "offerings")
    )
    active_sections = [s for s in sections.values() if s.active]
    section_labels = {
        s.id: s.custom_label
        or (
            f"{programs[s.program_id].acronym if s.program_id in programs else s.program_id}"
            f"-{s.year_level}{s.section_letter}"
        )
        for s in active_sections
    }
    active_offerings = [o for o in offerings.values() if o.active]
    rules = next(iter(by_kind["constraints"].values()), None)
    issues = []

    def issue(code, message, identity=None, severity="blocking"):
        issues.append(
            ReadinessIssue(code=code, message=message, record_id=identity, severity=severity)
        )

    if not active_sections:
        issue("missing_sections", "Create the sections intended for this academic period.")
    if not active_offerings:
        issue("missing_offerings", "Create subject offerings for this academic period.")
    if not rules or not rules.operating_windows:
        issue(
            "missing_operating_hours",
            "Supply permitted days and operating hours in Scheduling Constraints.",
        )
    for section in active_sections:
        program_label = (
            programs[section.program_id].acronym
            if section.program_id in programs
            else section.program_id
        )
        label = (
            section.custom_label or f"{program_label}-{section.year_level}{section.section_letter}"
        )
        if not any(o.section_id == section.id for o in active_offerings):
            issue(
                "section_without_offerings", f"{label} has no active subject offerings.", section.id
            )
        if not section.population_verified:
            issue(
                "population_unverified",
                f"{label}: population is unverified; "
                "capacity coverage is not asserted unless explicitly required.",
                section.id,
                "warning",
            )
    normalized_offerings = []
    for offering in active_offerings:
        subject, section = subjects.get(offering.subject_id), sections.get(offering.section_id)
        label = subject.code if subject else offering.id
        if not subject or not section or not subject.active or not section.active:
            issue(
                "inactive_reference", f"{label}: activate a valid subject and section.", offering.id
            )
            continue
        program = programs.get(section.program_id)
        if not program or not program.active or section.program_id not in subject.program_ids:
            issue(
                "program_association",
                f"{label}: associate the subject with the active section program.",
                offering.id,
            )
        if not offering.teacher_ids:
            issue(
                "missing_faculty",
                f"{label}: assign an instructor or explicit eligible faculty.",
                offering.id,
            )
        for identity in offering.teacher_ids:
            teacher = faculty.get(identity)
            if not teacher or not teacher.active or subject.id not in teacher.subject_ids:
                issue(
                    "faculty_eligibility",
                    f"{label}: selected faculty is missing, inactive "
                    "or not eligible for this subject.",
                    offering.id,
                )
            elif not teacher.availability:
                issue(
                    "teacher_availability_missing",
                    f"{teacher.name}: enter permitted teaching windows.",
                    teacher.id,
                )
        if not offering.room_ids:
            issue(
                "missing_room_eligibility",
                f"{label}: select eligible classroom resources.",
                offering.id,
            )
        if any(
            identity not in rooms or not rooms[identity].active for identity in offering.room_ids
        ):
            issue(
                "room_reference",
                f"{label}: selected resources are missing or inactive.",
                offering.id,
            )
        minutes = offering.weekly_minutes_override or subject.required_weekly_minutes
        patterns = (
            offering.patterns_override
            if offering.patterns_override is not None
            else subject.patterns
        )
        if minutes is None:
            issue(
                "missing_weekly_minutes",
                f"{label}: enter required weekly contact minutes.",
                offering.id,
            )
            continue
        if not patterns:
            issue(
                "missing_patterns",
                f"{label}: allow at least one valid meeting pattern.",
                offering.id,
            )
            continue
        selected_faculty = [faculty[tid] for tid in offering.teacher_ids if tid in faculty]
        if selected_faculty and not any(
            (t.max_weekly_minutes is None or t.max_weekly_minutes >= minutes)
            and any(
                all(
                    t.max_daily_minutes is None or duration <= t.max_daily_minutes
                    for duration in p.durations
                )
                for p in patterns
            )
            for t in selected_faculty
        ):
            issue(
                "insufficient_faculty_workload",
                f"{label}: no selected instructor can provide the weekly minutes "
                "and meeting durations within the supplied workload limits.",
                offering.id,
            )
        capacity = max(
            [
                n
                for n in (
                    subject.minimum_capacity,
                    offering.minimum_capacity,
                    section.population if section.population_verified else None,
                )
                if n is not None
            ],
            default=None,
        )
        if not capacity:
            issue(
                "capacity_not_required",
                f"{label}: no verified population or minimum capacity supplied; "
                "capacity suitability remains unasserted.",
                offering.id,
                "warning",
            )
        try:
            normalized_offerings.append(
                Offering(
                    id=offering.id,
                    subject_id=subject.id,
                    subject_name=subject.name,
                    section_id=section.id,
                    eligible_teacher_ids=offering.teacher_ids,
                    eligible_room_ids=offering.room_ids,
                    required_weekly_minutes=minutes,
                    patterns=patterns,
                    required_room_type=offering.required_room_type or subject.required_room_type,
                    required_equipment=sorted(
                        set(subject.required_equipment + offering.required_equipment)
                    ),
                    minimum_capacity=capacity,
                    allowed_buildings=offering.allowed_buildings,
                )
            )
        except ValidationError as error:
            issue("session_requirement", f"{label}: {error.errors()[0]['msg']}", offering.id)
    if rules and not rules.all_intended_offerings_supplied:
        issue(
            "scope_not_complete",
            "Coverage applies only to supplied active offerings; "
            "all intended offerings have not been declared complete.",
            severity="warning",
        )
    if any(not getattr(e.record, "active", True) for e in snapshot.records):
        issue(
            "inactive_records",
            "Inactive records are excluded. Active offerings referencing them block generation.",
            severity="warning",
        )
    inputs = None
    if not any(i.severity == "blocking" for i in issues):
        teacher_ids = {tid for o in active_offerings for tid in o.teacher_ids}
        room_ids = {rid for o in active_offerings for rid in o.room_ids}
        try:
            inputs = GenerationInput(
                period_id=snapshot.period.id,
                data_version=f"academic:{snapshot.period.id}:revision:{snapshot.period.revision}",
                scope_description=(
                    f"{snapshot.period.title}. {snapshot.period.source} inputs; "
                    "coverage limited to this saved period's active offerings."
                ),
                synthetic=False,
                all_intended_offerings_supplied=rules.all_intended_offerings_supplied,
                operating_windows=rules.operating_windows,
                transition_buffer_minutes=rules.transition_buffer_minutes,
                programs=[solver_fields(p, Program) for p in programs.values()],
                sections=[solver_fields(s, Section) for s in active_sections],
                teachers=[solver_fields(faculty[tid], Teacher) for tid in sorted(teacher_ids)],
                rooms=[solver_fields(rooms[rid], Room) for rid in sorted(room_ids)],
                offerings=normalized_offerings,
                locked_assignments=rules.locked_assignments,
                enrollments=rules.enrollments,
                options=rules.options,
            )
            offering_labels = {
                o.id: f"{subjects[o.subject_id].code} · {section_labels[o.section_id]}"
                for o in active_offerings
            }

            def report(diagnostic):
                label = offering_labels.get(diagnostic.offering_id)
                message = f"{label}: {diagnostic.message}" if label else diagnostic.message
                for identity, section_label in section_labels.items():
                    message = message.replace(f"Section {identity} ", f"Section {section_label} ")
                issue(diagnostic.code, message, diagnostic.offering_id)

            for diagnostic in readiness(inputs):
                report(diagnostic)
            if not any(i.severity == "blocking" for i in issues):
                for diagnostic in infeasibility_diagnostics(inputs):
                    report(diagnostic)
        except ValidationError as error:
            issue("input_contract", error.errors()[0]["msg"])
    return AcademicReadiness(
        period=snapshot.period,
        issues=issues,
        ready=not any(i.severity == "blocking" for i in issues),
        programs=sum(p.active for p in programs.values()),
        subjects=sum(s.active for s in subjects.values()),
        sections=len(active_sections),
        faculty=sum(t.active for t in faculty.values()),
        offerings=len(active_offerings),
        eligible_resources=sum(
            r.active and r.schedulable and r.condition == "operational" for r in rooms.values()
        ),
        inputs=inputs,
    )
