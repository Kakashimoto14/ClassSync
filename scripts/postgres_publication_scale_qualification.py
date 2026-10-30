"""Representative generated publication workload on a new guarded local cluster."""

import argparse
from datetime import date
from pathlib import Path
from time import perf_counter

from classync_contracts.calendar import AcademicCalendar
from classync_contracts.publication import RoomRestriction
from classync_persistence.database import transaction

from scripts.postgres_academic_restore_qualification import prepare_source
from scripts.postgres_academic_restore_qualification import store as academic_store
from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_publication_repository_qualification import (
    authorize_grants,
    bounded_runtime,
    checked_connection,
    publish_command,
    repository,
    saved_draft,
    state,
    verify_fresh_target,
)
from scripts.postgres_publication_resource_qualification import build_period
from scripts.postgres_web_session_qualification import write_new_evidence


def exercise(connection):
    root = checked_connection(connection)
    owner, runtime = engine_for(connection, bootstrap=True), None
    timings = {}

    def measured(label, operation, *, bounded=True):
        began = perf_counter()
        result = operation()
        timings[label] = perf_counter() - began
        require(not bounded or timings[label] < 15,
                f"Local 15s operation envelope exceeded: {label}")
        return result

    try:
        runtime = bounded_runtime(connection)
        with transaction(owner) as db:
            verify_fresh_target(db, connection, root)
        _, _, migrator = prepare_source(connection, owner, runtime)
        authorize_grants(connection, owner, migrator)
        calendar = AcademicCalendar(academic_year="2026-2027", semester="first",
            effective_start=date(2026, 10, 5), effective_end=date(2026, 12, 28))
        # A generated 100-offering/3,000-enrollment trial consumed several CPU
        # minutes in repeated academic snapshot validation before reaching output.
        # Keep this local regression bounded while retaining multi-period occurrences.
        offerings, students_per_offering = 25, 10
        snapshot = measured("academic_fixture", lambda: build_period(academic_store(runtime),
            "scale", count=offerings, students_per_offering=students_per_offering,
            calendar=calendar), bounded=False)
        draft = measured("solver_and_draft", lambda: saved_draft(runtime, snapshot), bounded=False)
        require(len(draft.generation_result.assignments) == offerings
                and len(draft.input_snapshot.enrollments) == offerings * students_per_offering,
                "Wrong scale fixture")
        repo = repository(runtime)
        command = publish_command(draft, snapshot)
        before = state(owner)
        review = measured("review", lambda: repo.publish(command, commit=False))
        occurrence_count = offerings * 13
        require(review["occurrences"] == occurrence_count and state(owner) == before,
                "Scale review count or no-write invariant failed")
        receipt = measured("publish", lambda: repo.publish(command, commit=True))
        immutable = state(owner)
        view = measured("projection", lambda: repo.admin_calendar(command.dataset,
            snapshot.period.id, date(2026, 10, 5), date(2026, 12, 6)))
        require(len(view["occurrences"]) == offerings * 9, "Scale projection lost occurrences")
        require(measured("replay", lambda: repo.publish(command, commit=True)) == receipt,
                "Scale replay changed receipt")
        runtime.dispose()
        require(measured("reconnect_replay", lambda: repo.publish(command, commit=True)) == receipt
                and state(owner) == immutable, "Scale reconnect mutated immutable state")
        for index, room in enumerate(draft.input_snapshot.rooms):
            body = RoomRestriction(id=f"generated-scale-{index}", dataset=command.dataset,
                kind="reservation", expected_revision=0,
                room_id=room.id, starts_at="2026-10-06T08:00:00+08:00",
                ends_at="2026-10-06T09:00:00+08:00", reason="Generated non-teaching reservation")
            measured(f"restriction_{index}", lambda b=body: repo.put_restriction(b))
        after = state(owner)
        require(len(after["room_restrictions"]) == len(after["restriction_audit"]) == offerings,
                "Scale restriction audit count differs")
        for table in ("solver_runs", "drafts", "published_versions", "publication_heads"):
            require(after[table] == immutable[table], "Restrictions changed published state")
        final_review = measured("review_with_restrictions", lambda: repo.publish(
            command.model_copy(update={"idempotency_key": "scale-review-after-restrictions",
                                       "expected_version": 1}), commit=False), bounded=False)
        require(final_review["occurrences"] == occurrence_count,
                "Restrictions changed the validated occurrence count")
        return {"offerings": offerings, "student_enrollments": offerings * students_per_offering,
                "published_occurrences": occurrence_count, "projected_occurrences": offerings * 9,
                "restrictions_and_audits": offerings,
                "solver_status": draft.solver_status, "seconds": timings,
                "local_operation_envelope_seconds": 15, "production_scale_acceptance": False}
    finally:
        if runtime is not None:
            runtime.dispose()
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and not args.output.is_symlink()
            and args.output.parent.is_dir(), "New output required")
    write_new_evidence(args.output, qualify(args.bin, exercise))
    print("Representative publication workload passed; owned cluster stopped")


if __name__ == "__main__":
    main()
