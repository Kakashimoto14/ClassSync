"""Two conflicting real writers, both orderings, in a new generated-only PG cluster."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Event
from unittest.mock import patch

from classync_contracts.publication import PublicationCommand, RoomRestriction
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
    must_fail,
    repository,
    saved_draft,
    state,
    verify_fresh_target,
    wait_for_locks,
)
from scripts.postgres_publication_resource_qualification import build_period, fixture_calendar
from scripts.postgres_web_session_qualification import write_new_evidence
from services.scheduling.app.draft_rules import DraftError, digest, encode
from services.scheduling.app.occurrences import dated_occurrences

ORDERS = ("publication", "restriction")


def proposals(draft, snapshot, label):
    calendar = snapshot.period.calendar
    first = calendar.model_copy(update={"effective_end": date(2026, 10, 5)})
    second = calendar.model_copy(update={"effective_start": date(2026, 10, 12)})
    # Revalidate dates rather than trusting unchecked model_copy updates.
    first, second = (type(calendar).model_validate(item.model_dump()) for item in (first, second))
    common = {"draft_id": draft.id, "dataset": "synthetic",
              "expected_academic_revision": snapshot.period.revision}
    baseline = PublicationCommand(**common, expected_version=0,
                                  idempotency_key="conflicting-baseline-" + label, calendar=first)
    candidate = PublicationCommand(**common, expected_version=1,
                                   idempotency_key="conflicting-candidate-" + label,
                                   calendar=second)
    events = dated_occurrences(draft.input_snapshot, draft.generation_result.assignments, second,
                              date(2026, 10, 12), date(2026, 10, 12))
    require(len(events) == 1 and events[0]["starts_at"] == "2026-10-12T08:00:00+08:00"
            and events[0]["ends_at"] == "2026-10-12T09:00:00+08:00",
            "Actual candidate is not the fixed conflicting October12 occurrence")
    restriction = RoomRestriction(id="conflicting-room-" + label, room_id=events[0]["room"]["id"],
                                  dataset="synthetic", starts_at=events[0]["starts_at"],
                                  ends_at=events[0]["ends_at"], kind="reservation",
                                  reason="Invented mutually exclusive writer qualification",
                                  expected_revision=0)
    return baseline, candidate, restriction


def attempt(operation):
    try:
        return {"ok": True, "value": operation()}
    except DraftError as error:
        return {"ok": False, "status": error.status, "code": error.code}


def assert_outcomes(first_writer, publication, restriction):
    require(first_writer in ORDERS, "Unknown conflicting writer ordering")
    winner = publication if first_writer == "publication" else restriction
    loser = restriction if first_writer == "publication" else publication
    expected = {"ok": False, "status": 409, "code": "restriction_publication_conflict"}
    if first_writer == "restriction":
        expected = {"ok": False, "status": 422, "code": "room_restricted"}
    require(winner.get("ok") is True and loser == expected,
            "Conflicting writers did not have the exact expected winner and rejection")


def assert_transition(before, after, first_writer, candidate, restriction_body, result):
    require(first_writer in ORDERS, "Unknown conflicting writer ordering")
    for table in ("solver_runs", "drafts"):
        require(after[table] == before[table], "Conflicting writers changed private snapshots")
    if first_writer == "publication":
        receipt = result["value"]
        require(receipt["status"] == "published" and receipt["revision"] == 2,
                "Winning publication did not commit revision two")
        old_versions = before["published_versions"]
        new_versions = after["published_versions"]
        added = [row for row in new_versions if row not in old_versions]
        require(len(new_versions) == len(old_versions) + 1
                and all(row in new_versions for row in old_versions) and len(added) == 1
                and added[0]["id"] == receipt["id"]
                and added[0]["idempotency_key"] == candidate.idempotency_key,
                "Winning publication changed immutable history or command binding")
        target = receipt["period_id"]
        expected_heads = [row | {"revision": 2} if row["period_id"] == target else row
                          for row in before["publication_heads"]]
        require(after["publication_heads"] == expected_heads,
                "Winning publication changed another head")
        require(all(after[table] == before[table]
                    for table in ("room_restrictions", "restriction_audit"))
                and not any(row["id"] == restriction_body.id for row in after["room_restrictions"]),
                "Losing restriction left a row or audit")
    else:
        require(after["published_versions"] == before["published_versions"]
                and after["publication_heads"] == before["publication_heads"]
                and not any(row["idempotency_key"] == candidate.idempotency_key
                            for row in after["published_versions"]),
                "Losing publication left a version, head or key binding")
        value = result["value"]
        old = before["room_restrictions"]
        new = after["room_restrictions"]
        added = [row for row in new if row not in old]
        require(len(new) == len(old) + 1 and all(row in new for row in old)
                and len(added) == 1 and added[0]["id"] == restriction_body.id
                and added[0]["revision"] == value["revision"] == 1
                and json.loads(added[0]["payload"]) == value
                and digest(added[0]["payload"]) == added[0]["checksum"],
                "Winning restriction changed another row or failed exact persistence")
        old_audit, new_audit = before["restriction_audit"], after["restriction_audit"]
        added_audit = [row for row in new_audit if row not in old_audit]
        require(len(new_audit) == len(old_audit) + 1 and all(row in new_audit for row in old_audit)
                and len(added_audit) == 1 and added_audit[0]["id"] == restriction_body.id
                and added_audit[0]["old_snapshot"] is None
                and added_audit[0]["new_snapshot"] == added[0]
                and added_audit[0]["actor_uid"] == "uid-admin",
                "Winning restriction did not commit exactly one linked audit snapshot")


def run_order(connection, owner, runtime, academic, first_writer):
    require(first_writer in ORDERS, "Unknown conflicting writer ordering")
    label = "conflict-" + first_writer
    calendar = fixture_calendar().model_copy(update={"effective_end": date(2026, 10, 12)})
    snapshot = build_period(academic, label, calendar=calendar)
    draft = saved_draft(runtime, snapshot)
    baseline, candidate, restriction_body = proposals(draft, snapshot, label)
    pub_repo, room_repo = repository(runtime), repository(runtime)
    baseline_receipt = pub_repo.publish(baseline, commit=True)
    require(baseline_receipt["revision"] == 1, "Baseline did not publish revision one")
    require(pub_repo.publish(candidate, commit=False)["status"] == "ready-for-review",
            "Candidate was not independently valid before the conflicting reservation")
    current = pub_repo.admin_calendar("synthetic", snapshot.period.id,
                                      date(2026, 10, 12), date(2026, 10, 12))
    require(current["occurrences"] == [], "Restriction target was already published")
    before = state(owner)
    entered, release = Event(), Event()
    hooked = pub_repo if first_writer == "publication" else room_repo
    method = "review_scope" if first_writer == "publication" else "expanded"
    real_method = getattr(hooked, method)
    paused = False

    def delegate_then_pause(*args, **kwargs):
        nonlocal paused
        value = real_method(*args, **kwargs)
        if not paused:
            paused = True
            entered.set()
            require(release.wait(timeout=2.5), "Conflicting writer observation gate timed out")
        return value

    def publication():
        return attempt(lambda: pub_repo.publish(candidate, commit=True))

    def restriction():
        return attempt(lambda: room_repo.put_restriction(restriction_body))

    with patch.object(hooked, method, side_effect=delegate_then_pause), ThreadPoolExecutor(
        max_workers=2
    ) as pool:
        first = pool.submit(publication if first_writer == "publication" else restriction)
        try:
            require(entered.wait(timeout=3), "First real writer did not reach validation hook")
            second = pool.submit(restriction if first_writer == "publication" else publication)
            observed = wait_for_locks(owner, runtime=connection.runtime, count=1)
            require(not first.done() and not second.done(), "Conflicting writer did not wait")
        finally:
            release.set()
        first_result, second_result = first.result(timeout=20), second.result(timeout=20)
    pub_result, restriction_result = ((first_result, second_result)
                                      if first_writer == "publication"
                                      else (second_result, first_result))
    assert_outcomes(first_writer, pub_result, restriction_result)
    after = state(owner)
    winner = pub_result if first_writer == "publication" else restriction_result
    assert_transition(before, after, first_writer, candidate, restriction_body, winner)
    require(pub_repo.publish(baseline, commit=True) == baseline_receipt,
            "Conflicting race changed the immutable baseline replay receipt")
    if first_writer == "publication":
        require(pub_repo.publish(candidate, commit=True) == pub_result["value"],
                "Winning publication did not replay exactly")
        must_fail(lambda: room_repo.put_restriction(restriction_body),
                  "restriction_publication_conflict", 409)
    else:
        must_fail(lambda: pub_repo.publish(candidate, commit=True), "room_restricted", 422)
        must_fail(lambda: room_repo.put_restriction(restriction_body),
                  "restriction_version_conflict", 409)
    require(state(owner) == after, "Winner replay or loser retry changed durable state")
    return {"first_writer": first_writer, "solver_status": draft.solver_status,
            "observed_lock_waiters": observed, "winner": first_writer,
            "loser": restriction_result if first_writer == "publication" else pub_result,
            "only_exact_winner_rows_changed": True, "loser_identity_or_key_absent": True,
            "baseline_and_winning_publication_replay_exact": True,
            "loser_and_stale_restriction_retries_no_write": True,
            "final_scheduling_state_sha256": digest(encode(after))}


def exercise(connection):
    root = checked_connection(connection)
    owner, runtime = engine_for(connection, bootstrap=True), None
    try:
        runtime = bounded_runtime(connection)
        check_pool(runtime)
        with transaction(owner) as db:
            verify_fresh_target(db, connection, root)
        _first, _other, migrator = prepare_source(connection, owner, runtime)
        authorize_grants(connection, owner, migrator)
        academic = academic_store(runtime)
        outcomes = [run_order(connection, owner, runtime, academic, order) for order in ORDERS]
        return {"migration": MIGRATION, "actual_conflicting_writer_orders": outcomes,
                "validation_and_solver_results_replaced": False,
                "limitations": ["Synthetic generated records only", "No scale acceptance",
                                "No provider/HTTP/browser, approval or outbox acceptance",
                                "No old publication history migration or restore"],
                "full_p3b": False, "production_acceptance": False}
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
    print("Generated conflicting publication writers passed; owned PostgreSQL stopped")


if __name__ == "__main__":
    main()
