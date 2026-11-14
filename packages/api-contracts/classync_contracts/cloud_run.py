"""Separate the managed Cloud Run invoker identity from Firebase user identity."""

import re
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

_RUN_ORIGIN = re.compile(r"https://[a-z0-9][a-z0-9.-]*\.run\.app")
_TOKEN = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_METADATA_IDENTITY = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
)


def run_origin(value):
    if not isinstance(value, str) or not _RUN_ORIGIN.fullmatch(value) or ".." in value:
        raise ValueError("Expected a canonical HTTPS Cloud Run origin")
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _metadata_token(audience):
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(
        _METADATA_IDENTITY + "?" + urlencode({"audience": audience}),
        headers={"Metadata-Flavor": "Google"},
    )
    try:
        with opener.open(request, timeout=2) as response:
            if response.headers.get("Metadata-Flavor") != "Google":
                raise ValueError("Invalid workload identity response")
            token = response.read(16_385).decode("ascii")
            if len(token) > 16_384 or not _TOKEN.fullmatch(token):
                raise ValueError("Invalid workload identity response")
            return token
    except (OSError, UnicodeError) as error:
        raise ValueError("Cloud Run workload identity unavailable") from error


def service_headers(enabled, origin, headers=None):
    """Never relay a browser-supplied invoker header or replace Authorization."""
    result = {
        key: value for key, value in (headers or {}).items()
        if key.lower() != "x-serverless-authorization"
    }
    if enabled:
        result["X-Serverless-Authorization"] = "Bearer " + _metadata_token(run_origin(origin))
    return result
