"""Phase B seed: the seven CdM degree programs beyond BSIT (owner-authorized defaults)."""

from collections import Counter, defaultdict

import pytest

import scripts.seed_campus_data as seed
from scripts.seed_campus_data import (
    PERIOD_ID,
    _same,
    apply_seed,
    build_academic_records,
    build_defense_records,
    load_json,
)
from scripts.seed_program_catalog import LOAD_SHARE, classify
from scripts.tests.test_seed_campus_data import MemoryRepo
from services.scheduling.app.catalog import excluded_space_ids

CATALOG = "packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json"


@pytest.fixture(scope="module")
def built():
    return build_defense_records(PERIOD_ID, load_json(CATALOG))


def by_kind(records, kind):
    return [r for r in records if r.kind == kind]


def test_all_degree_programs_with_tcp_left_as_its_catalog_row(built):
    records, students = built
    acronyms = {r.acronym for r in by_kind(records, "programs")}
    assert acronyms == {"BSIT", "BSCPE", "BSEd-SCI", "BEEd-GEN", "BEEd-ECED", "BTLEd-ICT",
                        "BSBA-HRM", "BSE"}
    sections = by_kind(records, "sections")
    assert len(sections) == 36 and len(by_kind(records, "offerings")) == 247
    assert len(students) == len({s["id"] for s in students}) == 432
    assert "tcp" not in {s.program_id for s in sections}  # no prospectus: nothing invented
    per_program = Counter(s.program_id for s in sections)
    assert all(count == 4 for program, count in per_program.items() if program != seed.stable_uuid(
        "program", "BSIT"))


def test_bsit_records_are_unchanged_and_builds_are_deterministic(built):
    records, students = built
    bsit, bsit_students = build_academic_records(PERIOD_ID, load_json(CATALOG))
    assert all(_same(a, b) for a, b in zip(bsit[:-1], records[: len(bsit) - 1], strict=True))
    assert records[-1].enrollments[: len(bsit[-1].enrollments)] == bsit[-1].enrollments
    assert [s["id"] for s in students[: len(bsit_students)]] == [s["id"] for s in bsit_students]
    again, _ = build_defense_records(PERIOD_ID, load_json(CATALOG))
    assert all(_same(a, b) for a, b in zip(records, again, strict=True))


def test_new_faculty_stay_at_or_under_75_percent_and_a_quarter_are_part_time(built):
    records, _ = built
    subjects = {s.id: s for s in by_kind(records, "subjects")}
    faculty = {f.id: f for f in by_kind(records, "faculty") if f.max_continuous_minutes}
    load = defaultdict(int)
    for offering in by_kind(records, "offerings"):
        teacher = offering.teacher_ids[0]
        load[teacher] += subjects[offering.subject_id].required_weekly_minutes
        if teacher in faculty:
            assert offering.subject_id in faculty[teacher].subject_ids
    assert faculty and all(load[f] <= LOAD_SHARE * faculty[f].max_weekly_minutes for f in faculty)
    part_time = [f for f in faculty.values() if f.max_weekly_minutes == 600]
    assert 0.2 <= len(part_time) / len(faculty) <= 0.3
    assert all(f.max_continuous_minutes == 240 for f in faculty.values())


def test_rooms_follow_type_rules_and_never_include_excluded_spaces(built):
    records, _ = built
    rooms = {r.id: r for r in by_kind(records, "resources")}
    sections = {s.id: s for s in by_kind(records, "sections")}
    for offering in by_kind(records, "offerings"):
        assert offering.room_ids and not set(offering.room_ids) & excluded_space_ids()
        assert {rooms[r].room_type for r in offering.room_ids} == {offering.required_room_type}
        if offering.required_room_type == "science_lab":
            assert sections[offering.section_id].program_id == "bsed-sci"
    types = Counter(o.required_room_type for o in by_kind(records, "offerings"))
    assert types["athletic_space"] == 21 and types["science_lab"] == 6


@pytest.mark.parametrize(
    ("title", "lab", "program", "expected"),
    [
        ("Physical Activity Towards Health and Fitness 1", 0, "BSCPE",
         ("athletic_space", "pahfit")),
        ("Outdoor and Adventure Activities", 0, "BSED SCIENCE", ("athletic_space", "pahfit")),
        ("PAHFIT1 Movement Compentency Training", 0, "BECED", ("athletic_space", "pahfit")),
        ("National Service Training Program 1", 0, "BSBA HRM", ("athletic_space", "sports")),
        ("Computer Programming 1", 1, "BSCPE", ("computer_lab", "computer_lab_instruction")),
        ("General Biology", 1, "BSED SCIENCE", ("science_lab", "bse_science_instruction")),
        ("Child Development", 2, "BECED", ("lecture_classroom", "academic_instruction")),
    ],
)
def test_classifier(title, lab, program, expected):
    assert classify(title, lab, program) == expected


def test_expanding_an_existing_bsit_period_preserves_edits_and_is_idempotent(monkeypatch):
    repo = MemoryRepo()
    # First, the period as previously seeded with BSIT only.
    monkeypatch.setattr(seed, "build_defense_records", build_academic_records)
    apply_seed(repo)
    offering_key = next(k for k in repo.records if k[0] == "offerings")
    edited, revision = repo.records[offering_key]
    edited = edited.model_copy(update={"room_ids": edited.room_ids[:1]})
    repo.records[offering_key] = (edited, revision + 1)
    constraints_key = ("constraints", "rules")
    before = repo.records[constraints_key][0].enrollments
    # An Administrator removed one BSIT student's enrollment; a rerun must not restore it.
    trimmed = repo.records[constraints_key][0].model_copy(update={"enrollments": before[1:]})
    repo.records[constraints_key] = (trimmed, repo.records[constraints_key][1] + 1)
    monkeypatch.undo()

    written, students = apply_seed(repo)
    assert written > 0 and students == 432 - 96
    assert _same(repo.records[offering_key][0], edited)  # Administrator edit kept
    enrollments = repo.records[constraints_key][0].enrollments
    assert enrollments[: len(before) - 1] == before[1:]
    assert before[0].student_id not in {e.student_id for e in enrollments}
    assert len(enrollments) == len(before) - 1 + (432 - 96)
    assert sum(k[0] == "offerings" for k in repo.records) == 247
    assert apply_seed(repo) == (0, 0)
