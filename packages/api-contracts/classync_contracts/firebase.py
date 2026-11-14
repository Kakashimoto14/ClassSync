import json
import os
from threading import Lock

import firebase_admin
from firebase_admin import credentials
from pydantic_settings import BaseSettings, SettingsConfigDict

_ADC_INITIALIZATION = Lock()


class FirebaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    firebase_project_id: str | None = None
    firebase_service_account_json: str | None = None
    firebase_client_email: str | None = None
    firebase_private_key: str | None = None
    firebase_use_adc: bool = False


def initialize_firebase(settings: FirebaseSettings) -> firebase_admin.App:
    if settings.firebase_use_adc:
        if (
            not settings.firebase_project_id or not settings.firebase_project_id.strip()
            or settings.firebase_service_account_json or settings.firebase_client_email
            or settings.firebase_private_key or "FIREBASE_AUTH_EMULATOR_HOST" in os.environ
        ):
            raise RuntimeError("ADC requires an explicit Firebase project and no key or emulator")
        name = "classsync-adc-" + settings.firebase_project_id
        with _ADC_INITIALIZATION:
            try:
                app = firebase_admin.get_app(name)
            except ValueError:
                app = firebase_admin.initialize_app(
                    options={"projectId": settings.firebase_project_id}, name=name
                )
        if (app.project_id != settings.firebase_project_id
                or not isinstance(app.credential, credentials.ApplicationDefault)):
            raise RuntimeError("Firebase ADC project mismatch")
        return app
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass
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
