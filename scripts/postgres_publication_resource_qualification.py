"""Isolated actual publication conflicts from generated durable academic records only."""

import argparse
import re
from datetime import date
from pathlib import Path

from classync_contracts.academic import PeriodCreate, RecordWrite
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.publication import PublicationCommand
from classync_persistence.database import transaction

from scripts.postgres_academic_restore_qualification import prepare_source
from scripts.postgres_academic_restore_qualification import store as academic_store
from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_publication_repository_qualification import (
    MIGRATION,
    authorize_grants,
    bounded_runtime,
    check_pool,
    checked_connection,
    repository,
    saved_draft,
    state,
    verify_fresh_target,
)
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.app.draft_rules import DraftError, digest, encode
from services.scheduling.app.occurrences import dated_occurrences

KINDS = ("room", "teacher", "section", "student")
WINDOW = {"day": 0, "start": 480, "end": 540}


def fixture_options(label, count, students_per_offering, shared_ids):
    require(
        isinstance(label, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,35}", label),
        "Short generated fixture label required",
    )
    require(
        type(count) is int
        and 1 <= count <= 200
        and type(students_per_offering) is int
        and 1 <= students_per_offering <= 100,
        "Bounded independent offering/student counts required",
    )
    require(
        isinstance(shared_ids, dict)
        and set(shared_ids) <= set(KINDS)
        and all(
            isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]{0,70}", value)
            for value in shared_ids.values()
        )
        and (not shared_ids or count == students_per_offering == 1),
        "Shared generated identities require a single offering and student",
    )


def fixture_calendar():
    return AcademicCalendar(
        academic_year="2026-2027",
        semester="first",
        effective_start=date(2026, 10, 5),
        effective_end=date(2026, 10, 5),
        instructional_days=[0],
    )


def record_definitions(period_id, label, *, count=1, students_per_offering=1, shared_ids=None):
    """Invented, bounded academic inputs; this function neither solves nor opens storage."""
    shared_ids = {} if shared_ids is None else shared_ids
    fixture_options(label, count, students_per_offering, shared_ids)
    program = label + "-program"
    records = [
        {
            "kind": "programs",
            "id": program,
            "acronym": label.upper(),
            "name": "Invented resource-matrix program " + label,
            "institute": "Synthetic qualification only",
            "section_policy": "custom",
        }
    ]
    enrollments = []
    for index in range(count):
        prefix = f"{label}-{index}"
        subject, offering = prefix + "-subject", prefix + "-offering"
        identities = {kind: shared_ids.get(kind, prefix + "-" + kind) for kind in KINDS}
        records.extend(
            [
                {
                    "kind": "subjects",
                    "id": subject,
                    "code": subject.upper(),
                    "name": "Invented 60 minute subject " + str(index),
                    "provenance": "synthetic",
                    "program_ids": [program],
                    "required_weekly_minutes": 60,
                    "patterns": [{"id": "single-60", "durations": [60]}],
                },
                {
                    "kind": "sections",
                    "id": identities["section"],
                    "period_id": period_id,
                    "program_id": program,
                    "custom_label": "Invented group " + str(index),
                    "population": students_per_offering,
                    "population_verified": True,
                },
                {
                    "kind": "faculty",
                    "id": identities["teacher"],
                    "name": "Invented faculty " + identities["teacher"],
                    "subject_ids": [subject],
                    "availability": [dict(WINDOW)],
                },
                {
                    "kind": "resources",
                    "id": identities["room"],
                    "name": "Invented room " + identities["room"],
                    "building": "Synthetic qualification facility",
                    "source": "synthetic",
                    "schedulable": True,
                    "condition": "operational",
                    "capacity": students_per_offering,
                    "capacity_verified": True,
                    "availability": [dict(WINDOW)],
                    "verification_note": "Invented test assertion; no institutional room data.",
                },
                {
                    "kind": "offerings",
                    "id": offering,
                    "subject_id": subject,
                    "section_id": identities["section"],
                    "teacher_ids": [identities["teacher"]],
                    "room_ids": [identities["room"]],
                },
            ]
        )
        for student in range(students_per_offering):
            identity = (
                identities["student"]
                if students_per_offering == 1
                else (identities["student"] + "-" + str(student))
            )
            enrollments.append({"student_id": identity, "offering_ids": [offering]})
    records.append(
        {
            "kind": "constraints",
            "id": "rules",
            "operating_windows": [dict(WINDOW)],
            "all_intended_offerings_supplied": True,
            "enrollments": enrollments,
        }
    )
    return records


def build_period(
    academic, label, *, count=1, students_per_offering=1, shared_ids=None, calendar=None
):
    """Persist normal Academic writes; reusable fixture capacity is not scale acceptance."""
    definitions = record_definitions(
        "pending",
        label,
        count=count,
        students_per_offering=students_per_offering,
        shared_ids=shared_ids,
    )
    calendar = (
        fixture_calendar()
        if calendar is None
        else AcademicCalendar.model_validate(calendar.model_dump())
    )
    snapshot = academic.create_period(
        PeriodCreate(
            title="Generated resource matrix " + label, include_cdm_catalog=False, calendar=calendar
        )
    )
    for definition in definitions:
        if definition["kind"] == "sections":
            definition = definition | {"period_id": snapshot.period.id}
        revision = next(
            (
                entry.revision
                for entry in snapshot.records
                if entry.record.kind == definition["kind"] and entry.record.id == definition["id"]
            ),
            0,
        )
        body = RecordWrite.model_validate({"expected_revision": revision, "record": definition})
        snapshot = academic.save(snapshot.period.id, body.record.kind, body.record.id, body)
    return snapshot


def conflict_identities(draft):
    inputs = draft.input_snapshot
    return {
        "room": {room.id for room in inputs.rooms},
        "teacher": {teacher.id for teacher in inputs.teachers},
        "section": {section.id for section in inputs.sections},
        "student": {enrollment.student_id for enrollment in inputs.enrollments},
    }


def assert_isolated_conflict(base, candidate, kind):
    require(kind in {*KINDS, None}, "Unknown isolated resource conflict")
    left, right = conflict_identities(base), conflict_identities(candidate)
    for resource in KINDS:
        common = left[resource] & right[resource]
        require(
            len(common) == (1 if resource == kind else 0),
            "Resource fixture shares unintended conflict identities: " + resource,
        )
    for draft in (base, candidate):
        require(
            all(
                teacher.max_daily_minutes is None and teacher.max_weekly_minutes is None
                for teacher in draft.input_snapshot.teachers
            ),
            "Workload cap would mask the isolated resource conflict",
        )
        events = dated_occurrences(
            draft.input_snapshot,
            draft.generation_result.assignments,
            fixture_calendar(),
            date(2026, 10, 5),
            date(2026, 10, 5),
        )
        require(
            len(events) == 1
            and events[0]["starts_at"] == "2026-10-05T08:00:00+08:00"
            and events[0]["ends_at"] == "2026-10-05T09:00:00+08:00",
            "Real solver did not produce the forced single-window occurrence",
        )


def exact_conflict(operation, kind):
    require(kind in KINDS, "Unknown isolated resource conflict")
    try:
        operation()
    except DraftError as error:
        require(
            error.status == 422
            and error.code == "publication_conflict"
            and str(error).startswith(kind.title() + " conflict between "),
            "Wrong isolated publication conflict: " + str(error),
        )
    else:
        raise RuntimeError("Isolated publication conflict unexpectedly succeeded")


def command_for(draft, snapshot, label):
    return PublicationCommand(
        draft_id=draft.id,
        dataset="synthetic",
        expected_version=0,
        expected_academic_revision=snapshot.period.revision,
        idempotency_key="resource-matrix-" + label,
        calendar=snapshot.period.calendar,
    )


def exercise(connection):
    root = checked_connection(connection)
    owner, runtime = engine_for(connection, bootstrap=True), None
    try:
        runtime = bounded_runtime(connection)
        check_pool(runtime)
        with transaction(owner) as db:
            verify_fresh_target(db, connection, root)
        _unused_first, _unused_other, migrator = prepare_source(connection, owner, runtime)
        authorize_grants(connection, owner, migrator)
        academic, publication = academic_store(runtime), repository(runtime)
        base_snapshot = build_period(academic, "matrix-base")
        base = saved_draft(runtime, base_snapshot)
        base_command = command_for(base, base_snapshot, "base")
        receipt = publication.publish(base_command, commit=True)
        require(
            receipt["revision"] == 1 and receipt["status"] == "published",
            "Base period did not publish",
        )
        identities = conflict_identities(base)
        results = []
        for kind in KINDS:
            snapshot = build_period(
                academic, "matrix-" + kind, shared_ids={kind: next(iter(identities[kind]))}
            )
            draft = saved_draft(runtime, snapshot)
            assert_isolated_conflict(base, draft, kind)
            before = state(owner)
            command = command_for(draft, snapshot, kind)
            exact_conflict(lambda command=command: publication.publish(command, commit=True), kind)
            require(state(owner) == before, "Rejected resource conflict changed Scheduling state")
            require(
                publication.publish(base_command, commit=True) == receipt,
                "Rejected conflict changed the base immutable receipt",
            )
            results.append(
                {
                    "kind": kind,
                    "solver_status": draft.solver_status,
                    "exact_422_publication_conflict": True,
                    "all_six_scheduling_tables_unchanged": True,
                }
            )
        control_snapshot = build_period(academic, "matrix-control")
        control = saved_draft(runtime, control_snapshot)
        assert_isolated_conflict(base, control, None)
        before = state(owner)
        control_receipt = publication.publish(
            command_for(control, control_snapshot, "control"), commit=True
        )
        after = state(owner)
        require(
            control_receipt["revision"] == 1
            and control_receipt["status"] == "published"
            and len(after["published_versions"]) == len(before["published_versions"]) + 1
            and len(after["publication_heads"]) == len(before["publication_heads"]) + 1
            and all(row in after["published_versions"] for row in before["published_versions"])
            and all(row in after["publication_heads"] for row in before["publication_heads"])
            and all(
                after[table] == before[table]
                for table in ("solver_runs", "drafts", "room_restrictions", "restriction_audit")
            )
            and publication.publish(base_command, commit=True) == receipt,
            "Nonconflicting control changed existing durable state",
        )
        return {
            "migration": MIGRATION,
            "base_solver_status": base.solver_status,
            "actual_durable_resource_matrix": results,
            "same_time_disjoint_resource_control": True,
            "control_solver_status": control.solver_status,
            "final_scheduling_state_sha256": digest(encode(after)),
            "limitations": [
                "Synthetic generated records only",
                "No scale acceptance",
                "No conflicting restriction/publication winner matrix",
                "No provider/HTTP/browser, approval or outbox acceptance",
            ],
            "full_p3b": False,
            "production_acceptance": False,
        }
    finally:
        if runtime is not None:
            runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(
        not args.output.exists() and not args.output.is_symlink() and args.output.parent.is_dir(),
        "New output required",
    )
    write_new_evidence(args.output, qualify(args.bin, exercise))
    print("Generated publication resource matrix passed; owned PostgreSQL stopped")


if __name__ == "__main__":
    main()
