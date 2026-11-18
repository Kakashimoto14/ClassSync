"""Non-root container entry for the existing three services; no migration or seeding."""

import os

import uvicorn
from classync_contracts.cloud_run import run_origin


def hosted_configuration(environ, service):
    """Cloud Run must never start as an emulator, legacy sandbox or key-based deployment."""
    required = {
        "CLASSSYNC_ENV": "production", "FIREBASE_USE_ADC": "true",
        "CLOUD_RUN_IAM_ENABLED": "true", "ENABLE_SCHEDULING_SANDBOX": "false",
        "ENABLE_TEST_IDENTITY_ADAPTERS": "false",
    }
    if any(environ.get(name) != value for name, value in required.items()):
        raise ValueError("Cloud Run requires hosted security settings")
    forbidden = {
        "GOOGLE_APPLICATION_CREDENTIALS", "FIREBASE_SERVICE_ACCOUNT_JSON",
        "FIREBASE_CLIENT_EMAIL", "FIREBASE_PRIVATE_KEY",
        "FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST",
    }
    if any(name in environ for name in forbidden):
        raise ValueError("Cloud Run must use its managed identity without emulator or key settings")
    database = "IDENTITY" if service == "gateway" else service.upper()
    if (not environ.get(database + "_DATABASE_URL") or
            environ.get(database + "_DATABASE_TRANSPORT") != "verify-full"):
        raise ValueError("Cloud Run requires a configured verified TLS database")
    project = environ.get("FIREBASE_PROJECT_ID", "")
    if not project or project.startswith("demo-") or not environ.get("INSTITUTIONAL_TENANT_ID"):
        raise ValueError("Cloud Run requires an explicit hosted project and tenant")
    if service in {"gateway", "scheduling"}:
        run_origin(environ.get("ACADEMIC_SERVICE_URL"))
    if service == "gateway":
        run_origin(environ.get("SCHEDULING_SERVICE_URL"))
        if environ.get("ALLOW_UNAUTHENTICATED_DEVELOPMENT") != "false":
            raise ValueError("Cloud Run must disable the development bypass")


def configuration(environ):
    service = environ.get("CLASSSYNC_SERVICE", "gateway")
    if service not in {"gateway", "academic", "scheduling"}:
        raise ValueError("Choose gateway, academic or scheduling")
    if environ.get("K_SERVICE"):
        hosted_configuration(environ, service)
    port = int(environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT is outside the valid range")
    return f"services.{service}.app.main:app", port


if __name__ == "__main__":
    if os.environ.get("CLASSSYNC_SERVICE", "gateway") == "all":
        from scripts.render_entrypoint import main as render_main

        raise SystemExit(render_main())
    application, port = configuration(os.environ)
    uvicorn.run(
        application, host="0.0.0.0", port=port, workers=1, proxy_headers=False, access_log=False
    )
