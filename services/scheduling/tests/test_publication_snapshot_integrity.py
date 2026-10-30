"""Stored publication summaries must agree with the independently validated run."""

import json

import pytest

from services.scheduling.app.draft_rules import DraftError, digest, encode
from services.scheduling.app.publication_rules import PublicationRules
from services.scheduling.tests.test_publication_rules import publication_row


@pytest.mark.parametrize(
    "field",
    [
        "session_count",
        "offerings_scheduled",
        "allocated_minutes",
        "required_minutes",
        "validation",
    ],
)
def test_checksum_consistent_summary_corruption_is_not_reported_as_valid(field):
    row = publication_row()
    payload = json.loads(row["payload"])
    if field == "validation":
        payload["draft"]["validation"]["valid"] = False
    else:
        payload["draft"][field] += 1
    row["payload"] = encode(payload)
    row["checksum"] = digest(row["payload"])
    with pytest.raises(DraftError) as denied:
        PublicationRules().decode(row)
    assert (denied.value.status, denied.value.code) == (409, "publication_integrity")
