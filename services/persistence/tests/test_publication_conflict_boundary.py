"""Pure evidence-shape checks for the separate guarded PG race qualifier."""

import copy

import pytest

from scripts.postgres_publication_conflict_qualification import (
    publication_winner_transition,
    restriction_winner_transition,
)


def baseline_state():
    return {
        "solver_runs": [{"id": "run-a"}, {"id": "run-b"}],
        "drafts": [{"id": "draft-a"}, {"id": "draft-b"}],
        "published_versions": [{"id": "version-a", "revision": 1,
                                "idempotency_key": "baseline-a"}],
        "publication_heads": [{"period_id": "period-a", "revision": 1}],
        "room_restrictions": [],
        "restriction_audit": [],
    }


def test_publication_winner_only_advances_version_and_head():
    before = baseline_state()
    after = copy.deepcopy(before)
    after["published_versions"].append(
        {"id": "version-b", "revision": 2, "idempotency_key": "future-publish"}
    )
    after["publication_heads"][0]["revision"] = 2

    publication_winner_transition(
        before, after, period_id="period-a", key="future-publish", version_id="version-b"
    )


@pytest.mark.parametrize(
    "unexpected",
    [
        ("room_restrictions", {"id": "partial-restriction"}),
        ("restriction_audit", {"id": "partial-audit"}),
        ("drafts", {"id": "unexpected-draft"}),
    ],
)
def test_publication_winner_rejects_loser_or_unrelated_writes(unexpected):
    before = baseline_state()
    after = copy.deepcopy(before)
    after["published_versions"].append(
        {"id": "version-b", "revision": 2, "idempotency_key": "future-publish"}
    )
    after["publication_heads"][0]["revision"] = 2
    table, row = unexpected
    after[table].append(row)

    with pytest.raises(RuntimeError):
        publication_winner_transition(
            before, after, period_id="period-a", key="future-publish", version_id="version-b"
        )


def test_restriction_winner_only_adds_restriction_and_matching_audit():
    before = baseline_state()
    after = copy.deepcopy(before)
    after["room_restrictions"].append(
        {"id": "future-room", "room_id": "room-a", "revision": 1}
    )
    after["restriction_audit"].append(
        {"id": "future-room", "revision": 1, "old_snapshot": None}
    )

    restriction_winner_transition(
        before, after, restriction_id="future-room", room_id="room-a"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "partial_publication",
        "publication_head",
        "wrong_room",
        "missing_audit",
        "extra_audit",
    ],
)
def test_restriction_winner_rejects_publication_or_partial_audit(mutation):
    before = baseline_state()
    after = copy.deepcopy(before)
    after["room_restrictions"].append(
        {"id": "future-room", "room_id": "room-a", "revision": 1}
    )
    after["restriction_audit"].append(
        {"id": "future-room", "revision": 1, "old_snapshot": None}
    )
    if mutation == "partial_publication":
        after["published_versions"].append(
            {"id": "partial", "revision": 2, "idempotency_key": "loser-key"}
        )
    elif mutation == "publication_head":
        after["publication_heads"][0]["revision"] = 2
    elif mutation == "wrong_room":
        after["room_restrictions"][0]["room_id"] = "other-room"
    elif mutation == "missing_audit":
        after["restriction_audit"].clear()
    else:
        after["restriction_audit"].append(
            {"id": "extra", "revision": 2, "old_snapshot": None}
        )

    with pytest.raises(RuntimeError):
        restriction_winner_transition(
            before, after, restriction_id="future-room", room_id="room-a"
        )
