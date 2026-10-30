"""Actual SDK with in-memory synthetic keys and stubbed network transports only."""

import json
import time
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import firebase_admin
from classync_contracts import token_verification as tokens
from classync_contracts.firebase import FirebaseSettings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from firebase_admin import auth, credentials
from google.auth import crypt, jwt
from google.auth.credentials import AnonymousCredentials


@contextmanager
def offline_firebase(monkeypatch):
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)

    class OfflineCredential(credentials.Base):
        def get_credential(self):
            return AnonymousCredentials()

    app = firebase_admin.initialize_app(
        OfflineCredential(), {"projectId": "synthetic-project"}, name="offline-test-" + str(uuid4())
    )
    try:
        monkeypatch.setattr(tokens, "initialize_firebase", lambda _: app)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public = private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        signer = crypt.RSASigner.from_string(pem, key_id="synthetic-kid")
        client = auth._get_client(app)
        client._token_verifier.request = lambda *args, **kwargs: SimpleNamespace(
            status=200, data=json.dumps({"synthetic-kid": public.decode()}).encode(), headers={}
        )
        user = SimpleNamespace(disabled=False, tokens_valid_after_timestamp=0)
        monkeypatch.setattr(client, "get_user", lambda _: user)
        now = int(time.time())

        def encoded(**changes):
            return jwt.encode(
                signer,
                {
                    "sub": "synthetic-uid",
                    "iss": "https://securetoken.google.com/synthetic-project",
                    "aud": "synthetic-project",
                    "iat": now - 10,
                    "auth_time": now - 10,
                    "exp": now + 600,
                    "role": "administrator",
                    "tenant_id": "forged-tenant",
                    **changes,
                },
            ).decode()

        settings = FirebaseSettings(firebase_project_id="synthetic-project", _env_file=None)
        yield tokens.FirebaseTokenVerifier(settings), encoded, user, client
    finally:
        firebase_admin.delete_app(app)

