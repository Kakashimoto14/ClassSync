from datetime import datetime

from scripts.student_presentation_fixture import fixture


def test_synthetic_export_reproducible_and_conflict_free():
    sample = fixture()
    assert sample == fixture()
    assert not sample["metadata"]["live"]
    events = sample["calendar"]["occurrences"]
    friday = [event for event in events if event["date"] == "2026-10-30"]
    assert len(friday) == 3
    assert not [event for event in events if event["date"] == "2026-10-31"]
    assert friday[0]["ends_at"] == friday[1]["starts_at"]
    assert (
        len(
            {
                datetime.fromisoformat(event["ends_at"])
                - datetime.fromisoformat(event["starts_at"])
                for event in events
            }
        )
        == 3
    )
    assert sample["metadata"]["hard_conflicts_at_export"] == 0


def test_room_change_is_separate_validated_synthetic_scenario():
    baseline, changed = fixture(), fixture(room_change=True)
    key = "student-0-2:2026-10-30"
    before = next(event for event in baseline["calendar"]["occurrences"] if event["id"] == key)
    after = next(event for event in changed["calendar"]["occurrences"] if event["id"] == key)
    assert not before["changed"] and after["changed"]
    assert before["room"]["name"] == "LAB-201" and after["room"]["name"] == "LAB-202"
    assert before["starts_at"] == after["starts_at"]
