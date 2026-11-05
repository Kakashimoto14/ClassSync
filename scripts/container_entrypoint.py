"""Non-root container entry for the existing three services; no migration or seeding."""

import os

import uvicorn


def configuration(environ):
    service = environ.get("CLASSSYNC_SERVICE", "gateway")
    if service not in {"gateway", "academic", "scheduling"}:
        raise ValueError("Choose gateway, academic or scheduling")
    port = int(environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT is outside the valid range")
    return f"services.{service}.app.main:app", port


if __name__ == "__main__":
    application, port = configuration(os.environ)
    uvicorn.run(
        application, host="0.0.0.0", port=port, workers=1, proxy_headers=False, access_log=False
    )
