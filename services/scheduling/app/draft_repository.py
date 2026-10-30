"""SQLite immutable snapshots. No client result/validation metadata is accepted."""

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
)
from pydantic import ValidationError

from .draft_rules import (
    DraftError as DraftError,
)
from .draft_rules import (
    DraftSnapshot,
)
from .draft_rules import (
    digest as digest,
)
from .draft_rules import (
    encode as encode,
)
from .draft_rules import (
    now as now,
)
from .draft_rules import (
    verified_result as verified_result,
)


class DraftRepository(DraftSnapshot):
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
