"""Build the existing solver DTO exclusively from persisted academic records."""

from collections import defaultdict

from classync_contracts.academic import AcademicReadiness, AcademicSnapshot, ReadinessIssue
from classync_contracts.scheduling import GenerationInput, Offering, Program, Room, Section, Teacher
from pydantic import ValidationError

from .catalog import excluded_space_ids
from .readiness import infeasibility_diagnostics, readiness

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


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
    used_rooms = {rid for o in active_offerings for rid in o.room_ids}
    used_teachers = {tid for o in active_offerings for tid in o.teacher_ids}
    simulation = (
        snapshot.period.source in {"development-entered", "synthetic-review"}
        and bool(used_rooms)
        and all(rid in rooms and rooms[rid].source == "synthetic" for rid in used_rooms)
        and all(tid in faculty and faculty[tid].synthetic for tid in used_teachers)
    )
    rules = next(iter(by_kind["constraints"].values()), None)
    issues = []

    def issue(code, message, identity=None, severity="blocking", action_path=None):
        issues.append(
            ReadinessIssue(
                code=code,
                message=message,
                record_id=identity,
                severity=severity,
                action_path=action_path,
            )
        )

    if not active_sections:
        issue("missing_sections", "Create the sections intended for this academic period.")
    if not active_offerings:
        issue("missing_offerings", "Create subject offerings for this academic period.")
    if snapshot.period.calendar is None:
        issue(
            "missing_academic_calendar",
            "Enter the approved academic year, semester, effective dates and instructional days.",
        )
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
                "verify aggregate enrollment before assigning capacity-limited rooms.",
                section.id,
                "blocking" if snapshot.period.source == "institutional" else "warning",
            )
        if not simulation and snapshot.period.source == "institutional":
            if (
                not section.entry_cohort_year
                or not section.curriculum_version_id
                or not section.cohort_assignment_verified
            ):
                issue(
                    "cohort_assignment_unverified",
                    f"{label}: confirm the Registrar-assigned entry cohort and curriculum version.",
                    section.id,
                )
            if not section.identity_verified:
                issue(
                    "section_identity_unverified",
                    f"{label}: confirm the official section identity.",
                    section.id,
                )
            if section.population_verified and not section.verification_reference:
                issue(
                    "population_reference_missing",
                    f"{label}: record the verified aggregate-population source/reference.",
                    section.id,
                )
            if (
                section.cohort_assignment_verified or section.identity_verified
            ) and not section.verification_reference:
                issue(
                    "section_verification_reference_missing",
                    f"{label}: record the cohort/identity verification source.",
                    section.id,
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
        if subject.curriculum_version_id != section.curriculum_version_id:
            issue(
                "curriculum_association",
                f"{label}: section curriculum does not match.",
                offering.id,
            )
        if not simulation and (
            subject.curriculum_version_id or snapshot.period.source == "institutional"
        ):
            if not subject.curriculum_review_verified:
                issue(
                    "curriculum_unreviewed",
                    f"{label}: review and approve the source course or Registrar mapping.",
                    subject.id,
                )
            if not subject.contact_minutes_verified:
                issue(
                    "contact_minutes_unverified", f"{label}: approve contact minutes.", subject.id
                )
            if not subject.curriculum_review_reference:
                issue(
                    "curriculum_reference_missing",
                    f"{label}: record the Registrar/source review reference.",
                    subject.id,
                )
            if not subject.contact_minutes_reference:
                issue(
                    "contact_minutes_reference_missing",
                    f"{label}: record the approved minutes/pattern reference.",
                    subject.id,
                )
        if not simulation and snapshot.period.source == "institutional":
            if not offering.term_offering_verified:
                issue(
                    "term_offering_unverified",
                    f"{label}: confirm this actual offering for the selected period and section.",
                    offering.id,
                )
            if not offering.verification_reference:
                issue(
                    "offering_reference_missing",
                    f"{label}: record the approved term-offering reference.",
                    offering.id,
                )
        if (
            offering.weekly_minutes_override is not None or offering.patterns_override is not None
        ) and not offering.override_requirements_verified:
            issue(
                "offering_override_unverified",
                f"{label}: verify offering-specific minutes and meeting patterns.",
                offering.id,
            )
        if not simulation and any(
            tid in faculty and faculty[tid].synthetic for tid in offering.teacher_ids
        ):
            issue(
                "synthetic_faculty",
                f"{label}: synthetic faculty cannot serve institutional data.",
                offering.id,
            )
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
            if teacher and teacher.active and teacher.max_weekly_minutes is None:
                issue(
                    "faculty_workload_unverified",
                    f"{teacher.name}: enter the approved weekly workload limit.",
                    teacher.id,
                )
            if (
                not simulation
                and snapshot.period.source == "institutional"
                and teacher
                and teacher.active
            ):
                if not (
                    teacher.eligibility_verified
                    and teacher.availability_verified
                    and teacher.workload_verified
                    and teacher.verification_reference
                ):
                    issue(
                        "faculty_verification_missing",
                        f"{teacher.name}: verify eligibility, availability and workload and record "
                        "the source/reference.",
                        teacher.id,
                    )
        if not offering.room_ids:
            issue(
                "missing_room_eligibility",
                f"{label}: select eligible classroom resources.",
                offering.id,
            )
        if excluded := sorted(set(offering.room_ids) & excluded_space_ids()):
            issue(
                "excluded_space_selected",
                f"{label}: remove excluded campus spaces ({', '.join(excluded)}); "
                "they are never schedulable.",
                offering.id,
                action_path="/admin/offerings",
            )
        if any(
            identity not in rooms or not rooms[identity].active for identity in offering.room_ids
        ):
            issue(
                "room_reference",
                f"{label}: selected resources are missing or inactive.",
                offering.id,
            )
        for identity in offering.room_ids:
            room = rooms.get(identity)
            if not simulation and snapshot.period.source == "institutional" and room:
                owner_verified_catalog_room = (
                    room.source == "cdm-provisional"
                    and room.schedulable
                    and room.condition == "operational"
                    and room.type_verified
                    and room.capacity_verified
                    and room.availability_verified
                )
                if room.source != "administrator-supplied" and not owner_verified_catalog_room:
                    issue(
                        "noninstitutional_room",
                        f"{room.name}: provisional resources require administrator-verified "
                        "operational, type, capacity and availability metadata before use.",
                        room.id,
                    )
                if not room.availability_verified:
                    issue(
                        "room_availability_unverified",
                        f"{room.name}: verify availability and blocked windows.",
                        room.id,
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
                    subject_code=subject.code,
                    section_id=section.id,
                    activity_type=offering.activity_type,
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
    calendar = snapshot.period.calendar
    if rules and calendar and (
        outside := sorted(
            {w.day for w in rules.operating_windows} - set(calendar.instructional_days)
        )
    ):
        issue(
            "operating_days_outside_calendar",
            "Operating windows on "
            + ", ".join(DAY_NAMES[day] for day in outside)
            + " are ignored because the academic calendar does not list them as "
            "instructional days.",
            severity="warning",
            action_path="/admin/academic",
        )
    if rules and not rules.all_intended_offerings_supplied:
        issue(
            "scope_not_complete",
            "Declare and verify that all intended offerings and shared commitments in this "
            "period scope are supplied before generation.",
        )
    if rules and not simulation and snapshot.period.source == "institutional":
        if not rules.operating_windows_verified or not rules.verification_reference:
            issue(
                "operating_windows_unverified",
                "Verify academic operating windows and record the approved calendar/rules "
                "reference.",
            )
        if not rules.shared_scope_verified or not rules.shared_scope_reference:
            issue(
                "shared_scope_unverified",
                "Review shared ICS, IBE and ITE offerings, faculty, rooms and fixed "
                "commitments in this period, and record the approved scope reference.",
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
                synthetic=simulation,
                all_intended_offerings_supplied=rules.all_intended_offerings_supplied,
                operating_windows=[
                    window
                    for window in rules.operating_windows
                    if window.day in snapshot.period.calendar.instructional_days
                ],
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
                issue(
                    diagnostic.code,
                    message,
                    diagnostic.offering_id,
                    action_path=diagnostic.action_path,
                )

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
        assigned_faculty=len(
            {
                tid
                for o in active_offerings
                for tid in o.teacher_ids
                if tid in faculty and faculty[tid].active
            }
        ),
        offerings=len(active_offerings),
        eligible_resources=sum(
            r.active and r.schedulable and r.condition == "operational" for r in rooms.values()
        ),
        inputs=inputs,
    )
