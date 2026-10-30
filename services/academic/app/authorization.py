"""Owned Academic identity/data pool; no migrations or SQLite fallback."""

from contextlib import contextmanager

from classync_contracts.request_authorization import AuthorizationAdapters
from classync_contracts.token_verification import FirebaseTokenVerifier
from classync_persistence.configuration import postgres_configuration
from classync_persistence.database import postgres_engine
from classync_persistence.memberships import PostgresMembershipLookup


@contextmanager
def configured_academic(application, settings):
    if settings.academic_database_url is None:
        yield
        return
    if hasattr(application.state, "authorization_adapters") or hasattr(
        application.state, "academic_engine"
    ):
        raise ValueError("Academic authorization/storage is already configured")
    url, parameters = postgres_configuration(
        settings.academic_database_url,
        transport=settings.academic_database_transport,
        environment=settings.classsync_env,
        firebase_project_id=settings.firebase_project_id,
        tenant_id=settings.institutional_tenant_id,
        application_name="classsync-academic",
    )
    engine = postgres_engine(
        url, connect_args=parameters, pool_timeout=3, pool_size=5, max_overflow=0
    )
    adapters = None
    try:
        adapters = AuthorizationAdapters(
            FirebaseTokenVerifier(settings),
            PostgresMembershipLookup(engine, firebase_project_id=settings.firebase_project_id),
        )
        application.state.authorization_adapters = adapters
        application.state.academic_engine = engine
        yield
    finally:
        if getattr(application.state, "academic_engine", None) is engine:
            del application.state.academic_engine
        if (
            adapters is not None
            and getattr(application.state, "authorization_adapters", None) is adapters
        ):
            del application.state.authorization_adapters
        engine.dispose()
