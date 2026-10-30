"""Storage-free publication rule tests; no solver, database or service is started."""

import sqlite3
from datetime import date

import pytest
from classync_contracts.scheduling import (
    Assignment,
    DraftDetail,
    Enrollment,
    GenerationResult,
    RunMetadata,
    scheduling_input_hash,
)

from services.scheduling.app.draft_rules import DraftError, DraftSnapshot, digest, encode
from services.scheduling.app.publication_rules import PublicationRules, overlap
from services.scheduling.app.validation import validate_timetable
from services.scheduling.tests.test_calendar import configuration
from services.scheduling.tests.test_engine import tiny

STAMP = "2026-10-26T08:00:00+00:00"


@pytest.fixture(autouse=True)
def prohibit_database_and_solver(monkeypatch):
    from ortools.sat.python import cp_model

    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: pytest.fail("Opened database"))
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda *a, **k: pytest.fail("Solver ran"))


def publication_row(*, version=1, start="2026-10-01", period="period-a", offset=0,
                    multiple=False, dataset="institutional"):
    """Only invented unit data; placements pass the independent validator, never CP-SAT."""
    inputs = tiny(count=2 if multiple else 1)
    inputs.period_id = period
    # Exercise institutional projection shape without claiming institutional provenance.
    inputs.synthetic = dataset == "synthetic"
    if not inputs.synthetic:
        for room in inputs.rooms:
            room.source = "administrator-supplied"
    if multiple:
        other = inputs.teachers[0].model_copy(update={"id": "private-faculty"})
        inputs.teachers.append(other)
        inputs.offerings[1].eligible_teacher_ids = [other.id]
    inputs.enrollments = [Enrollment(student_id="linked-student", offering_ids=["test-0"])]
    if multiple:
        inputs.enrollments.append(
            Enrollment(student_id="private-student", offering_ids=["test-1"])
        )
    assignments = []
    for index, offering in enumerate(inputs.offerings):
        window = next(w for w in inputs.operating_windows if w.day == index * 2)
        assignments.append(Assignment(
            id=f"session-{index}", offering_id=offering.id, subject_id=offering.subject_id,
            section_id=offering.section_id, teacher_id=offering.eligible_teacher_ids[0],
            room_id=offering.eligible_room_ids[0], day=window.day,
            start=window.start + offset,
            end=window.start + offset + offering.required_weekly_minutes,
        ))
    validation = validate_timetable(inputs, assignments)
    assert validation.valid and validation.hard_conflict_count == 0, validation.model_dump()
    result = GenerationResult(
        run_id=f"manual-run-{version}", period_id=period, input_hash=scheduling_input_hash(inputs),
        data_version=inputs.data_version, solver_status="feasible", assignments=assignments,
        total_offerings_requested=len(inputs.offerings),
        total_offerings_scheduled=len(inputs.offerings), coverage=validation.coverage,
        hard_conflict_count=0, diagnostics=[], validation=validation,
        metadata=RunMetadata(solver="manually placed test fixture; solver not executed",
                             solver_version="not-run", seed=inputs.options.seed,
                             wall_time_seconds=0,
                             time_limit_seconds=inputs.options.time_limit_seconds),
    )
    metadata = {"id": f"draft-{version}", "title": "Invented publication rules fixture",
                "created_at": STAMP, "scope": "administrator", "owner": "synthetic-admin"}
    draft = DraftDetail(
        **DraftSnapshot().make_summary(inputs, result, metadata).model_dump(),
        input_snapshot=inputs, generation_result=result, validation=validation,
    )
    calendar = configuration().calendar.model_copy(update={
        "effective_start": date.fromisoformat(start), "effective_end": date(2026, 10, 31),
        "phases": [], "exceptions": [],
    })
    # Validate changed calendar fields instead of relying on model_copy's unchecked updates.
    calendar = type(calendar).model_validate(calendar.model_dump())
    payload = encode({"draft": draft.model_dump(mode="json"),
                      "calendar": calendar.model_dump(mode="json"),
                      "review": {"status": "ready-for-review"}})
    return {"id": f"version-{version}", "sequence": version, "revision": version,
            "period_id": period, "draft_id": draft.id, "tenant": "tenant-a",
            "dataset": dataset, "actor": "synthetic-admin", "created_at": STAMP,
            "payload": payload, "checksum": digest(payload)}


class MemoryRules(PublicationRules):
    """Explicit storage ports; filtering proves the arguments supplied by pure rules."""

    def __init__(self, rows):
        self.stored_rows = rows
        self.calls = []

    def rows(self, db, tenant, dataset, period):
        self.calls.append(("rows", db, tenant, dataset, period))
        return sorted([row for row in self.stored_rows
                       if row["tenant"] == tenant and row["dataset"] == dataset
                       and (period is None or row["period_id"] == period)],
                      key=lambda row: row["sequence"])

    def head(self, db, tenant, dataset, period):
        self.calls.append(("head", db, tenant, dataset, period))
        return max(row["revision"] for row in self.stored_rows
                   if row["tenant"] == tenant and row["dataset"] == dataset
                   and row["period_id"] == period)


def event(name, *, start="2026-10-05T08:00:00+08:00", end="2026-10-05T09:00:00+08:00",
          buffer=0):
    return {"id": name, "starts_at": start, "ends_at": end, "buffer": buffer,
            "room": {"id": f"room-{name}"}, "teacher": {"id": f"teacher-{name}"},
            "section": {"id": f"section-{name}"}, "students": [f"student-{name}"]}


def share(left, right, kind):
    if kind == "student":
        right["students"] = left["students"][:]
    else:
        right[kind] = dict(left[kind])


def test_constructor_and_import_require_no_database(monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: pytest.fail("Opened database"))
    from services.scheduling.app.publication_rules import PublicationRules

    rules = PublicationRules()
    assert callable(rules.decode) and callable(rules.expanded) and callable(rules.project)


def test_corrupt_publication_checksum_is_rejected_before_decoding():
    from services.scheduling.app.publication_rules import PublicationRules

    with pytest.raises(DraftError) as denied:
        PublicationRules().decode({"payload": "not valid JSON", "checksum": "different"})
    assert denied.value.status == 409
    assert denied.value.code == "publication_integrity"


def test_decode_round_trips_typed_draft_and_calendar():
    row = publication_row()
    result = PublicationRules().decode(row)
    assert isinstance(result["draft"], DraftDetail)
    assert result["draft"].generation_result.validation.valid
    assert result["calendar"].effective_start == date(2026, 10, 1)
    assert result["review"] == {"status": "ready-for-review"}


@pytest.mark.parametrize("operation", ["expanded", "project", "summary"])
def test_tampered_historical_snapshot_cannot_be_hidden_by_a_valid_later_revision(operation):
    first, second = publication_row(), publication_row(version=2, start="2026-10-19")
    first["payload"] += " "  # Still valid JSON, but no longer the checksummed publication.
    rules = MemoryRules([first, second])
    with pytest.raises(DraftError) as denied:
        if operation == "expanded":
            rules.expanded([first, second], date(2026, 10, 1), date(2026, 10, 31))
        elif operation == "project":
            rules.project(object(), "tenant-a", "institutional", "period-a",
                          date(2026, 10, 19), date(2026, 10, 31), {"role": "administrator"})
        else:
            rules.summary(first, object())
    assert (denied.value.status, denied.value.code) == (409, "publication_integrity")


@pytest.mark.parametrize("kind", ["room", "teacher", "section", "student"])
def test_each_resource_rejects_overlap_without_other_resource_contention(kind):
    left = event("a")
    right = event("b", start="2026-10-05T08:30:00+08:00")
    share(left, right, kind)
    assert overlap(left, right) and overlap(right, left)
    with pytest.raises(DraftError) as denied:
        PublicationRules().conflicts([right, left])
    assert (denied.value.status, denied.value.code) == (422, "publication_conflict")
    assert str(denied.value).startswith(kind.title() + " conflict")


@pytest.mark.parametrize("kind", ["room", "teacher", "section", "student"])
@pytest.mark.parametrize("buffers", [(30, 0), (0, 30)])
def test_transition_buffer_uses_stricter_of_both_sessions_for_each_resource(kind, buffers):
    left = event("a", buffer=buffers[0])
    right = event("b", start="2026-10-05T09:15:00+08:00",
                  end="2026-10-05T10:15:00+08:00", buffer=buffers[1])
    share(left, right, kind)
    assert not overlap(left, right)
    with pytest.raises(DraftError) as denied:
        PublicationRules().conflicts([left, right])
    assert denied.value.code == "publication_conflict"
    right["starts_at"] = "2026-10-05T09:30:00+08:00"
    PublicationRules().conflicts([left, right])


def test_touching_sessions_are_nonoverlapping_and_unrelated_overlaps_allowed():
    left, right = event("a"), event("b")
    PublicationRules().conflicts([left, right])
    for kind in ["room", "teacher", "section", "student"]:
        share(left, right, kind)
    right.update(starts_at=left["ends_at"], ends_at="2026-10-05T10:00:00+08:00")
    assert not overlap(left, right) and not overlap(right, left)
    PublicationRules().conflicts([right, left])


@pytest.mark.parametrize("limit,second_day", [("max_daily", "2026-10-05"),
                                             ("max_weekly", "2026-10-07")])
def test_combined_effective_workload_rejects_excess_without_any_overlap(limit, second_day):
    left = event("a")
    right = event("b", start=f"{second_day}T10:00:00+08:00",
                  end=f"{second_day}T11:00:00+08:00")
    share(left, right, "teacher")
    left[limit] = right[limit] = 90
    with pytest.raises(DraftError) as denied:
        PublicationRules().conflicts([left, right])
    assert (denied.value.status, denied.value.code) == (422, "publication_workload")
    left[limit] = right[limit] = 120
    PublicationRules().conflicts([left, right])


@pytest.mark.parametrize("limit,second_day", [("max_daily", "2026-10-05"),
                                             ("max_weekly", "2026-10-07")])
@pytest.mark.parametrize("second_cap", [120, None])
@pytest.mark.parametrize("reverse", [False, True])
def test_workload_enforces_every_supplied_cap_independent_of_event_order(
    limit, second_day, second_cap, reverse,
):
    left = event("a")
    right = event("b", start=f"{second_day}T10:00:00+08:00",
                  end=f"{second_day}T11:00:00+08:00")
    share(left, right, "teacher")
    left[limit], right[limit] = 90, second_cap
    events = [right, left] if reverse else [left, right]
    with pytest.raises(DraftError) as denied:
        PublicationRules().conflicts(events)
    assert (denied.value.status, denied.value.code) == (422, "publication_workload")


@pytest.mark.parametrize("limit,second_day", [("max_daily", "2026-10-06"),
                                             ("max_weekly", "2026-10-12")])
def test_workload_buckets_reset_at_day_or_iso_week_boundary(limit, second_day):
    left = event("a")
    right = event("b", start=f"{second_day}T08:00:00+08:00",
                  end=f"{second_day}T09:00:00+08:00")
    share(left, right, "teacher")
    left[limit] = right[limit] = 60
    PublicationRules().conflicts([left, right])


def test_effective_revision_retains_past_dates_and_replaces_only_covered_period():
    original = publication_row()
    replacement = publication_row(version=2, start="2026-10-19", offset=60)
    independent = publication_row(version=3, period="period-b")
    events = PublicationRules().expanded(
        [original, replacement, independent], date(2026, 10, 5), date(2026, 10, 26)
    )
    first_period = [item for item in events if item["period_id"] == "period-a"]
    assert [(item["date"], item["version"]) for item in first_period] == [
        ("2026-10-05", "version-1"), ("2026-10-12", "version-1"),
        ("2026-10-19", "version-2"), ("2026-10-26", "version-2"),
    ]
    assert first_period[2]["starts_at"][11:16] > first_period[0]["starts_at"][11:16]
    assert len([item for item in events if item["period_id"] == "period-b"]) == 4
    assert PublicationRules().expanded([original], date(2026, 11, 1), date(2026, 11, 2)) == []


@pytest.mark.parametrize("role", ["student", "teacher", "administrator"])
def test_institutional_projection_filters_current_record_and_strips_private_metadata(role):
    row = publication_row(multiple=True)
    rules, port = MemoryRules([row]), object()
    faculty_id = PublicationRules().decode(row)["draft"].input_snapshot.teachers[0].id
    result = rules.project(port, "tenant-a", "institutional", "period-a",
                           date(2026, 10, 5), date(2026, 10, 7),
                           {"role": role, "uid": "unrelated-auth-uid",
                            "student_id": "linked-student", "faculty_id": faculty_id})
    assert rules.calls == [("rows", port, "tenant-a", "institutional", "period-a")]
    assert [item["offering_id"] for item in result["occurrences"]] == (
        ["test-0", "test-1"] if role == "administrator" else ["test-0"]
    )
    assert bool(result["sections"]) == (role == "administrator")
    assert bool(result["teachers"]) == (role == "administrator")
    for item in result["occurrences"]:
        assert not {"buffer", "students", "max_daily", "max_weekly"} & item.keys()
    assert "private-student" not in encode(result)
    assert result["calendar"]["published_version"] == row["id"]
    assert not {"payload", "checksum", "draft", "generation_result"} & result.keys()


@pytest.mark.parametrize("viewer", [
    {"role": "student", "uid": "linked-student", "student_id": "not-enrolled"},
    {"role": "student", "uid": "linked-student"},
    {"role": "teacher", "uid": "private-faculty", "faculty_id": "not-assigned"},
    {"role": "teacher", "uid": "private-faculty"},
])
def test_auth_uid_cannot_replace_required_institutional_record_membership(viewer):
    with pytest.raises(DraftError) as denied:
        MemoryRules([publication_row(multiple=True)]).project(
            object(), "tenant-a", "institutional", "period-a",
            date(2026, 10, 5), date(2026, 10, 7), viewer,
        )
    assert (denied.value.status, denied.value.code) == (403, "projection_forbidden")


@pytest.mark.parametrize("tenant,dataset,period", [
    ("other-tenant", "institutional", "period-a"),
    ("tenant-a", "synthetic", "period-a"),
    ("tenant-a", "institutional", "other-period"),
])
def test_empty_scoped_rows_never_fall_back_to_another_tenant_dataset_or_period(
    tenant, dataset, period,
):
    rules, port = MemoryRules([publication_row()]), object()
    with pytest.raises(DraftError) as denied:
        rules.project(port, tenant, dataset, period, date(2026, 10, 5), date(2026, 10, 7),
                      {"role": "administrator"})
    assert (denied.value.status, denied.value.code) == (404, "not_published")
    assert rules.calls == [("rows", port, tenant, dataset, period)]


def test_summary_uses_scoped_current_revision_and_never_returns_raw_snapshot():
    first, second = publication_row(), publication_row(version=2)
    rules, port = MemoryRules([first, second]), object()
    assert rules.summary(first, port)["status"] == "superseded"
    summary = rules.summary(second, port)
    assert summary["status"] == "published" and summary["revision"] == 2
    assert not {"payload", "checksum", "draft", "generation_result"} & summary.keys()
    assert rules.calls == [("head", port, "tenant-a", "institutional", "period-a")] * 2
