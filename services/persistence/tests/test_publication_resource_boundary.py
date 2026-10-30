"""Portable resource-matrix guards; no solver, database or server execution."""

import sqlite3
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from classync_contracts.academic import (
    AcademicPeriod,
    AcademicSnapshot,
    RecordEnvelope,
    RecordWrite,
)
from classync_contracts.scheduling import Assignment

from scripts import postgres_publication_resource_qualification as resource
from scripts.postgres_disposable import create_root
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_rules import DraftError


@pytest.fixture(autouse=True)
def no_solver_or_database(monkeypatch):
    from ortools.sat.python import cp_model
    from sqlalchemy.engine import Engine

    monkeypatch.setattr(sqlite3, "connect", lambda *_a, **_k: pytest.fail("SQLite opened"))
    monkeypatch.setattr(Engine, "connect", lambda *_a, **_k: pytest.fail("PostgreSQL opened"))
    monkeypatch.setattr(
        cp_model.CpSolver, "solve", lambda *_a, **_k: pytest.fail("Solver executed")
    )


def manual_draft(label, *, shared_ids=None):
    """Pure generated data for guard testing; actual qualifier never uses this placement."""
    period = "period-" + label
    records = resource.record_definitions(period, label, shared_ids=shared_ids)
    snapshot = AcademicSnapshot(
        period=AcademicPeriod(
            id=period,
            title="Invented portable fixture",
            revision=8,
            created_at="2026-10-28T00:00:00+00:00",
            source="institutional",
            calendar=resource.fixture_calendar(),
        ),
        records=[
            RecordEnvelope(
                revision=1,
                updated_at="2026-10-28T00:00:00+00:00",
                updated_by="synthetic-admin",
                record=RecordWrite.model_validate({"expected_revision": 0, "record": row}).record,
            )
            for row in records
        ],
    )
    ready = academic_readiness(snapshot)
    assert ready.ready and ready.inputs is not None, ready.model_dump()
    offering = ready.inputs.offerings[0]
    assignment = Assignment(
        id="manual-session",
        offering_id=offering.id,
        subject_id=offering.subject_id,
        section_id=offering.section_id,
        teacher_id=offering.eligible_teacher_ids[0],
        room_id=offering.eligible_room_ids[0],
        day=0,
        start=480,
        end=540,
    )
    return SimpleNamespace(
        input_snapshot=ready.inputs, generation_result=SimpleNamespace(assignments=[assignment])
    )


def test_existing_evidence_stops_before_cluster_start(tmp_path, monkeypatch):
    path = tmp_path / "preserve.json"
    path.write_text("sentinel", encoding="utf-8")
    monkeypatch.setattr(resource, "qualify", lambda *_a: pytest.fail("Cluster started"))
    with pytest.raises(RuntimeError, match="New output required"):
        resource.main(["--bin", str(tmp_path), "--output", str(path)])
    assert path.read_text(encoding="utf-8") == "sentinel"


def test_unmarked_target_fails_before_engine_construction(tmp_path, monkeypatch):
    monkeypatch.setattr(resource, "engine_for", lambda *_a, **_k: pytest.fail("Engine created"))
    with pytest.raises(ValueError):
        resource.exercise(SimpleNamespace(root=tmp_path / "original"))


def test_marked_target_binding_failure_disposes_engines_without_migration(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    connection = SimpleNamespace(root=create_root(tmp_path))
    disposed = []
    owner = SimpleNamespace(dispose=lambda: disposed.append("owner"))
    runtime = SimpleNamespace(dispose=lambda: disposed.append("runtime"))
    monkeypatch.setattr(resource, "engine_for", lambda *_a, **_k: owner)
    monkeypatch.setattr(resource, "bounded_runtime", lambda *_a: runtime)
    monkeypatch.setattr(resource, "check_pool", lambda *_a: None)

    @contextmanager
    def fake_transaction(_engine):
        yield object()

    def deny_binding(*_args):
        raise RuntimeError("target binding mismatch")

    monkeypatch.setattr(resource, "transaction", fake_transaction)
    monkeypatch.setattr(resource, "verify_fresh_target", deny_binding)
    monkeypatch.setattr(resource, "prepare_source", lambda *_a: pytest.fail("Migration ran"))
    with pytest.raises(RuntimeError, match="target binding mismatch"):
        resource.exercise(connection)
    assert disposed == ["runtime", "owner"]


@pytest.mark.parametrize(
    "changes",
    [
        {"label": "../outside"},
        {"label": ""},
        {"label": "x" * 37},
        {"count": True},
        {"count": 0},
        {"count": 201},
        {"students_per_offering": False},
        {"students_per_offering": 0},
        {"students_per_offering": 101},
        {"shared_ids": {"faculty": "wrong-key"}},
        {"shared_ids": {"room": "../outside"}},
        {"shared_ids": []},
        {"count": 2, "shared_ids": {"room": "shared-room"}},
        {"students_per_offering": 2, "shared_ids": {"student": "shared-student"}},
    ],
)
def test_invalid_fixture_options_stop_before_academic_writes(changes):
    arguments = {"label": "guard", "count": 1, "students_per_offering": 1, "shared_ids": {}}
    with pytest.raises(RuntimeError):
        resource.build_period(SimpleNamespace(), **(arguments | changes))


def test_bounded_multiple_offerings_have_independent_resources_and_student_links():
    records = resource.record_definitions(
        "generated-period", "batch", count=3, students_per_offering=4
    )
    for definition in records:
        RecordWrite.model_validate({"expected_revision": 0, "record": definition})
    assert len(records) == 17
    assert len([row for row in records if row["kind"] == "offerings"]) == 3
    rules = records[-1]
    assert len(rules["enrollments"]) == 12
    assert len({row["student_id"] for row in rules["enrollments"]}) == 12
    offerings = {row["id"] for row in records if row["kind"] == "offerings"}
    assert {row["offering_ids"][0] for row in rules["enrollments"]} == offerings
    assert rules["operating_windows"] == [resource.WINDOW]
    assert "options" not in rules and not rules.get("locked_assignments")
    assert all(
        "max_daily_minutes" not in row and "max_weekly_minutes" not in row
        for row in records
        if row["kind"] == "faculty"
    )
    assert all(row["source"] == "synthetic" for row in records if row["kind"] == "resources")


@pytest.mark.parametrize("kind", resource.KINDS)
def test_actual_occurrence_guard_proves_only_one_shared_conflict_identity(kind):
    base = manual_draft("base")
    shared = next(iter(resource.conflict_identities(base)[kind]))
    candidate = manual_draft("candidate", shared_ids={kind: shared})
    resource.assert_isolated_conflict(base, candidate, kind)
    with pytest.raises(RuntimeError, match="unintended conflict identities"):
        resource.assert_isolated_conflict(base, candidate, None)


def test_disjoint_simultaneous_control_passes_isolation_guard():
    resource.assert_isolated_conflict(manual_draft("base"), manual_draft("control"), None)


def test_additional_shared_resource_cannot_mask_selected_conflict():
    base = manual_draft("base")
    shared = {
        kind: next(iter(values))
        for kind, values in resource.conflict_identities(base).items()
        if kind in {"room", "teacher"}
    }
    with pytest.raises(RuntimeError, match="unintended conflict identities: teacher"):
        resource.assert_isolated_conflict(
            base, manual_draft("candidate", shared_ids=shared), "room"
        )


def test_workload_cap_cannot_mask_exact_conflict():
    base, candidate = manual_draft("base"), manual_draft("control")
    candidate.input_snapshot.teachers[0].max_daily_minutes = 60
    with pytest.raises(RuntimeError, match="Workload cap"):
        resource.assert_isolated_conflict(base, candidate, None)


def test_unforced_solver_placement_cannot_pass_matrix_guard():
    base, candidate = manual_draft("base"), manual_draft("control")
    candidate.generation_result.assignments[0].start = 510
    candidate.generation_result.assignments[0].end = 570
    with pytest.raises(DraftError) as denied:
        resource.assert_isolated_conflict(base, candidate, None)
    assert (denied.value.status, denied.value.code) == (422, "dated_constraints")


@pytest.mark.parametrize(
    "status,code,message",
    [
        (422, "publication_workload", "Teacher workload"),
        (409, "publication_conflict", "Room conflict between a and b."),
        (422, "publication_conflict", "Teacher conflict between a and b."),
    ],
)
def test_other_failure_or_resource_name_cannot_satisfy_exact_room_conflict(status, code, message):
    def operation():
        raise DraftError(status, code, message)

    with pytest.raises(RuntimeError, match="Wrong isolated publication conflict"):
        resource.exact_conflict(operation, "room")


def test_unexpected_success_is_not_accepted_as_resource_conflict():
    with pytest.raises(RuntimeError, match="unexpectedly succeeded"):
        resource.exact_conflict(lambda: {"status": "published"}, "room")


@pytest.mark.parametrize("kind", resource.KINDS)
def test_exact_typed_conflict_and_resource_label_are_required(kind):
    def operation():
        raise DraftError(422, "publication_conflict", kind.title() + " conflict between a and b.")

    resource.exact_conflict(operation, kind)
