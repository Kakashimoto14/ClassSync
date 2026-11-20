"""Optional Google adapters. Never used by registration scanning or timetable generation."""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException
from google.api_core.exceptions import AlreadyExists, Conflict, FailedPrecondition, NotFound
from google.cloud import firestore, storage

from .coursework_schema import Preferences

ADVISORY_DEADLINE_SECONDS = 10


def owner_key(project, tenant, uid):
    return hashlib.sha256((project + "\0" + tenant + "\0" + uid).encode()).hexdigest()


class GoogleCoursework:
    """ADC and private bucket permissions are supplied only by an approved deployment."""

    def __init__(self, settings):
        self.settings = settings

    def preferences(self):
        return firestore.Client(project=self.settings.firebase_project_id)

    @staticmethod
    def view(snapshot):
        if not snapshot.exists:
            raise HTTPException(404, "No saved course preferences")
        value = snapshot.to_dict()
        preferences = Preferences.model_validate(value["preferences"])
        revision = value["revision"]
        if type(revision) is not int or revision < 1:
            raise ValueError("Invalid stored preference revision")
        generation = str(UUID(value["generation"]))
        return {
            "preferences": preferences.model_dump(),
            "revision": revision,
            "generation": generation,
        }

    def preference(self, owner, operation, body=None, revision=None, generation=None):
        client = self.preferences()
        try:
            reference = client.collection("classsync_course_preferences").document(owner)
            if operation == "create":
                result = {
                    "preferences": body.model_dump(),
                    "revision": 1,
                    "generation": str(uuid4()),
                }
                reference.create(result, retry=None, timeout=5)
                return result
            snapshot = reference.get(retry=None, timeout=5)
            current = self.view(snapshot)
            if operation == "read":
                return current
            if current["revision"] != revision or current["generation"] != str(generation):
                raise HTTPException(409, "Preferences changed. Read the current revision.")
            option = firestore.LastUpdateOption(snapshot.update_time)
            if operation == "delete":
                reference.delete(option=option, retry=None, timeout=5)
                return {"deleted": True}
            updates = body.model_dump(
                exclude={"expected_revision", "expected_generation"}, exclude_none=True
            )
            preferences = Preferences.model_validate({**current["preferences"], **updates})
            reference.update(
                {"preferences": preferences.model_dump(), "revision": revision + 1},
                option=option,
                retry=None,
                timeout=5,
            )
            return {
                "preferences": preferences.model_dump(),
                "revision": revision + 1,
                "generation": current["generation"],
            }
        except (AlreadyExists, Conflict, FailedPrecondition) as error:
            raise HTTPException(409, "Preferences changed. Read the current revision.") from error
        except NotFound as error:
            raise HTTPException(404, "No saved course preferences") from error
        finally:
            client.close()

    def private_bucket(self, client):
        bucket = client.bucket(self.settings.course_storage_bucket)
        bucket.reload(retry=None, timeout=5)
        policy = bucket.iam_configuration
        if (
            policy.public_access_prevention != "enforced"
            or not policy.uniform_bucket_level_access_enabled
        ):
            raise HTTPException(503, "Course upload storage privacy is not qualified")
        return bucket

    def upload(self, owner, text):
        client = storage.Client(project=self.settings.firebase_project_id)
        try:
            bucket = self.private_bucket(client)
            identifier = uuid4()
            blob = bucket.blob(f"course-demo/{owner}/{identifier.hex}.txt")
            blob.cache_control = "private, no-store"
            blob.content_disposition = f'attachment; filename="{identifier.hex}.txt"'
            # No original filename, public URL, ACL change or academic evidence is used.
            blob.metadata = {
                "created_at": datetime.now(UTC).isoformat(),
                "purpose": "synthetic-demo",
            }
            blob.upload_from_string(
                text.encode(),
                content_type="text/plain; charset=utf-8",
                if_generation_match=0,
                retry=None,
                timeout=5,
            )
            return {"id": str(identifier), "bytes": len(text.encode()), "private": True}
        finally:
            client.close()

    def file(self, owner, identifier, *, delete=False):
        client = storage.Client(project=self.settings.firebase_project_id)
        try:
            bucket = self.private_bucket(client)
            blob = bucket.blob(f"course-demo/{owner}/{identifier.hex}.txt")
            if delete:
                blob.delete(retry=None, timeout=5)
                return {"deleted": True}
            # A bounded ranged read cannot download an arbitrarily large replaced object.
            value = blob.download_as_bytes(start=0, end=32000, retry=None, timeout=5)
            if len(value) > 32000:
                raise HTTPException(413, "Stored course file exceeds the safe size")
            value.decode("utf-8", errors="strict")
            return value
        except NotFound as error:
            raise HTTPException(404, "Course file not found") from error
        finally:
            client.close()

    def advisory(self, topic):
        subjects = {
            "study-planning": "organizing independent study time",
            "classroom-request-etiquette": "writing a polite classroom change request",
        }
        prompt = (
            "Give two brief general tips about " + subjects[topic] + ". "
            "Do not name courses, people, rooms, actual dates or class times. "
            "Do not decide permissions, enrollment, approvals or timetables. "
            "This is non-sensitive advisory coursework only."
        )
        return asyncio.run(self._advisory(prompt))

    async def _advisory(self, prompt):
        async with (
            asyncio.timeout(ADVISORY_DEADLINE_SECONDS),
            httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client,
        ):
            async with client.stream(
                "POST",
                "https://generativelanguage.googleapis.com/v1beta/models/"
                + self.settings.course_gemini_model
                + ":generateContent",
                headers={"x-goog-api-key": self.settings.gemini_api_key.get_secret_value()},
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"candidateCount": 1, "maxOutputTokens": 160},
                },
            ) as response:
                response.raise_for_status()
                payload = bytearray()
                async for chunk in response.aiter_bytes():
                    payload.extend(chunk)
                    if len(payload) > 64000:
                        raise ValueError("Advisory response exceeds limit")
                result = json.loads(payload)
            candidates = result.get("candidates", [])
            if result.get("promptFeedback", {}).get("blockReason") or not candidates:
                raise HTTPException(503, "Advisory content is unavailable")
            candidate = candidates[0]
            if candidate.get("finishReason") not in {"STOP", "MAX_TOKENS"}:
                raise HTTPException(503, "Advisory content is unavailable")
            text = " ".join(
                part.get("text", "") for part in candidate.get("content", {}).get("parts", [])
            )
            if not text.strip():
                raise HTTPException(503, "Advisory content is unavailable")
            return {"text": text.strip()[:1200], "advisory_only": True}
