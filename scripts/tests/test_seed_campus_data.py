from scripts.seed_campus_data import (
    PERIOD_ID,
    _arguments,
    _same,
    build_academic_records,
    curriculum_subjects,
    load_json,
    merge_room_defaults,
    room_defaults,
)


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
    assert {record.year_level for record in first if record.kind == "subjects"} == {1, 2, 3, 4}
    assert sum(record.kind == "sections" for record in first) == 8
    assert sum(record.kind == "faculty" for record in first) == 12


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
