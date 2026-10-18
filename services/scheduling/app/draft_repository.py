"""SQLite immutable snapshots. No client result/validation metadata is accepted."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from classync_contracts.scheduling import (
    DraftDetail,
    DraftList,
    DraftSummary,
    GenerationInput,
    GenerationResult,
    SaveDraftRequest,
    scheduling_input_hash,
)
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


class DraftRepository:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self, *, write=False):
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except sqlite3.Error as error:
            if connection:
                connection.rollback()
            raise DraftError(
                503,
                "persistence_unavailable",
                "Draft storage is unavailable; no save was confirmed. Retry safely.",
            ) from error
        except OSError as error:
            raise DraftError(
                503,
                "persistence_unavailable",
                "Cannot open draft storage. Check the configured database path.",
            ) from error
        except Exception:
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()

    def migrate(self):
        with self.connection(write=True) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise DraftError(
                    409,
                    "database_version",
                    "Unsupported database version; restore compatible code or migrate explicitly.",
                )
            if version == 0:
                sql = (Path(__file__).parents[1] / "migrations/001_drafts.sql").read_text()
                # executescript commits implicitly; keep complete statements in our transaction.
                statement = ""
                for line in sql.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        db.execute(statement)
                        statement = ""
                db.execute("PRAGMA user_version=1")
            if version < 2:
                sql = (Path(__file__).parents[1] / "migrations/002_academic_scope.sql").read_text()
                statement = ""
                for line in sql.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        db.execute(statement)
                        statement = ""
                db.execute("PRAGMA user_version=2")
            check = db.execute("PRAGMA quick_check").fetchone()[0]
            if check != "ok" or db.execute("PRAGMA foreign_key_check").fetchone():
                raise DraftError(
                    503,
                    "database_integrity",
                    "Draft database integrity check failed; restore a verified backup.",
                )

    def remember_run(self, inputs, result, scope, owner):
        verified_result(inputs, result)
        payload = encode(
            {"inputs": inputs.model_dump(mode="json"), "result": result.model_dump(mode="json")}
        )
        with self.connection(write=True) as db:
            db.execute(
                "INSERT INTO solver_runs VALUES (?, ?, ?, ?, 1, ?, ?)",
                (result.run_id, scope, owner, now(), payload, digest(payload)),
            )

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

    def save(self, request: SaveDraftRequest, scope, owner):
        with self.connection(write=True) as db:
            existing = db.execute(
                "SELECT * FROM scheduling_drafts WHERE scope=? AND owner=? "
                "AND (idempotency_key=? OR run_id=?)",
                (scope, owner, request.idempotency_key, request.run_id),
            ).fetchall()
            if existing:
                if len(existing) != 1:
                    raise DraftError(
                        409, "idempotency_conflict", "This save key belongs to a different draft."
                    )
                draft = self.detail(existing[0])
                if (draft.run_id, draft.title, draft.input_hash) != (
                    request.run_id,
                    request.title,
                    request.input_hash,
                ):
                    raise DraftError(
                        409,
                        "idempotency_conflict",
                        "This run or save key was used with different details. "
                        "Existing drafts are unchanged.",
                    )
                return draft, False
            row = db.execute(
                "SELECT * FROM solver_runs WHERE id=? AND scope=? AND owner=?",
                (request.run_id, scope, owner),
            ).fetchone()
            if not row:
                raise DraftError(
                    404,
                    "run_not_found",
                    "No permitted server-held run exists. Generate a new timetable first.",
                )
            try:
                created = datetime.fromisoformat(row["created_at"])
                if created.tzinfo is None:
                    raise ValueError("Missing timezone")
            except ValueError as error:
                raise DraftError(
                    409, "snapshot_integrity", "Stored run timestamp is invalid."
                ) from error
            if created < datetime.now(UTC) - timedelta(hours=24):
                raise DraftError(
                    410,
                    "run_expired",
                    "This unsaved run is older than 24 hours. Generate a new candidate.",
                )
            try:
                payload = self.unpack(row)
                inputs = GenerationInput.model_validate(payload["inputs"])
                result = GenerationResult.model_validate(payload["result"])
            except (ValidationError, KeyError, TypeError) as error:
                raise DraftError(
                    409, "snapshot_integrity", "The stored run is incompatible or corrupted."
                ) from error
            validation = verified_result(inputs, result)
            if result.run_id != request.run_id or request.input_hash != result.input_hash:
                raise DraftError(
                    409,
                    "input_version_conflict",
                    "The run and input version differ. No draft was saved.",
                )
            metadata = dict(
                id=str(uuid4()), title=request.title, created_at=now(), owner=owner, scope=scope
            )
            summary = self.make_summary(inputs, result, metadata)
            draft = DraftDetail(
                **summary.model_dump(),
                input_snapshot=inputs,
                generation_result=result,
                validation=validation,
            )
            value = encode(draft.model_dump(mode="json"))
            db.execute(
                "INSERT INTO scheduling_drafts VALUES (?, ?, ?, ?, ?, ?, 1, 'draft', ?, ?, ?)",
                (
                    draft.id,
                    result.run_id,
                    scope,
                    owner,
                    draft.title,
                    draft.created_at,
                    request.idempotency_key,
                    value,
                    digest(value),
                ),
            )
            return draft, True

    def get(self, draft_id, scope, owner):
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM scheduling_drafts WHERE id=? AND scope=? AND owner=?",
                (draft_id, scope, owner),
            ).fetchone()
            if not row:
                raise DraftError(
                    404,
                    "draft_not_found",
                    "This saved draft does not exist in your permitted scope.",
                )
            return self.detail(row)

    def list(self, scope, owner, *, limit=25, offset=0):
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM scheduling_drafts WHERE scope=? AND owner=? "
                "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (scope, owner, limit + 1, offset),
            ).fetchall()
            summaries = [
                DraftSummary.model_validate(
                    self.detail(row).model_dump(include=set(DraftSummary.model_fields))
                )
                for row in rows[:limit]
            ]
            return DraftList(
                drafts=summaries, limit=limit, offset=offset, has_more=len(rows) > limit
            )

    def calendar_samples(self, scope, owner, *, limit=25, offset=0):
        """Read-only discovery uses the same synthetic-data guard as review.

        Entered/institutional snapshots stay out of the anonymous sample chooser.
        Iterate rather than truncating the unfiltered list before applying eligibility.
        """
        allowed = []
        seen = 0
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM scheduling_drafts WHERE scope=? AND owner=? "
                "ORDER BY created_at DESC, id DESC",
                (scope, owner),
            )
            for row in rows:
                draft = self.detail(row)
                if not calendar_review_allowed(draft):
                    continue
                if seen >= offset:
                    allowed.append(
                        DraftSummary.model_validate(
                            draft.model_dump(include=set(DraftSummary.model_fields))
                        )
                    )
                seen += 1
                if len(allowed) > limit:
                    break
        return DraftList(
            drafts=allowed[:limit], limit=limit, offset=offset, has_more=len(allowed) > limit
        )


def calendar_review_allowed(draft):
    return draft.input_snapshot.synthetic and all(
        r.source == "synthetic" for r in draft.input_snapshot.rooms
    )
