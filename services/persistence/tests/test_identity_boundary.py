from types import SimpleNamespace

import pytest
from classync_persistence.memberships import PostgresMembershipLookup, identity_context
from classync_persistence.schema import migrate


@pytest.mark.parametrize("tenant,uid", [(None, "uid"), (" ", "uid"), ("tenant", " ")])
def test_identity_context_requires_explicit_tenant_and_verified_uid(tenant, uid):
    with pytest.raises(ValueError):
        identity_context(None, tenant_id=tenant, uid=uid)


def test_lookup_cannot_omit_verifier_project_binding():
    with pytest.raises(ValueError, match="project binding"):
        PostgresMembershipLookup(None, firebase_project_id=" ")


def test_migration_rejects_another_dialect_before_loading_alembic():
    with pytest.raises(ValueError, match="PostgreSQL connection"):
        migrate(SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))


def test_migration_requires_caller_owned_transaction():
    with pytest.raises(ValueError, match="caller-owned transaction"):
        migrate(SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql"), in_transaction=lambda: False,
        ))
