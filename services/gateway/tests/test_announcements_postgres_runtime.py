"""Announcements on a throwaway PostgreSQL cluster, as a read-only identity runtime role.

The earlier `FOR SHARE OF m` membership lock needs UPDATE on `memberships`, which the runtime
role never has, so every list and write failed with 42501 behind an HTTP 503.
"""

import pytest
from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from services.gateway.app.announcements import Announcements, NoticeEdit, NoticeInput
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT = "cdm", "demo-classsync-notices"
ADMIN = {"tenant_id": TENANT, "uid": "admin-uid", "role": "administrator"}
STRANGER = {"tenant_id": TENANT, "uid": "stranger", "role": "administrator"}
NOTICE = NoticeInput(title="Runtime notice", body="Invented text", audience=["administrator"])


@pytest.fixture(scope="module")
def notices(cluster):  # noqa: F811
    provisioned = provision(cluster)
    engine = provisioned.engine
    with transaction(engine("boot")) as db:
        execute(db, "INSERT INTO classsync_identity.tenants VALUES (:t,:p)", t=TENANT, p=PROJECT)
        identity_context(db, tenant_id=TENANT, uid="admin-uid")
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        execute(db, "INSERT INTO classsync_identity.people(tenant_id,id) VALUES (:t,'p-a')",
                t=TENANT)
        execute(db, "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,roles,state,revision) VALUES "
                    "(:t,'admin-uid','p-a',ARRAY['administrator'],'active',1)", t=TENANT)
    try:
        yield provisioned, Announcements(engine("runtime"), tenant=TENANT, project=PROJECT)
    finally:
        for item in provisioned.engines.values():
            item.dispose()


def test_row_locking_membership_is_not_available_to_the_runtime_role(notices):
    provisioned, _ = notices
    with transaction(provisioned.engine("runtime")) as db:
        identity_context(db, tenant_id=TENANT, uid="admin-uid")
        with pytest.raises(DBAPIError) as error:
            db.execute(text("SELECT 1 FROM classsync_identity.memberships FOR SHARE"))
        assert error.value.orig.sqlstate == "42501"


def test_administrator_creates_lists_edits_and_archives_a_notice(notices):
    _, repository = notices
    created = repository.create(ADMIN, NOTICE)
    assert created["revision"] == 1
    assert [row["id"] for row in repository.list(ADMIN)["announcements"]] == [created["id"]]
    edit = NoticeEdit(**{**NOTICE.model_dump(), "title": "Edited"}, expected_revision=1)
    assert repository.change(ADMIN, created["id"], 1, edit)["title"] == "Edited"
    with pytest.raises(HTTPException) as stale:
        repository.change(ADMIN, created["id"], 1, edit)
    assert stale.value.status_code == 409
    repository.change(ADMIN, created["id"], 2)
    assert repository.list(ADMIN)["announcements"] == []


def test_non_member_is_denied_not_reported_unavailable(notices):
    _, repository = notices
    for call in (
        lambda: repository.list(STRANGER),
        lambda: repository.create(STRANGER, NOTICE),
    ):
        with pytest.raises(HTTPException) as denied:
            call()
        assert denied.value.status_code == 403
