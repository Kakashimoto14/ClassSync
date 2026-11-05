"""Explicitly hypothetical BSIT pilot; only the disposable qualifier invokes persistence."""

from classync_contracts.academic import (
    AcademicConstraints,
    AcademicFaculty,
    AcademicOffering,
    AcademicProgram,
    AcademicResource,
    AcademicSection,
    PeriodCreate,
)
from classync_contracts.curriculum import catalog

from .curriculum_catalog import subject_from_course


def pilot_records():
    data = catalog()
    windows = [dict(day=day, start=420, end=1140) for day in range(6)]
    records = [
        AcademicProgram(id="bsit", acronym="BSIT", name="Information Technology", institute="ICS")
    ]
    enrollments = []
    for year, cohort in ((1, 2026), (2, 2025), (3, 2024), (4, 2023)):
        source = next(
            v
            for v in data["versions"]
            if v["program"] == "BSIT" and int(v["entry_cohort"]) == cohort
        )
        section_id = f"SYN-BSIT{year}A"
        records.append(
            AcademicSection(
                id=section_id,
                period_id="__assigned_by_repository__",
                program_id="bsit",
                year_level=year,
                section_letter="A",
                entry_cohort_year=cohort,
                curriculum_version_id=source["id"],
                population=20,
                population_verified=True,
            )
        )
        room_id = f"SYN-ROOM-{year}"
        records.append(
            AcademicResource(
                id=room_id,
                name=f"Synthetic room {year}",
                building="Synthetic campus",
                source="synthetic",
                schedulable=True,
                condition="operational",
                availability=windows,
                capacity=30,
                capacity_verified=True,
                verification_note="Synthetic test assumption only; no physical room assertion",
            )
        )
        offering_ids = []
        for row in data["courses"]:
            if (
                row["curriculum_version_id"] != source["id"]
                or row["year_level"] != str(year)
                or (row["semester"] != "1")
            ):
                continue
            subject = subject_from_course(row["id"])
            # Demonstrative allocation, deliberately independent of PDF Lec/Lab/Units.
            subject.required_weekly_minutes = 180
            from classync_contracts.scheduling import SessionPattern

            subject.patterns = [SessionPattern(id="synthetic-two-90", durations=[90, 90])]
            records.append(subject)
            teachers = []
            for candidate in range(1, 4):
                identity = f"SYN-{row['subject_code']}-{candidate:02}"
                teachers.append(identity)
                records.append(
                    AcademicFaculty(
                        id=identity,
                        name=f"Synthetic Faculty {row['subject_code']} {candidate:02}",
                        synthetic=True,
                        subject_ids=[subject.id],
                        availability=windows,
                        max_daily_minutes=360,
                        max_weekly_minutes=900,
                    )
                )
            oid = f"SYN-offering-{row['id']}"
            offering_ids.append(oid)
            records.append(
                AcademicOffering(
                    id=oid,
                    subject_id=subject.id,
                    section_id=section_id,
                    teacher_ids=teachers,
                    room_ids=[room_id],
                )
            )
        enrollments.append(
            dict(
                student_id=f"SYN-student-{year}",
                offering_ids=offering_ids,
                entry_cohort_year=cohort,
                curriculum_version_id=source["id"],
            )
        )
    records.append(
        AcademicConstraints.model_validate(
            dict(
                operating_windows=windows,
                all_intended_offerings_supplied=True,
                enrollments=enrollments,
                options=dict(time_limit_seconds=10.0, seed=42),
            )
        )
    )
    assert sum(r.kind == "subjects" for r in records) == 27
    assert sum(r.kind == "faculty" for r in records) == 81
    return records


def seed_pilot(repository, *, calendar=None):
    return repository.create_synthetic_review_period(
        PeriodCreate(
            title="SYNTHETIC BSIT 2026/27 first-term pilot — hypothetical sections",
            include_cdm_catalog=False,
            calendar=calendar,
        ),
        pilot_records(),
    )
