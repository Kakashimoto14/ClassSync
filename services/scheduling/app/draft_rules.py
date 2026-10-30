"""Shared scheduling snapshot integrity and independently validated draft contracts."""

import hashlib
import json
from datetime import UTC, datetime

from classync_contracts.scheduling import DraftDetail, DraftSummary, scheduling_input_hash
from pydantic import ValidationError

from .validation import validate_timetable


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def now():
    return datetime.now(UTC).isoformat()


class DraftError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code = status, code


def verified_result(inputs, result):
    validation = validate_timetable(inputs, result.assignments)
    if (
        result.solver_status not in {"feasible", "optimal"}
        or result.input_hash != scheduling_input_hash(inputs)
        or result.period_id != inputs.period_id
        or result.data_version != inputs.data_version
        or result.total_offerings_requested != len(inputs.offerings)
        or result.total_offerings_scheduled != len(inputs.offerings)
        or not validation.valid
        or validation.hard_conflict_count != 0
        or result.validation != validation
        or result.coverage != validation.coverage
        or result.hard_conflict_count != 0
    ):
        raise DraftError(
            422, "invalid_generated_run", "The server run is not a complete validated timetable."
        )
    return validation


class DraftSnapshot:
    def unpack(self, row):
        if row["schema_version"] != 1:
            raise DraftError(
                409, "snapshot_version", "This stored snapshot requires a different schema version."
            )
        if digest(row["payload"]) != row["checksum"]:
            raise DraftError(
                409,
                "snapshot_integrity",
                "Stored snapshot integrity failed; no timetable was accepted.",
            )
        try:
            return json.loads(row["payload"])
        except ValueError as error:
            raise DraftError(
                409, "snapshot_integrity", "Stored snapshot cannot be decoded."
            ) from error

    def detail(self, row):
        try:
            draft = DraftDetail.model_validate(self.unpack(row))
            if any(
                getattr(draft, key) != row[key] for key in ("id", "run_id", "title", "created_at")
            ):
                raise ValueError("Stored metadata differs")
            if draft.creator != row["owner"]:
                raise ValueError("Stored owner differs")
            validation = verified_result(draft.input_snapshot, draft.generation_result)
            expected = self.make_summary(draft.input_snapshot, draft.generation_result, row)
            summary = DraftSummary.model_validate(
                draft.model_dump(include=set(DraftSummary.model_fields))
            )
            if summary != expected or draft.validation != validation:
                raise ValueError("Stored coverage differs")
            if row["scope"] == "sandbox" and (
                not draft.input_snapshot.synthetic
                or any(r.source != "synthetic" for r in draft.input_snapshot.rooms)
            ):
                raise ValueError("Sandbox source differs")
            return draft
        except (ValidationError, ValueError, DraftError) as error:
            if isinstance(error, DraftError) and error.code in {
                "snapshot_version",
                "snapshot_integrity",
            }:
                raise
            raise DraftError(
                409,
                "snapshot_integrity",
                "Stored draft validation failed; it cannot be displayed as valid.",
            ) from error

    def make_summary(self, inputs, result, row):
        return DraftSummary(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            creator=row["owner"],
            period_id=inputs.period_id,
            source=(
                "development-entered"
                if row["scope"] == "academic-sandbox"
                else "synthetic-preview"
                if inputs.synthetic
                else "institutional"
            ),
            run_id=result.run_id,
            input_hash=result.input_hash,
            data_version=inputs.data_version,
            solver_status=result.solver_status,
            session_count=len(result.assignments),
            offerings_requested=result.total_offerings_requested,
            offerings_scheduled=result.total_offerings_scheduled,
            required_minutes=sum(c.required_minutes for c in result.coverage),
            allocated_minutes=sum(c.allocated_minutes for c in result.coverage),
        )
