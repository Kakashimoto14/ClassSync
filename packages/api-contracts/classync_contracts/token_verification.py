"""Identity-verification port and Firebase adapter. Token claims grant no membership."""

import os
from enum import StrEnum
from typing import Protocol

from firebase_admin import auth

from .firebase import FirebaseSettings, initialize_firebase
from .identity import VerifiedPrincipal


class AdapterTrust(StrEnum):
    FIREBASE = "firebase"
    AUTHORITATIVE = "authoritative"
    TEST = "test"
    EMULATOR = "emulator"


class TokenErrorCode(StrEnum):
    REQUIRED = "authentication_required"
    INVALID = "invalid_token"
    EXPIRED = "token_expired"
    REVOKED = "token_revoked"
    UNAVAILABLE = "identity_unavailable"


class TokenVerificationError(Exception):
    def __init__(self, code: TokenErrorCode):
        self.code = code
        super().__init__(code.value)


class TokenVerifier(Protocol):
    trust: AdapterTrust

    def verify(self, token: str) -> VerifiedPrincipal: ...


class FirebaseTokenVerifier:
    trust = AdapterTrust.FIREBASE

    def __init__(self, settings: FirebaseSettings):
        self.settings = settings

    def verify(self, token: str) -> VerifiedPrincipal:
        # Firebase Admin deliberately accepts unsigned emulator tokens when this
        # variable is set. Institutional verification must never inherit that mode.
        if "FIREBASE_AUTH_EMULATOR_HOST" in os.environ:
            raise TokenVerificationError(TokenErrorCode.UNAVAILABLE)
        project = self.settings.firebase_project_id
        if not isinstance(project, str) or not project.strip():
            raise TokenVerificationError(TokenErrorCode.UNAVAILABLE)
        try:
            app = initialize_firebase(self.settings)
            if app.project_id != project:
                raise TokenVerificationError(TokenErrorCode.UNAVAILABLE)
        except TokenVerificationError:
            raise
        except Exception as error:
            raise TokenVerificationError(TokenErrorCode.UNAVAILABLE) from error
        try:
            claims = auth.verify_id_token(token, app=app, check_revoked=True)
        except auth.ExpiredIdTokenError as error:
            raise TokenVerificationError(TokenErrorCode.EXPIRED) from error
        except (auth.RevokedIdTokenError, auth.UserDisabledError) as error:
            raise TokenVerificationError(TokenErrorCode.REVOKED) from error
        except auth.CertificateFetchError as error:
            raise TokenVerificationError(TokenErrorCode.UNAVAILABLE) from error
        except (auth.InvalidIdTokenError, ValueError) as error:
            raise TokenVerificationError(TokenErrorCode.INVALID) from error
        except Exception as error:
            # Includes revocation/account lookup outages: never proceed unverified.
            raise TokenVerificationError(TokenErrorCode.UNAVAILABLE) from error
        try:
            if (
                claims.get("aud") != project
                or claims.get("iss") != f"https://securetoken.google.com/{project}"
                or claims.get("sub") != claims.get("uid")
                # Native Firebase Auth tenants are a separate identity realm.
                # A UID there must not alias a project-level UID. A future
                # explicitly tenant-aware verifier must qualify that integration.
                or claims.get("firebase", {}).get("tenant") is not None
            ):
                raise ValueError("Unexpected verified identity binding")
            return VerifiedPrincipal(uid=claims["uid"])
        except (ValueError, KeyError, AttributeError, TypeError) as error:
            raise TokenVerificationError(TokenErrorCode.INVALID) from error
