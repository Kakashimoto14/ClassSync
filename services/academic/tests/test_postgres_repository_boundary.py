from datetime import datetime, timedelta, timezone

import pytest
from classync_contracts.identity import VerifiedPrincipal

from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.academic.app.record_rules import adapter, checksum, encode


@pytest.mark.parametrize("principal", [None, "uid", {"uid": "uid", "role": "administrator"}])
def test_pg_academic_rejects_unverified_subject_before_opening_database(principal):
    with pytest.raises(ValueError, match="verified principal"):
        PostgresAcademicRepository(
            object(), tenant_id="tenant", firebase_project_id="demo", principal=principal
        )


@pytest.mark.parametrize("field,value", [("tenant_id", ""), ("firebase_project_id", " ")])
def test_pg_academic_requires_explicit_server_binding_without_migration(field, value):
    config = {"tenant_id": "tenant", "firebase_project_id": "demo"}
    config[field] = value
    with pytest.raises(ValueError):
        PostgresAcademicRepository(object(), principal=VerifiedPrincipal(uid="uid"), **config)


def test_pg_snapshot_record_timestamp_preserves_existing_utc_contract():
    record = adapter.validate_python(
        {"kind": "subjects", "id": "subject", "code": "SYN", "name": "Synthetic"}
    )
    payload = encode(record.model_dump(mode="json"))
    repository = object.__new__(PostgresAcademicRepository)
    entry = repository.envelope(
        {
            "id": record.id,
            "kind": record.kind,
            "revision": 1,
            "payload": payload,
            "checksum": checksum(payload),
            "updated_by": "synthetic-uid",
            "updated_at": datetime(2026, 10, 26, 8, tzinfo=timezone(timedelta(hours=8))),
        }
    )
    assert entry.updated_at == "2026-10-26T00:00:00+00:00"
