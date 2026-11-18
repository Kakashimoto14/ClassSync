"""Qualification follows the migration graph and rejects incomplete RLS coverage."""

import pytest

from scripts.postgres_identity_qualification import identity_tables, require_identity_policies


@pytest.mark.parametrize("target,count", [
    ("0007_publication_state", 6),
    ("0013_synthetic_review_period_mode", 6),
    ("0014_account_onboarding", 8),
    ("head", 9),
])
def test_identity_inventory_tracks_the_requested_migration(target, count):
    tables = identity_tables(target)
    assert len(tables) == count
    require_identity_policies([(name, True, True) for name in tables], tables)


@pytest.mark.parametrize("defect", ["missing", "replacement", "disabled", "not_forced"])
def test_missing_or_unprotected_onboarding_tables_cannot_pass(defect):
    tables = identity_tables("head")
    policies = [(name, True, True) for name in tables]
    if defect == "missing":
        policies.pop()
    elif defect == "replacement":
        policies[-1] = ("unreviewed_table", True, True)
    else:
        policies[-1] = (tables[-1], defect != "disabled", defect != "not_forced")
    with pytest.raises(RuntimeError, match="FORCE RLS"):
        require_identity_policies(policies, tables)
