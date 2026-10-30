"""Current-owner PostgreSQL runs/drafts; no legacy SQL bridge or service cutover."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from classync_contracts.identity import (
    MembershipAuthorizationError,
    MembershipErrorCode,
    VerifiedPrincipal,
)
from classync_contracts.scheduling import (
    DraftDetail,
    DraftList,
    DraftSummary,
    GenerationInput,
    GenerationResult,
)
from classync_persistence.academic_periods import PostgresAcademicPeriods, utc_timestamp
from classync_persistence.database import transaction
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .draft_rules import DraftError, DraftSnapshot, digest, encode, now, verified_result


class PostgresDraftRepository(DraftSnapshot):
    def __init__(self, engine, *, tenant_id, firebase_project_id, principal: VerifiedPrincipal):
        PostgresAcademicPeriods.validate_principal(principal)
        self.context = PostgresAcademicPeriods(
            engine, tenant_id=tenant_id, firebase_project_id=firebase_project_id
        )
        self.engine, self.principal = engine, principal
        self.keys = {"tenant": tenant_id, "owner": principal.uid}

    @contextmanager
    def session(self, *, write=False):
        try:
            with transaction(self.engine) as db:
                if not write:
                    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                self.context.context(db, self.principal)
                if not db.scalar(
                    text("""
                    SELECT 1 FROM classsync_identity.memberships m
                    JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                    WHERE m.tenant_id=:tenant AND m.uid=:owner AND m.state='active'
                        AND 'administrator'=ANY(m.roles) AND t.firebase_project_id=:project
                """),
                    {**self.keys, "project": self.context.project_id},
                ):
                    raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
                yield db
        except IntegrityError as error:
            raise DraftError(
                409,
                "idempotency_conflict",
                "This run or save key already exists. Existing snapshots are unchanged.",
            ) from error
        except SQLAlchemyError as error:
            raise DraftError(
                503,
                "persistence_unavailable",
                "Draft storage is unavailable; no save was confirmed. Retry safely.",
            ) from error

    @staticmethod
    def metadata(row):
        return {
            **row,
            "owner": row["owner_uid"],
            "scope": "administrator",
            "created_at": utc_timestamp(row["created_at"]),
        }

    def remember_run(self, inputs, result):
        with self.session(write=True) as db:
            verified_result(inputs, result)
            payload = encode(
                {"inputs": inputs.model_dump(mode="json"), "result": result.model_dump(mode="json")}
            )
            db.execute(
                text("""
                INSERT INTO classsync_scheduling.solver_runs
                    (tenant_id,owner_uid,id,created_at,payload,checksum)
                VALUES (:tenant,:owner,:id,:created,:payload,:checksum)
            """),
                {
                    **self.keys,
                    "id": result.run_id,
                    "created": now(),
                    "payload": payload,
                    "checksum": digest(payload),
                },
            )

    def save(self, request):
        with self.session(write=True) as db:
            # One stable transaction lock per verified owner serializes both run and key
            # reuse. Hash collisions only serialize unrelated owners; they grant no access.
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                {"key": encode(["classsync-draft-save", self.keys["tenant"], self.keys["owner"]])},
            )
            rows = (
                db.execute(
                    text("""
                SELECT * FROM classsync_scheduling.drafts
                WHERE tenant_id=:tenant AND owner_uid=:owner
                    AND (idempotency_key=:key OR run_id=:run)
            """),
                    {**self.keys, "key": request.idempotency_key, "run": request.run_id},
                )
                .mappings()
                .all()
            )
            if rows:
                if len(rows) != 1:
                    raise DraftError(
                        409, "idempotency_conflict", "This save key belongs to another draft."
                    )
                if rows[0]["idempotency_key"] != request.idempotency_key:
                    raise DraftError(
                        409,
                        "idempotency_conflict",
                        "This run already has a saved draft. Use its original save key.",
                    )
                draft = self.detail(self.metadata(rows[0]))
                if (draft.run_id, draft.title, draft.input_hash) != (
                    request.run_id,
                    request.title,
                    request.input_hash,
                ):
                    raise DraftError(
                        409,
                        "idempotency_conflict",
                        "This run or save key was used with different details.",
                    )
                return draft, False
            row = (
                db.execute(
                    text("""
                SELECT * FROM classsync_scheduling.solver_runs
                WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:run
            """),
                    {**self.keys, "run": request.run_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DraftError(
                    404,
                    "run_not_found",
                    "No permitted server-held run exists. Generate a new timetable first.",
                )
            if row["created_at"] < datetime.now(UTC) - timedelta(hours=24):
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
                id=str(uuid4()),
                title=request.title,
                created_at=now(),
                owner=self.principal.uid,
                scope="administrator",
            )
            draft = DraftDetail(
                **self.make_summary(inputs, result, metadata).model_dump(),
                input_snapshot=inputs,
                generation_result=result,
                validation=validation,
            )
            value = encode(draft.model_dump(mode="json"))
            db.execute(
                text("""
                INSERT INTO classsync_scheduling.drafts
                    (tenant_id,owner_uid,id,run_id,title,created_at,idempotency_key,payload,checksum)
                VALUES (:tenant,:owner,:id,:run,:title,:created,:key,:payload,:checksum)
            """),
                {
                    **self.keys,
                    "id": draft.id,
                    "run": result.run_id,
                    "title": draft.title,
                    "created": draft.created_at,
                    "key": request.idempotency_key,
                    "payload": value,
                    "checksum": digest(value),
                },
            )
            return draft, True

    def get(self, draft_id):
        with self.session() as db:
            row = (
                db.execute(
                    text("""
                SELECT * FROM classsync_scheduling.drafts
                WHERE tenant_id=:tenant AND owner_uid=:owner AND id=:id
            """),
                    {**self.keys, "id": draft_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise DraftError(
                    404,
                    "draft_not_found",
                    "This saved draft does not exist in your permitted scope.",
                )
            return self.detail(self.metadata(row))

    def list(self, *, limit=25, offset=0):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise DraftError(
                422, "pagination", "Use a page size from 1 to 100 and a nonnegative offset."
            )
        with self.session() as db:
            rows = (
                db.execute(
                    text("""
                SELECT * FROM classsync_scheduling.drafts
                WHERE tenant_id=:tenant AND owner_uid=:owner
                ORDER BY created_at DESC,id DESC LIMIT :limit OFFSET :offset
            """),
                    {**self.keys, "limit": limit + 1, "offset": offset},
                )
                .mappings()
                .all()
            )
            summaries = [
                DraftSummary.model_validate(
                    self.detail(self.metadata(row)).model_dump(
                        include=set(DraftSummary.model_fields)
                    )
                )
                for row in rows[:limit]
            ]
            return DraftList(
                drafts=summaries, limit=limit, offset=offset, has_more=len(rows) > limit
            )
