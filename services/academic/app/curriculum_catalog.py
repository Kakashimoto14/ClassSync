"""Read-only source catalog and explicit exact-course staging DTO conversion."""

from classync_contracts.academic import AcademicSubject
from classync_contracts.curriculum import PROGRAMS, catalog, course

from .record_rules import AcademicError


def review_catalog():
    data = catalog()
    return {**data, "program_ids": PROGRAMS}


def subject_from_course(identity):
    row = course(identity)
    if row is None:
        raise AcademicError(404, "curriculum_course_not_found", "Unknown source course.")
    return AcademicSubject(
        id=f"review-{row['id']}",
        code=row["subject_code"],
        name=row["subject_title"],
        curriculum_version_id=row["curriculum_version_id"],
        curriculum_course_id=row["id"],
        program_ids=[PROGRAMS[row["program"]]],
        year_level=int(row["year_level"]),
        semester={"1": "first", "2": "second"}.get(row["semester"]),
        provenance="source-supplied",
        required_weekly_minutes=None,
        patterns=[],
    )
