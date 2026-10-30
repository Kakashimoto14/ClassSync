"""Academic invariants shared by local SQLite and PostgreSQL adapters.

The lookup callback must read typed records from the same owner/period transaction.
This module contains no database, identity provisioning or scheduling authority.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from classync_contracts import scheduling
from classync_contracts.academic import AcademicConstraints, AcademicRecord, AcademicResource
from pydantic import TypeAdapter

adapter = TypeAdapter(AcademicRecord)


class AcademicError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def timestamp():
    return datetime.now(UTC).isoformat()


def validate_calendar(calendar):
    if calendar is not None and calendar.published_version:
        raise AcademicError(
            422,
            "publication_version",
            "Publication versions are assigned by the scheduling service.",
        )


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def checksum(value):
    return hashlib.sha256(value.encode()).hexdigest()


def catalog_data():
    root = Path(scheduling.__file__).parent / "catalogs"
    return (
        json.loads((root / "programs.json").read_text()),
        json.loads((root / "cdm-spaces.json").read_text()),
    )


def references(record):
    refs = []
    if record.kind == "subjects":
        refs += [("programs", i) for i in record.program_ids]
    elif record.kind == "sections":
        refs.append(("programs", record.program_id))
    elif record.kind == "faculty":
        refs += [("subjects", i) for i in record.subject_ids]
    elif record.kind == "resources":
        refs += [("programs", i) for i in record.allowed_program_ids or []]
    elif record.kind == "offerings":
        refs += [("subjects", record.subject_id), ("sections", record.section_id)]
        refs += [("faculty", i) for i in record.teacher_ids]
        refs += [("resources", i) for i in record.room_ids]
    elif record.kind == "constraints":
        for lock in record.locked_assignments:
            refs += [
                ("offerings", lock.offering_id),
                ("sections", lock.section_id),
                ("faculty", lock.teacher_id),
                ("resources", lock.room_id),
                ("subjects", lock.subject_id),
            ]
        for student in record.enrollments:
            refs += [("offerings", i) for i in student.offering_ids]
    return set(refs)


def unique_label(record):
    if record.kind == "programs":
        return record.acronym.strip().casefold()
    if record.kind == "subjects":
        return record.code.strip().casefold()
    if record.kind == "sections":
        return encode(
            [record.program_id, record.custom_label or [record.year_level, record.section_letter]]
        )
    if record.kind == "offerings":
        return encode([record.subject_id, record.section_id])
    if record.kind == "resources":
        return encode([record.building.strip().casefold(), record.name.strip().casefold()])
    return record.id


def validate_record(record, period_id, lookup):
    """Validate against transaction-local scoped records before any mutation."""
    cache = {}

    def related(kind, identity):
        key = (kind, identity)
        if key not in cache:
            cache[key] = lookup(kind, identity)
        value = cache[key]
        if value is None:
            raise AcademicError(
                422,
                "missing_reference",
                f"Unknown {kind} reference: {identity}. Save that record in this period first.",
            )
        return value

    for field in ("name", "acronym", "code", "building"):
        if hasattr(record, field) and not getattr(record, field).strip():
            raise AcademicError(422, "required_field", f"Enter {field}.")
    for field in ("program_ids", "subject_ids", "teacher_ids", "room_ids"):
        if hasattr(record, field):
            values = getattr(record, field)
            if len(values) != len(set(values)):
                raise AcademicError(
                    422, "duplicate_reference", f"Select each {field} reference once."
                )
    for target_kind, target_id in references(record):
        related(target_kind, target_id)
    if record.kind == "sections":
        program = related("programs", record.program_id)
        if record.period_id != period_id:
            raise AcademicError(
                422, "period_reference", "Section belongs to a different academic period."
            )
        if program.section_policy == "degree" and (
            record.year_level is None or not record.section_letter
        ):
            raise AcademicError(
                422,
                "section_naming",
                "Degree sections require structured year level and section identifier.",
            )
        if program.section_policy == "custom" and not record.custom_label:
            raise AcademicError(
                422, "section_naming", "This program requires its own custom section label."
            )
        if (
            program.allowed_year_levels is not None
            and record.year_level not in program.allowed_year_levels
        ):
            raise AcademicError(
                422, "section_naming", "Year level is outside this program's configured policy."
            )
    if record.kind == "offerings":
        subject = related("subjects", record.subject_id)
        section = related("sections", record.section_id)
        if subject.program_ids and section.program_id not in subject.program_ids:
            raise AcademicError(
                422,
                "curriculum_association",
                "The subject is not associated with this section's program.",
            )
        for teacher_id in record.teacher_ids:
            if record.subject_id not in related("faculty", teacher_id).subject_ids:
                raise AcademicError(
                    422,
                    "faculty_eligibility",
                    "Selected faculty is not eligible for this subject.",
                )
        minutes = record.weekly_minutes_override or subject.required_weekly_minutes
        patterns = (
            record.patterns_override if record.patterns_override is not None else subject.patterns
        )
        if minutes is not None and any(sum(p.durations) != minutes for p in patterns):
            raise AcademicError(
                422,
                "weekly_minutes",
                "Offering patterns must total the required weekly minutes.",
            )
    if record.kind == "resources" and record.id.startswith("cdm-"):
        room = next((r for r in catalog_data()[1] if r["id"] == record.id), None)
        if (
            room is None
            or any(
                getattr(record, k) != room.get(k)
                for k in ("name", "building", "floor", "location", "alias")
            )
            or record.alias_unconfirmed != room.get("aliasUnconfirmed", False)
            or record.source != "cdm-provisional"
        ):
            raise AcademicError(
                422,
                "cdm_identity",
                "Preserve the supplied CdM resource ID, location and provisional label.",
            )


def initial_records(include_cdm_catalog):
    records = [AcademicConstraints()]
    if include_cdm_catalog:
        programs, rooms = catalog_data()
        records = (
            [adapter.validate_python({**p, "kind": "programs"}) for p in programs]
            + [
                AcademicResource(
                    **{k: v for k, v in room.items() if k not in {"aliasUnconfirmed", "alias"}},
                    source="cdm-provisional",
                    alias=room.get("alias"),
                    alias_unconfirmed=room.get("aliasUnconfirmed", False),
                )
                for room in rooms
            ]
            + records
        )
    return records
