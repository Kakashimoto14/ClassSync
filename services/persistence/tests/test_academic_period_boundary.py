from datetime import datetime, timedelta, timezone

import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.academic_periods import PostgresAcademicPeriods


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", ""),
        ("tenant_id", " "),
        ("tenant_id", None),
        ("firebase_project_id", ""),
        ("firebase_project_id", " "),
        ("firebase_project_id", "x" * 129),
    ],
)
def test_metadata_requires_explicit_server_binding_without_connecting(field, value):
    config = {"tenant_id": "tenant", "firebase_project_id": "demo-project"}
    config[field] = value
    with pytest.raises(ValueError):
        PostgresAcademicPeriods(object(), **config)


@pytest.mark.parametrize("principal", [None, "uid", {"uid": "uid", "role": "administrator"}])
def test_unverified_subjects_rejected_before_database_access(principal):
    store = PostgresAcademicPeriods(object(), tenant_id="tenant", firebase_project_id="demo")
    with pytest.raises(ValueError, match="verified principal"):
        store.list_for(principal)
    with pytest.raises(ValueError, match="verified principal"):
        store.create_for(principal, title="Synthetic period")


@pytest.mark.parametrize("title", [None, "", " ", "x" * 161])
def test_invalid_title_rejected_before_database_access(title):
    store = PostgresAcademicPeriods(object(), tenant_id="tenant", firebase_project_id="demo")
    with pytest.raises(ValueError, match="title"):
        store.create_for(VerifiedPrincipal(uid="uid"), title=title)


def test_period_timestamp_is_canonical_utc_independent_of_database_timezone():
    row = {
        "id": "synthetic-period",
        "title": "Synthetic",
        "revision": 1,
        "created_at": datetime(2026, 10, 26, 8, tzinfo=timezone(timedelta(hours=8))),
    }
    assert PostgresAcademicPeriods.decode(row).created_at == "2026-10-26T00:00:00+00:00"
