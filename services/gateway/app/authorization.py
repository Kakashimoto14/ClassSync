"""Gateway identity provider ownership; no migrations or institutional provisioning."""

from contextlib import contextmanager

from classync_contracts.request_authorization import AuthorizationAdapters
from classync_contracts.token_verification import FirebaseTokenVerifier
from classync_persistence.configuration import postgres_configuration
from classync_persistence.database import postgres_engine
from classync_persistence.memberships import PostgresMembershipLookup

from .announcements import Announcements
from .onboarding_repository import OnboardingRepository


def connection_configuration(settings):
    return postgres_configuration(
        settings.identity_database_url,
        transport=settings.identity_database_transport,
        environment=settings.classsync_env,
        firebase_project_id=settings.firebase_project_id,
        tenant_id=settings.institutional_tenant_id,
        application_name="classsync-gateway-identity",
    )


@contextmanager
def configured_authorization(application, settings):
    """Own only the configured pool/adapters; leave explicit unconfigured tests alone."""
    if settings.identity_database_url is None:
        yield
        return
    if hasattr(application.state, "authorization_adapters"):
        raise ValueError("Identity authorization is already configured")
    url, parameters = connection_configuration(settings)
    engine = postgres_engine(
        url,
        connect_args=parameters,
        pool_timeout=3,
        pool_size=settings.database_pool_size,
        max_overflow=0,
    )
    adapters = None
    onboarding = None
    announcements = None
    try:
        adapters = AuthorizationAdapters(
            FirebaseTokenVerifier(settings),
            PostgresMembershipLookup(engine, firebase_project_id=settings.firebase_project_id),
        )
        application.state.authorization_adapters = adapters
        onboarding = OnboardingRepository(
            engine, tenant=settings.institutional_tenant_id, project=settings.firebase_project_id
        )
        application.state.onboarding_repository = onboarding
        announcements = Announcements(
            engine, tenant=settings.institutional_tenant_id, project=settings.firebase_project_id
        )
        application.state.announcements_repository = announcements
        yield
    finally:
        if (
            adapters is not None
            and getattr(application.state, "authorization_adapters", None) is adapters
        ):
            del application.state.authorization_adapters
        if (
            onboarding is not None
            and getattr(application.state, "onboarding_repository", None) is onboarding
        ):
            del application.state.onboarding_repository
        if (
            announcements is not None
            and getattr(application.state, "announcements_repository", None) is announcements
        ):
            del application.state.announcements_repository
        engine.dispose()
