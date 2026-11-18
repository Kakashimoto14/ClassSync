"""Private Firestore storage for reviewed academic fields only."""

from datetime import UTC, datetime

from fastapi import HTTPException
from google.api_core.exceptions import GoogleAPIError
from google.cloud import firestore
from pydantic import BaseModel, ConfigDict, model_validator

from .firestore_access import access_key
from .registration_schema import ReviewedAcademicFields


class StoredReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expires_at: datetime
    reviewed: ReviewedAcademicFields | None

    @model_validator(mode="after")
    def timezone_required(self):
        if self.expires_at.utcoffset() is None:
            raise ValueError("Registration expiration requires a timezone")
        return self


def expired_scan():
    return HTTPException(
        404, "This scan is unavailable or expired. Upload again or enter your courses."
    )


class FirestoreRegistrationReviews:
    def __init__(self, client, *, project, tenant, now=lambda: datetime.now(UTC)):
        if client.project != project or not project or not tenant:
            raise ValueError("Explicit Firestore project and tenant required")
        self.client, self.tenant, self.now = client, tenant, now
        self.collection = client.collection("registrationReviews")

    def _document(self, key, tenant, uid):
        if self.tenant != tenant:
            raise expired_scan()
        return self.collection.document(access_key(self.client.project, tenant, uid, str(key)))

    @staticmethod
    def _read(ref, tx=None):
        snap = ref.get(transaction=tx, retry=None, timeout=5)
        return StoredReview.model_validate(snap.to_dict()) if snap.exists else None

    def read(self, key, tenant, uid):
        try:
            record = self._read(self._document(key, tenant, uid))
        except (GoogleAPIError, ValueError, RuntimeError) as error:
            raise HTTPException(503, "Reviewed scans are temporarily unavailable.") from error
        if record is None:
            return None
        if record.reviewed is None or record.expires_at <= self.now():
            raise expired_scan()
        return {
            "id": str(key), "expires_at": record.expires_at.isoformat(),
            "original_retained": False, "method": "reviewed", "status": "reviewed",
            "confidence_available": False, "fields": {}, "courses": [], "warnings": [],
            "reviewed": {**record.reviewed.model_dump(mode="json"), "student_identifier": ""},
        }

    def _write(self, key, tenant, uid, expires_at, reviewed):
        ref = self._document(key, tenant, uid)

        @firestore.transactional
        def write(tx):
            existing = self._read(ref, tx)
            # Keep the original deadline. Erasure leaves only a short-lived marker so an
            # already admitted review cannot recreate the record after deletion.
            deadline = min(existing.expires_at, expires_at) if existing else expires_at
            if deadline <= self.now() or (existing is not None and existing.reviewed is None):
                raise expired_scan()
            tx.set(ref, StoredReview(expires_at=deadline, reviewed=reviewed).model_dump())

        try:
            write(self.client.transaction(max_attempts=3))
        except (GoogleAPIError, ValueError, RuntimeError) as error:
            raise HTTPException(503, "Reviewed scans are temporarily unavailable.") from error

    def save(self, key, tenant, uid, expires_at, review):
        fields = ReviewedAcademicFields.model_validate(
            review.model_dump(exclude={"student_identifier"}),
        )
        self._write(key, tenant, uid, expires_at, fields)

    def erase(self, key, tenant, uid, expires_at):
        self._write(key, tenant, uid, expires_at, None)
