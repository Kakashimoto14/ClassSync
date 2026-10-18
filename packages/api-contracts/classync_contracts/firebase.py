import json

import firebase_admin
from firebase_admin import credentials
from pydantic_settings import BaseSettings, SettingsConfigDict


class FirebaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    firebase_project_id: str | None = None
    firebase_service_account_json: str | None = None
    firebase_client_email: str | None = None
    firebase_private_key: str | None = None


def initialize_firebase(settings: FirebaseSettings) -> firebase_admin.App:
    if firebase_admin._apps:
        return firebase_admin.get_app()
    if settings.firebase_service_account_json:
        return firebase_admin.initialize_app(
            credentials.Certificate(json.loads(settings.firebase_service_account_json))
        )
    if all(
        [
            settings.firebase_project_id,
            settings.firebase_client_email,
            settings.firebase_private_key,
        ]
    ):
        certificate = {
            "type": "service_account",
            "project_id": settings.firebase_project_id,
            "client_email": settings.firebase_client_email,
            "private_key": settings.firebase_private_key.replace("\\n", "\n"),
        }
        return firebase_admin.initialize_app(credentials.Certificate(certificate))
    raise RuntimeError("Firebase Admin credentials are not configured")
