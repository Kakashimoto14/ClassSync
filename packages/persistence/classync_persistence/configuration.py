"""Explicit PostgreSQL/libpq transport boundary shared by configured services."""

import os
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url


def postgres_configuration(
    database_url, *, transport, environment, firebase_project_id, tenant_id, application_name
):
    """Explicit libpq target/transport; never inherit service/password-file defaults."""
    try:
        if any(key.upper().startswith("PG") for key in os.environ):
            raise ValueError()
        url = make_url(database_url.get_secret_value())
        if (
            url.drivername != "postgresql+psycopg"
            or url.query
            or not url.host
            or not re.fullmatch(r"[A-Za-z0-9.:-]+", url.host)
            or not url.port
            or not 0 < url.port < 65536
            or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,62}", url.username or "")
            or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,62}", url.database or "")
            or not isinstance(firebase_project_id, str)
            or not firebase_project_id.strip()
            or not isinstance(tenant_id, str)
            or not tenant_id.strip()
        ):
            raise ValueError()
        parameters = {
            "connect_timeout": 5,
            "options": "-c statement_timeout=5000 -c lock_timeout=1500",
            "passfile": str(Path(tempfile.gettempdir()) / ("classsync-no-passfile-" + uuid4().hex)),
            "application_name": application_name,
        }
        if transport == "loopback-sspi-test":
            if (
                environment != "test"
                or url.host != "127.0.0.1"
                or url.port <= 1024
                or url.port == 5432
                or url.password is not None
            ):
                raise ValueError()
            parameters.update(sslmode="disable", gssencmode="disable", require_auth="sspi")
        elif transport == "verify-full":
            parameters.update(
                sslmode="verify-full",
                sslrootcert="system",
                gssencmode="disable",
                require_auth="scram-sha-256",
            )
        else:
            raise ValueError()
        return url, parameters
    except Exception:
        raise ValueError("Identity database configuration is invalid") from None
