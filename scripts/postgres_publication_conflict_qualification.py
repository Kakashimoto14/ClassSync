"""Actual two-direction PostgreSQL publication/restriction conflict qualification.

Only fresh guarded disposable clusters are accepted. Academic records are generated
synthetic test inputs, and each saved draft is produced by the actual CP-SAT engine.
"""

import argparse
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Event
from unittest.mock import patch

from classync_contracts.academic import (
    AcademicConstraints,
    AcademicFaculty,
    AcademicOffering,
    AcademicProgram,
    AcademicResource,
    AcademicSection,
    AcademicSubject,
    PeriodCreate,
    RecordWrite,
)
from classync_contracts.calendar import AcademicCalendar
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.publication import PublicationCommand, RoomRestriction
from classync_contracts.scheduling import SaveDraftRequest, SessionPattern, Window
from classync_persistence.database import postgres_engine, transaction
from sqlalchemy.engine import URL

from scripts.postgres_academic_restore_qualification import prepare_source
from scripts.postgres_academic_restore_qualification import store as academic_store
from scripts.postgres_disposable import checked_root, qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_publication_repository_qualification import (
    MIGRATION,
    authorize_grants,
    repository,
    state,
    verify_fresh_target,
    wait_for_locks,
)
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_rules import DraftError, verified_result
from services.scheduling.app.engine import generate_week
from services.scheduling.app.postgres_draft_repository import PostgresDraftRepository

WINDOW = Window(day=0, start=480, end=510)
BASELINE_DATE = date(2026, 10, 5)
FUTURE_DATE = date(2026, 10, 12)
TABLES = (
    "solver_runs",
    "drafts",
    "published_versions",
    "publication_heads",
    "room_restrictions",
    "restriction_audit",
)


def bounded_runtime(connection):
    parameters = connection.parameters()
    url = URL.create(
        "postgresql+psycopg",
        username=parameters["user"],
        host=parameters["host"],
        port=parameters["port"],
        database=parameters["dbname"],
    )
    return postgres_engine(
        url, connect_args=parameters, pool_size=5, max_overflow=0, pool_timeout=3
    )


def create_period_and_draft(runtime, *, suffix):
    academic = academic_store(runtime)
    calendar = AcademicCalendar(
        academic_year="2026-2027",
        semester="first",
        effective_start=BASELINE_DATE,
        effective_end=FUTURE_DATE,
        instructional_days=[0],
    )
    snapshot = academic.create_period(
        PeriodCreate(
            title=f"Synthetic conflict qualification {suffix}",
            include_cdm_catalog=False,
            calendar=calendar,
        )
    )
    period_id = snapshot.period.id
    records = [
        AcademicProgram(
            id=f"conflict-program-{suffix}", acronym="TST", name="Generated test program",
            institute="Generated test institute", allowed_year_levels=[1],
        ),
        AcademicSubject(
            id=f"conflict-subject-{suffix}", code=f"TEST-{suffix}",
            name="Generated 30-minute class", program_ids=[f"conflict-program-{suffix}"],
            required_weekly_minutes=30,
            patterns=[SessionPattern(id="one-30", durations=[30])],
            provenance="synthetic",
        ),
        AcademicSection(
            id=f"conflict-section-{suffix}", period_id=period_id,
            program_id=f"conflict-program-{suffix}", year_level=1, section_letter="A",
            population=10, population_verified=True,
        ),
        AcademicFaculty(
            id=f"conflict-teacher-{suffix}", name="Generated test instructor",
            subject_ids=[f"conflict-subject-{suffix}"], availability=[WINDOW],
            max_weekly_minutes=30, max_daily_minutes=30,
        ),
        AcademicResource(
            id=f"conflict-room-{suffix}", name="Generated test room",
            building="Generated test building", source="synthetic", schedulable=True,
            condition="operational", capacity=10, capacity_verified=True,
            availability=[WINDOW], verification_note="Disposable generated test fixture",
        ),
        AcademicOffering(
            id=f"conflict-offering-{suffix}", subject_id=f"conflict-subject-{suffix}",
            section_id=f"conflict-section-{suffix}", teacher_ids=[f"conflict-teacher-{suffix}"],
            room_ids=[f"conflict-room-{suffix}"],
        ),
    ]
    for record in records:
        snapshot = academic.save(
            period_id, record.kind, record.id,
            RecordWrite(expected_revision=0, record=record),
        )
    constraints = next(item for item in snapshot.records if item.record.kind == "constraints")
    snapshot = academic.save(
        period_id,
        "constraints",
        constraints.record.id,
        RecordWrite(
            expected_revision=constraints.revision,
            record=AcademicConstraints(
                operating_windows=[WINDOW], all_intended_offerings_supplied=True
            ),
        ),
    )
    readiness = academic_readiness(snapshot)
    require(readiness.ready and readiness.inputs is not None,
            "Generated one-offering academic period is not ready")
    inputs = readiness.inputs
    require(inputs.synthetic and len(inputs.offerings) == 1,
            "Conflict fixture must be one generated synthetic offering")
    result = generate_week(inputs)
    verified_result(inputs, result)
    require(result.solver_status in {"optimal", "feasible"}
            and result.validation is not None and result.validation.valid
            and len(result.assignments) == 1
            and result.assignments[0].day == 0
            and result.assignments[0].start == 480
            and result.assignments[0].end == 510,
            "Actual CP-SAT did not produce the exact Monday 08:00–08:30 session")
    drafts = PostgresDraftRepository(
        runtime,
        tenant_id="tenant-a",
        firebase_project_id="synthetic-project",
        principal=VerifiedPrincipal(uid="uid-admin"),
    )
    drafts.remember_run(inputs, result)
    draft, created = drafts.save(
        SaveDraftRequest(
            run_id=result.run_id,
            input_hash=result.input_hash,
            title=f"Generated conflict draft {suffix}",
            idempotency_key=f"conflict-save-{suffix}-0001",
        )
    )
    require(created and drafts.get(draft.id) == draft,
            "Generated immutable conflict draft did not round-trip")
    return snapshot, draft


def command(snapshot, draft, *, suffix, revision, through_future):
    calendar = snapshot.period.calendar.model_copy(deep=True)
    calendar.effective_start = BASELINE_DATE
    calendar.effective_end = FUTURE_DATE if through_future else BASELINE_DATE
    calendar.phases = []
    return PublicationCommand(
        draft_id=draft.id,
        dataset="synthetic",
        expected_version=revision,
        expected_academic_revision=snapshot.period.revision,
        idempotency_key=f"conflict-publish-{suffix}-{revision + 1:04d}",
        calendar=calendar,
    )


def restriction(room_id, *, suffix):
    return RoomRestriction(
        id=f"future-monday-{suffix}",
        room_id=room_id,
        dataset="synthetic",
        starts_at="2026-10-12T08:00:00+08:00",
        ends_at="2026-10-12T09:00:00+08:00",
        kind="reservation",
        reason="Generated race acceptance interval",
        expected_revision=0,
    )


def invoke(operation):
    try:
        return {"outcome": "success", "value": operation()}
    except DraftError as error:
        return {"outcome": "denied", "status": error.status, "code": error.code}


def publication_winner_transition(before, after, *, period_id, key, version_id):
    for table in TABLES:
        if table not in {"published_versions", "publication_heads"}:
            require(after[table] == before[table],
                    f"Losing restriction altered unexpected {table} rows")
    old_versions, new_versions = before["published_versions"], after["published_versions"]
    require(len(new_versions) == len(old_versions) + 1
            and all(row in new_versions for row in old_versions),
            "Winning publication did not append exactly one immutable version")
    added = [row for row in new_versions if row not in old_versions]
    require(len(added) == 1 and added[0]["id"] == version_id
            and added[0]["idempotency_key"] == key and added[0]["revision"] == 2,
            "Winning publication version or idempotency key differs from its command")
    old_heads, new_heads = before["publication_heads"], after["publication_heads"]
    require(len(old_heads) == len(new_heads) == 1
            and new_heads[0] == old_heads[0] | {"revision": 2}
            and old_heads[0]["period_id"] == period_id,
            "Winning publication did not advance only its existing head from one to two")


def restriction_winner_transition(before, after, *, restriction_id, room_id):
    for table in TABLES:
        if table not in {"room_restrictions", "restriction_audit"}:
            require(after[table] == before[table],
                    f"Losing publication altered unexpected {table} rows or inserted its key")
    old_restrictions, new_restrictions = before["room_restrictions"], after["room_restrictions"]
    require(len(new_restrictions) == len(old_restrictions) + 1
            and all(row in new_restrictions for row in old_restrictions),
            "Winning restriction did not append exactly one revision")
    added = [row for row in new_restrictions if row not in old_restrictions]
    require(len(added) == 1 and added[0]["id"] == restriction_id
            and added[0]["room_id"] == room_id and added[0]["revision"] == 1,
            "Winning restriction differs from the requested revision")
    old_audits, new_audits = before["restriction_audit"], after["restriction_audit"]
    require(len(new_audits) == len(old_audits) + 1
            and all(row in new_audits for row in old_audits),
            "Winning restriction did not append exactly one audit row")
    audits = [row for row in new_audits if row not in old_audits]
    require(len(audits) == 1 and audits[0]["id"] == restriction_id
            and audits[0]["revision"] == 1 and audits[0]["old_snapshot"] is None,
            "Winning restriction audit does not match its initial write")


def publish_wins(runtime, owner, snapshot, draft, suffix):
    pub = repository(runtime)
    rooms = repository(runtime)
    baseline = command(snapshot, draft, suffix=suffix, revision=0, through_future=False)
    initial = pub.publish(baseline, commit=True)
    require(initial["revision"] == 1, "Oct 5 baseline publication did not commit revision one")
    candidate = command(snapshot, draft, suffix=suffix, revision=1, through_future=True)
    body = restriction(f"conflict-room-{suffix}", suffix=suffix)
    before = state(owner)
    entered, release = Event(), Event()
    actual_review = pub.review_scope
    first_review = True

    def reviewed_then_pause(*args, **kwargs):
        nonlocal first_review
        value = actual_review(*args, **kwargs)
        if first_review:
            first_review = False
            require(value["occurrences"] == 2,
                    "Held publication review did not validate both Oct 5 and Oct 12")
            entered.set()
            require(release.wait(timeout=4), "Publication-first race gate timed out")
        return value

    def publish():
        return invoke(lambda: pub.publish(candidate, commit=True))

    def add_restriction():
        return invoke(lambda: rooms.put_restriction(body))

    with patch.object(pub, "review_scope", side_effect=reviewed_then_pause):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(publish)
            try:
                require(entered.wait(timeout=5),
                        "Publication did not reach completed real review")
                second = pool.submit(add_restriction)
                wait_for_locks(owner, runtime=runtime.url.username, count=1)
                require(not first.done() and not second.done(),
                        "Restriction did not wait behind the held publication transaction")
            finally:
                release.set()
            publication_result = first.result(timeout=20)
            restriction_result = second.result(timeout=20)
    require(publication_result["outcome"] == "success"
            and publication_result["value"]["revision"] == 2,
            "Held future-dated publication did not win revision two")
    require(restriction_result == {"outcome": "denied", "status": 409,
                                   "code": "restriction_publication_conflict"},
            "Restriction loser did not return the precise published-occupancy conflict")
    after = state(owner)
    publication_winner_transition(
        before, after, period_id=snapshot.period.id, key=candidate.idempotency_key,
        version_id=publication_result["value"]["id"],
    )
    require(pub.history("synthetic", snapshot.period.id)[0]["revision"] == 2,
            "Publication-first race winner is absent from current history")
    return {"publication_won": True, "publication_revision": 2,
            "restriction_loser": "restriction_publication_conflict/409",
            "observed_post_review_lock_waiter": True,
            "loser_left_no_restriction_or_audit_or_key": True}


def restriction_wins(runtime, owner, snapshot, draft, suffix):
    pub = repository(runtime)
    rooms = repository(runtime)
    baseline = command(snapshot, draft, suffix=suffix, revision=0, through_future=False)
    initial = pub.publish(baseline, commit=True)
    require(initial["revision"] == 1, "Independent Oct 5 baseline did not commit revision one")
    candidate = command(snapshot, draft, suffix=suffix, revision=1, through_future=True)
    body = restriction(f"conflict-room-{suffix}", suffix=suffix)
    before = state(owner)
    entered, release = Event(), Event()
    actual_expand = rooms.expanded
    first_expansion = True

    def expanded_then_pause(*args, **kwargs):
        nonlocal first_expansion
        events = actual_expand(*args, **kwargs)
        if first_expansion:
            first_expansion = False
            entered.set()
            require(release.wait(timeout=4), "Restriction-first race gate timed out")
        return events

    def publish():
        return invoke(lambda: pub.publish(candidate, commit=True))

    def add_restriction():
        return invoke(lambda: rooms.put_restriction(body))

    with patch.object(rooms, "expanded", side_effect=expanded_then_pause):
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(add_restriction)
            try:
                require(entered.wait(timeout=5),
                        "Restriction did not reach completed real published-scope expansion")
                second = pool.submit(publish)
                wait_for_locks(owner, runtime=runtime.url.username, count=1)
                require(not first.done() and not second.done(),
                        "Publication did not wait behind the held restriction transaction")
            finally:
                release.set()
            restriction_result = first.result(timeout=20)
            publication_result = second.result(timeout=20)
    require(restriction_result["outcome"] == "success"
            and restriction_result["value"]["revision"] == 1,
            "Validated future reservation did not win revision one")
    require(publication_result == {"outcome": "denied", "status": 422,
                                   "code": "room_restricted"},
            "Publication loser did not return the precise overlapping-room restriction")
    after = state(owner)
    restriction_winner_transition(
        before, after, restriction_id=body.id, room_id=body.room_id
    )
    require(pub.history("synthetic", snapshot.period.id)[0]["revision"] == 1,
            "Rejected publication added an idempotency key or partial version")
    return {"restriction_won": True, "restriction_revision": 1,
            "publication_loser": "room_restricted/422",
            "observed_post_expansion_lock_waiter": True,
            "loser_left_no_publication_version_head_or_key": True}


def exercise(connection):
    root = checked_root(connection.root, Path(tempfile.gettempdir()))
    owner = engine_for(connection, bootstrap=True)
    runtime = None
    try:
        runtime = bounded_runtime(connection)
        require(runtime.pool.size() == 5 and runtime.pool._max_overflow == 0
                and runtime.pool.timeout() == 3,
                "Conflict qualification runtime pool is not bounded")
        with transaction(owner) as db:
            verify_fresh_target(db, connection, root)
        with prepare_only_source(connection, owner, runtime) as source:
            _baseline, pub_snapshot, pub_draft, restr_snapshot, restr_draft = source
            pub_winner = publish_wins(runtime, owner, pub_snapshot, pub_draft, "pubwins")
            restriction_winner = restriction_wins(
                runtime, owner, restr_snapshot, restr_draft, "restrwins"
            )
            return {
                "migration": MIGRATION,
                "actual_cp_sat_solver_statuses": [pub_draft.solver_status,
                                                   restr_draft.solver_status],
                "exact_occurrence": "Monday 2026-10-05 and 2026-10-12, 08:00–08:30 Asia/Manila",
                "race_orders": [pub_winner, restriction_winner],
                "all_six_scheduling_tables_compared_before_and_after": True,
                "authorization_and_guards": "inherited from current guarded migration setup",
                "full_p3b": False,
                "production_acceptance": False,
            }
    finally:
        if runtime is not None:
            runtime.dispose()
        owner.dispose()


class prepare_only_source:
    """Set up the exact reviewed 0008 test authorities, then add isolated periods."""

    def __init__(self, connection, owner, runtime):
        self.connection, self.owner, self.runtime = connection, owner, runtime

    def __enter__(self):
        _old_snapshot, _empty, migrator = prepare_source(
            self.connection, self.owner, self.runtime
        )
        authorize_grants(self.connection, self.owner, migrator)
        first = create_period_and_draft(self.runtime, suffix="pubwins")
        second = create_period_and_draft(self.runtime, suffix="restrwins")
        return _old_snapshot, first[0], first[1], second[0], second[1]

    def __exit__(self, *_exc):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists() and not args.output.is_symlink()
            and args.output.parent.is_dir(), "Choose a new output in an existing directory")
    write_new_evidence(args.output, qualify(args.bin, exercise))
    print("PostgreSQL publication conflict qualification passed; owned cluster stopped")


if __name__ == "__main__":
    main()
