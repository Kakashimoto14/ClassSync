"""Validation helpers for period-bound Administrator roster edits."""

from classync_contracts.academic import AcademicOffering, AcademicSection, RosterStudentWrite
from classync_contracts.scheduling import Enrollment

from .record_rules import AcademicError


def enrollment_for_section(
    student_id: str,
    body: RosterStudentWrite,
    section: AcademicSection | None,
    offerings: list[AcademicOffering],
) -> Enrollment:
    if section is None or not section.active or section.year_level != body.year_level:
        raise AcademicError(
            422, "invalid_roster_section", "Choose an active section for that year level."
        )
    active_offerings = [offering for offering in offerings if offering.active]
    if not active_offerings:
        raise AcademicError(
            422, "section_without_offerings", "The selected section has no active offerings."
        )
    return Enrollment(
        student_id=student_id,
        offering_ids=[offering.id for offering in active_offerings],
        entry_cohort_year=section.entry_cohort_year,
        curriculum_version_id=section.curriculum_version_id,
    )
