"""Explicit local demo-project emulator support; application runtime must not import."""

import os
import re
import time
from contextlib import contextmanager
from uuid import uuid4

import firebase_admin
from classync_contracts.identity import VerifiedPrincipal
from classync_contracts.token_verification import (
    AdapterTrust,
    TokenErrorCode,
    TokenVerificationError,
)
from firebase_admin import auth, credentials
from google.auth.credentials import AnonymousCredentials


@contextmanager
def emulator_firebase(monkeypatch, *, project: str, endpoint: str):
    if not re.fullmatch(r"demo-[a-z0-9-]{1,40}", project):
        raise ValueError("Synthetic demo project required")
    match = re.fullmatch(r"127\.0\.0\.1:([0-9]{4,5})", endpoint)
    if not match or not 1024 < int(match[1]) < 65536:
        raise ValueError("Explicit loopback emulator endpoint required")

    class AnonymousCredential(credentials.Base):
        def get_credential(self):
            return AnonymousCredentials()

    # Caller owns the emulator process and endpoint. Never resolve ADC or a real
    # project's service account; this helper is exclusively injected by tests.
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", endpoint)
    app = firebase_admin.initialize_app(
        AnonymousCredential(), {"projectId": project}, name="emulator-test-" + uuid4().hex,
    )
    try:
        class EmulatorVerifier:
            trust = AdapterTrust.EMULATOR

            def verify(self, token):
                if os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") != endpoint:
                    raise TokenVerificationError(TokenErrorCode.UNAVAILABLE)
                try:
                    claims = auth.verify_id_token(token, app=app, check_revoked=True)
                    # The SDK deliberately skips Google signature/time validation
                    # for emulator JWTs. Preserve lifecycle fidelity explicitly.
                    now = int(time.time())
                    if any(type(claims.get(key)) is not int
                           for key in ("exp", "iat", "auth_time")):
                        raise ValueError("Invalid emulator token times")
                    if claims["exp"] <= now:
                        raise TokenVerificationError(TokenErrorCode.EXPIRED)
                    if not 0 <= claims["auth_time"] <= claims["iat"] <= now:
                        raise ValueError("Invalid emulator issue/authentication times")
                    if (claims.get("aud") != project
                            or claims.get("iss") != f"https://securetoken.google.com/{project}"
                            or claims.get("sub") != claims.get("uid")
                            or not isinstance(claims.get("firebase", {}), dict)
                            or claims.get("firebase", {}).get("tenant") is not None):
                        raise ValueError("Invalid emulator identity realm")
                    return VerifiedPrincipal(uid=claims["uid"])
                except TokenVerificationError:
                    raise
                except (auth.UserDisabledError, auth.RevokedIdTokenError) as error:
                    raise TokenVerificationError(TokenErrorCode.REVOKED) from error
                except auth.ExpiredIdTokenError as error:
                    raise TokenVerificationError(TokenErrorCode.EXPIRED) from error
                except (auth.InvalidIdTokenError, ValueError, KeyError, TypeError) as error:
                    raise TokenVerificationError(TokenErrorCode.INVALID) from error
                except Exception as error:
                    raise TokenVerificationError(TokenErrorCode.UNAVAILABLE) from error

        yield EmulatorVerifier(), app
    finally:
        firebase_admin.delete_app(app)
