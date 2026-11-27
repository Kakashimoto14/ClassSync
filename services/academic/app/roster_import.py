"""Authoritative CSV parsing for roster imports. Pure functions; no storage access."""

import csv
import io
import re

from classync_contracts.email_address import normalize_email

from .record_rules import AcademicError, checksum, encode

MAX_ROWS = 2000
REQUIRED_COLUMNS = ("student_id", "full_name", "email", "section")
OPTIONAL_COLUMNS = ("enrollment_status",)
STATUSES = ("active", "inactive", "unverified")
STUDENT_ID = re.compile(r"[0-9]{2}-[0-9]{5}")
# The same shape `classsync_identity.manage_student_roster` enforces, checked here so one bad
# address is a row message instead of a failed transaction.
DATABASE_EMAIL = re.compile(
    r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@"
    r"([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
)


def roster_email(value):
    """Normalized address that the roster database accepts, or None."""
    normalized = normalize_email(value)
    if normalized is None or len(normalized) > 320 or not DATABASE_EMAIL.fullmatch(normalized):
        return None
    return normalized


def _invalid(message):
    return AcademicError(422, "roster_import_file", message)


def parse_csv(content):
    """Return [{line, student_id, full_name, email, section, enrollment_status}] as typed."""
    try:
        reader = csv.reader(io.StringIO(content.lstrip("﻿"), newline=""), strict=True)
        header = next(reader, None)
        if header is None:
            raise _invalid("The file is empty.")
        columns = [name.strip().lower() for name in header]
        missing = [name for name in REQUIRED_COLUMNS if name not in columns]
        unknown = [name for name in columns if name not in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS)]
        if missing or unknown or len(set(columns)) != len(columns):
            raise _invalid(
                "Use one header row with student_id, full_name, email, section and, optionally, "
                "enrollment_status."
            )
        rows = []
        for values in reader:
            if not any(value.strip() for value in values):
                continue
            if len(values) != len(columns):
                raise _invalid(f"Line {reader.line_num} does not have {len(columns)} columns.")
            if len(rows) >= MAX_ROWS:
                raise _invalid(f"Import at most {MAX_ROWS} students per file.")
            row = dict(zip(columns, (value.strip() for value in values), strict=True))
            rows.append({"line": reader.line_num, **row})
    except csv.Error as error:
        raise _invalid("The file is not valid CSV. Check quotes and line endings.") from error
    if not rows:
        raise _invalid("The file has a header but no student rows.")
    return rows


def same_name(first, second):
    return " ".join((first or "").split()).casefold() == " ".join((second or "").split()).casefold()


def continuing_problem(student, name, email, section):
    """Why an existing university record may not join this section, or None.

    `student` is {display_name, email, in_own_period, binding}. Enrollment never edits the
    record, so every difference is refused rather than resolved silently. `section` is the
    target academic section, or None when it could not be resolved.
    """
    if not student["in_own_period"]:
        return (
            "Student ID already exists, but the record is not in any of your academic periods, "
            "so it cannot be enrolled here."
        )
    if not same_name(student["display_name"], name) or student["email"] != email:
        return "Name or email does not match the university record for this student ID."
    binding = student["binding"]
    if section is not None and binding is not None:
        if binding != (section.entry_cohort_year, section.curriculum_version_id):
            return (
                "This student's curriculum cohort differs from the section's. Choose a section "
                "of the same cohort."
            )
    return None


def validate_rows(rows, sections, *, enrolled, existing, existing_emails):
    """Normalize rows, decide create or enroll, and attach row-level messages.

    `sections` maps a case-folded section label or id to {id, label, record, offerings}.
    `existing` maps a student ID to its university record; `enrolled` holds the IDs already
    in the target period.
    """
    seen_ids, seen_emails, checked = set(), set(), []
    for row in rows:
        errors = []
        student = row["student_id"]
        name = row["full_name"]
        email = roster_email(row["email"])
        section = sections.get(row["section"].casefold())
        file_status = row.get("enrollment_status", "").lower()
        status = file_status or "unverified"
        record = existing.get(student)
        action, note = "create_new", ""
        if not STUDENT_ID.fullmatch(student):
            errors.append("Student ID must look like 24-00101.")
        elif student in seen_ids:
            errors.append("Student ID is repeated in this file.")
        elif student in enrolled:
            errors.append("Student is already enrolled in this period.")
        elif record is not None:
            action = "enroll_existing"
            problem = continuing_problem(
                record, name, email, section["record"] if section else None
            )
            if problem:
                errors.append(problem)
        seen_ids.add(student)
        if not 1 <= len(name) <= 160 or any(ord(char) < 32 for char in name):
            errors.append("Full name must be 1 to 160 characters on one line.")
        if email is None:
            errors.append("Email address is not valid.")
        elif email in seen_emails:
            errors.append("Email is repeated in this file.")
        elif action == "create_new" and email in existing_emails:
            errors.append("Email already belongs to a roster student.")
        if email:
            seen_emails.add(email)
        if section is None:
            errors.append("Section is not an active section of this period.")
        elif not section["offerings"]:
            errors.append("Section has no active subject offerings.")
        if status not in STATUSES:
            errors.append("Enrollment status must be active, inactive or unverified.")
        elif action == "enroll_existing":
            status = record["enrollment_status"]
            if file_status and file_status != status:
                note = f"Keeps current status {status}; the file's {file_status} is not applied."
        checked.append(
            {
                "line": row["line"],
                "student_id": student,
                "full_name": name,
                "email": email or row["email"],
                "section_id": section["id"] if section else None,
                "section_label": section["label"] if section else row["section"],
                "enrollment_status": status,
                "action": action,
                "note": note,
                "errors": errors,
            }
        )
    return checked


def rows_hash(period_id, rows):
    """Binds a commit to the exact normalized rows the Administrator previewed."""
    return checksum(
        encode(
            [period_id]
            + [
                [
                    row["student_id"],
                    row["full_name"],
                    row["email"],
                    row["section_id"],
                    row["enrollment_status"],
                    row["action"],
                ]
                for row in rows
            ]
        )
    )
