import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from scripts.seed_campus_data import (
    ARCHIVED_LEGACY_TITLE,
    LEGACY_PERIOD_ID,
    PERIOD_ID,
    PERIOD_TITLE,
    _arguments,
    _same,
    apply_seed,
    build_academic_records,
    curriculum_subjects,
    defense_calendar,
    load_json,
    merge_room_defaults,
    room_defaults,
    stable_uuid,
)
from services.academic.app.record_rules import initial_records, unique_label, validate_record


def test_dry_run_is_required_as_an_explicit_cli_action():
    assert _arguments(["--dry-run"]).dry_run
    assert _arguments(["--apply"]).apply


def test_defense_seed_plan_is_stable_and_covers_all_years_without_database_access():
    catalog = load_json("packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json")
    first, roster = build_academic_records(PERIOD_ID, catalog)
    second, second_roster = build_academic_records(PERIOD_ID, catalog)
    assert [record.id for record in first] == [record.id for record in second]
    assert [record["id"] for record in roster] == [record["id"] for record in second_roster]
    assert all(
        _same(first_record, second_record)
        for first_record, second_record in zip(first, second, strict=True)
    )
    assert len(curriculum_subjects()) == 32
    assert len(roster) == 96
    assert len({student["id"] for student in roster}) == 96
    assert {record.year_level for record in first if record.kind == "subjects"} == {1, 2, 3, 4}
    assert sum(record.kind == "sections" for record in first) == 8
    assert sum(record.kind == "faculty" for record in first) == 12


def test_generated_seed_entity_ids_are_deterministic_uuids():
    catalog = load_json("packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json")
    records, roster = build_academic_records(PERIOD_ID, catalog)
    UUID(PERIOD_ID)
    for record in records:
        if record.kind == "resources":
            continue  # canonical campus inventory IDs are source identifiers
        if record.kind == "constraints":
            assert record.id == "rules"  # contract-defined singleton identity
        else:
            UUID(record.id)
    for student in roster:
        UUID(student["person_id"])
        assert student["id"].count("-") == 1  # institutional student-number contract
    assert stable_uuid("period", "ay-2026-2027-first") == PERIOD_ID
    assert "defense-" not in PERIOD_ID


def test_room_defaults_activate_exactly_the_schedulable_catalog_and_preserve_exclusions():
    catalog = load_json("packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json")
    schedulable = [room for room in catalog if room["schedulable"]]
    excluded = [room for room in catalog if not room["schedulable"]]
    verified = [room_defaults(room) for room in schedulable]
    assert len(verified) == 41
    assert all(
        room.capacity_verified and room.type_verified and room.schedulable for room in verified
    )
    assert sum(room.room_type == "computer_lab" for room in verified) >= 4
    assert len(excluded) == 12 and all(room["schedulable"] is False for room in excluded)
    for room in excluded:
        try:
            room_defaults(room)
        except ValueError:
            continue
        raise AssertionError("excluded space was accepted for scheduling")


def test_seed_room_merge_preserves_admin_edits_and_maintenance_state():
    catalog = load_json("packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json")
    source = next(room for room in catalog if room["id"] == "cdm-prrc-302")
    defaults = room_defaults(source)
    edited = defaults.model_copy(
        update={
            "capacity": 52,
            "capacity_verified": False,
            "availability": [{"day": 0, "start": 480, "end": 900}],
            "availability_verified": False,
            "verification_note": "Administrator review note",
        }
    )
    merged = merge_room_defaults(edited, defaults)
    assert merged.capacity == 52
    assert merged.availability == edited.availability
    assert merged.verification_note == "Administrator review note"
    maintenance = edited.model_copy(update={"condition": "maintenance"})
    assert merge_room_defaults(maintenance, defaults) == maintenance


def test_apply_requires_exact_tenant_confirmation_before_any_database_access(monkeypatch):
    import pytest

    from scripts.seed_campus_data import main

    monkeypatch.setenv("CLASSYNC_SEED_ENV", "defense")
    monkeypatch.setenv("MIGRATION_DATABASE_URL", "not-opened")
    monkeypatch.setenv("INSTITUTIONAL_TENANT_ID", "defense-tenant")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "defense-project")
    monkeypatch.setenv("CLASSYNC_SEED_ADMIN_UID", "defense-admin")
    with pytest.raises(SystemExit, match="exact.*INSTITUTIONAL_TENANT_ID"):
        main(["--apply"])


class MemoryResult:
    def __init__(self, values=()):
        self.values = list(values)

    def scalars(self):
        return self

    def all(self):
        return self.values

    def mappings(self):
        return self

    def one_or_none(self):
        return self.values[0] if self.values else None

class MemoryDB:
    def __init__(self, repo):
        self.repo = repo

    def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}
        if "SELECT id FROM classsync_academic.period_metadata" in sql:
            return MemoryResult([self.repo.period_id])
        if "id=:legacy" in sql and "period_metadata" in sql:
            return MemoryResult([dict(self.repo.legacy)] if self.repo.legacy else [])
        if "UPDATE classsync_academic.period_metadata" in sql:
            self.repo.legacy["title"] = params["title"]
            self.repo.legacy["revision"] += 1
            return MemoryResult([{"revision": self.repo.legacy["revision"]}])
        if "academic.period.archived" in sql:
            self.repo.archive_events.append(params["revision"])
        if "INSERT INTO classsync_identity.students" in sql:
            self.repo.students.add(params["student"])
        if "INSERT INTO classsync_identity.faculty" in sql:
            self.repo.faculty[params["faculty"]] = params["person"]
            self.repo.faculty_inserts += 1
        if "INSERT INTO classsync_identity.people" in sql:
            self.repo.people.add(params["person"])
        return MemoryResult()

    def scalar(self, statement, params=None):
        params = params or {}
        if "classsync_identity.faculty" in str(statement):
            return int(params.get("faculty") in self.repo.faculty)
        return int(params.get("student") in self.repo.students)

class MemoryRepo:
    keys = {"tenant": "cdm", "owner": "test-admin"}

    def __init__(self):
        self.period_id = PERIOD_ID
        self.calendar = defense_calendar()
        self.records = {}
        self.students = set()
        self.faculty = {}
        self.faculty_inserts = 0
        self.people = set()
        self.labels = {}
        self.legacy = None
        self.archive_events = []
        # Simulate create-period's revision-1 default programs, 53 spaces and
        # singleton constraints, enforcing the same scoped unique-label key.
        for record in initial_records(True):
            self.store(record, revision=1)

    @contextmanager
    def session(self, *, write=False):
        yield MemoryDB(self)

    def params(self, period_id, **extra):
        return {**self.keys, "period": period_id, **extra}

    def snapshot_in(self, db, period_id):
        records = [
            SimpleNamespace(record=record, revision=revision)
            for (kind, _), (record, revision) in self.records.items()
            if kind
        ]
        return SimpleNamespace(
            period=SimpleNamespace(calendar=self.calendar), records=records
        )

    def store(self, record, revision):
        key = (record.kind, record.id)
        label_key = (record.kind, unique_label(record))
        other_id = self.labels.get(label_key)
        if other_id is not None and other_id != record.id:
            raise AssertionError(f"duplicate scoped unique_label: {label_key}")
        self.records[key] = (record, revision)
        self.labels[label_key] = record.id

    def write_in(self, db, period_id, body, *, allow_cohort_change=False):
        record = body.record
        key = (record.kind, record.id)
        current = self.records.get(key)
        revision = current[1] if current else 0
        assert body.expected_revision == revision
        label_key = (record.kind, unique_label(record))
        conflicting_id = self.labels.get(label_key)
        assert conflicting_id in (None, record.id), (
            f"duplicate scoped unique_label: {label_key}"
        )

        def lookup(kind, identity):
            found = self.records.get((kind, identity))
            return found[0] if found else None

        validate_record(
            record,
            period_id,
            lookup,
            allow_cohort_change=allow_cohort_change,
        )
        self.store(record, revision + 1)

    def bump(self, period_id):
        return None


def test_apply_reuses_prepopulated_catalog_ids_and_is_idempotent():
    """Model the scoped Postgres unique key against a new period's default catalog rows."""
    repo = MemoryRepo()
    preseeded_rooms = {
        record.id: record
        for record, _revision in repo.records.values()
        if record.kind == "resources"
    }
    assert len(preseeded_rooms) == 53

    first_written, first_students = apply_seed(repo)
    second_written, second_students = apply_seed(repo)

    records = [record for record, _ in repo.records.values()]
    programs = {record.id for record in records if record.kind == "programs"}
    # Phase B: BSIT's 54 offerings plus 193 for the seven other degree programs.
    assert sum(record.kind == "offerings" for record in records) == 247
    assert first_written > 0
    assert second_written == 0
    assert first_students == 432
    assert second_students == 0
    seeded_faculty = {record.id for record in records if record.kind == "faculty"}
    assert len(seeded_faculty) == 57
    # Every seeded faculty record gets exactly one identity, once, linked to a person row.
    assert set(repo.faculty) == seeded_faculty
    assert repo.faculty_inserts == 57  # the rerun inserted none
    assert set(repo.faculty.values()) <= repo.people
    assert len(repo.people) == 432 + 57
    assert all(
        set(record.program_ids) <= programs
        for record in records
        if record.kind == "subjects"
    )
    assert all(
        record.program_id in programs
        for record in records
        if record.kind == "sections"
    )
    rooms = [record for record in records if record.kind == "resources"]
    schedulable = [record for record in rooms if record.schedulable]
    excluded = [record for record in rooms if not record.schedulable]
    assert len(schedulable) == 41
    assert len(excluded) == 12
    assert all(_same(room, preseeded_rooms[room.id]) for room in excluded)
    assert all(
        room.type_verified and room.capacity_verified and room.availability_verified
        for room in schedulable
    )
    assert all(not room.type_verified and not room.capacity_verified for room in excluded)


def test_cli_help_runs_standalone_without_pythonpath():
    """`python scripts/seed_campus_data.py` must import services.* without PYTHONPATH."""
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": ""}
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "seed_campus_data.py"), "--help"],
        cwd=root / "scripts",
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--apply" in result.stdout


def test_reapplying_after_the_legacy_period_was_archived_is_a_clean_no_op():
    repo = MemoryRepo()
    repo.legacy = {
        "id": LEGACY_PERIOD_ID,
        "title": PERIOD_TITLE,
        "data_mode": "institutional",
        "revision": 4,
    }
    apply_seed(repo)
    assert repo.legacy["title"] == ARCHIVED_LEGACY_TITLE
    assert (repo.legacy["revision"], repo.archive_events) == (5, [5])

    # A database seeded before faculty identities existed receives them on the rerun.
    expected = set(repo.faculty)
    repo.faculty.clear()
    repo.faculty_inserts = 0
    assert apply_seed(repo) == (0, 0)
    assert set(repo.faculty) == expected and repo.faculty_inserts == 57
    assert (repo.legacy["revision"], repo.archive_events) == (5, [5])


@pytest.mark.parametrize(
    ("title", "data_mode"),
    [
        ("Renamed by an administrator", "institutional"),
        (ARCHIVED_LEGACY_TITLE, "synthetic"),
    ],
)
def test_an_unrecognised_legacy_period_is_still_preserved(title, data_mode):
    repo = MemoryRepo()
    repo.legacy = {"id": LEGACY_PERIOD_ID, "title": title, "data_mode": data_mode, "revision": 4}
    with pytest.raises(ValueError, match="legacy period does not match"):
        apply_seed(repo)
    assert (repo.legacy["title"], repo.legacy["revision"], repo.archive_events) == (title, 4, [])
