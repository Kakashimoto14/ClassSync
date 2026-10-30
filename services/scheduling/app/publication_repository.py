"""Atomic immutable publication versions and a durable, ordered event log.

Uses the draft database's transaction boundary. Publication never mutates a saved draft.
"""

import json
from uuid import uuid4

from .draft_repository import DraftError, digest, encode, now
from .publication_rules import PublicationRules, overlap

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS publication_heads (
 tenant TEXT NOT NULL,dataset TEXT NOT NULL,period_id TEXT NOT NULL,revision INTEGER NOT NULL,
 PRIMARY KEY(tenant,dataset,period_id))""",
    """CREATE TABLE IF NOT EXISTS published_versions (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT NOT NULL UNIQUE,
 tenant TEXT NOT NULL,dataset TEXT NOT NULL,period_id TEXT NOT NULL,revision INTEGER NOT NULL,
 draft_id TEXT NOT NULL REFERENCES scheduling_drafts(id),
 actor TEXT NOT NULL,created_at TEXT NOT NULL,
 idempotency_key TEXT NOT NULL,request_hash TEXT NOT NULL,
 payload TEXT NOT NULL,checksum TEXT NOT NULL,
 UNIQUE(tenant,dataset,idempotency_key),UNIQUE(tenant,dataset,period_id,revision))""",
    """CREATE TRIGGER IF NOT EXISTS immutable_publication_update
 BEFORE UPDATE ON published_versions
 BEGIN SELECT RAISE(ABORT,'Published versions are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS immutable_publication_delete
 BEFORE DELETE ON published_versions
 BEGIN SELECT RAISE(ABORT,'Publication history is retained'); END""",
    """CREATE TABLE IF NOT EXISTS publication_room_restrictions (
 tenant TEXT NOT NULL,dataset TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,
 PRIMARY KEY(tenant,dataset,id))""",
]


class PublicationRepository(PublicationRules):
    def __init__(self, drafts):
        self.drafts = drafts
        with drafts.connection(write=True) as db:
            for sql in SCHEMA:
                db.execute(sql)

    def rows(self, db, tenant, dataset, period=None):
        sql = "SELECT * FROM published_versions WHERE tenant=? AND dataset=?"
        values = [tenant, dataset]
        if period:
            sql += " AND period_id=?"
            values.append(period)
        return db.execute(sql + " ORDER BY sequence", values).fetchall()

    def head(self, db, tenant, dataset, period):
        row = db.execute(
            "SELECT revision FROM publication_heads WHERE tenant=? AND dataset=? AND period_id=?",
            (tenant, dataset, period),
        ).fetchone()
        return row[0] if row else 0

    def restrictions(self, db, tenant, dataset, events):
        rows = db.execute(
            "SELECT payload FROM publication_room_restrictions WHERE tenant=? AND dataset=?",
            (tenant, dataset),
        ).fetchall()
        restrictions = [json.loads(r[0]) for r in rows]
        for event in events:
            if any(r["room_id"] == event["room"]["id"] and overlap(r, event) for r in restrictions):
                raise DraftError(
                    422,
                    "room_restricted",
                    "Published occupancy overlaps a room restriction or reservation.",
                )

    def publish(self, command, draft, tenant, actor, *, commit):
        self.validate_candidate(command, draft)
        value = encode(command.model_dump(mode="json"))
        with self.drafts.connection(write=True) as db:
            # Re-read immutable draft under the publication write transaction.
            row = db.execute("SELECT * FROM scheduling_drafts WHERE id=?", (draft.id,)).fetchone()
            if row is None or self.drafts.detail(row) != draft:
                raise DraftError(
                    409, "draft_changed", "The permitted saved draft was not found unchanged."
                )
            existing = db.execute(
                "SELECT * FROM published_versions WHERE tenant=? AND dataset=? "
                "AND idempotency_key=?",
                (tenant, command.dataset, command.idempotency_key),
            ).fetchone()
            if existing:
                if existing["request_hash"] != digest(value):
                    raise DraftError(
                        409,
                        "publish_key_conflict",
                        "This publish key belongs to a different command.",
                    )
                return self.summary(existing, db)
            revision = self.head(db, tenant, command.dataset, draft.period_id)
            if revision != command.expected_version:
                raise DraftError(
                    409,
                    "publication_version_conflict",
                    "A competing publication changed this scope. Review the latest version.",
                )
            rows = self.rows(db, tenant, command.dataset)
            report = self.review_scope(db, tenant, command, draft, rows, revision)
            if not commit:
                return report
            duplicate = db.execute(
                "SELECT * FROM published_versions WHERE tenant=? AND dataset=? "
                "AND period_id=? AND draft_id=?",
                (tenant, command.dataset, draft.period_id, draft.id),
            ).fetchall()
            for old in duplicate:
                if self.decode(old)["calendar"] == command.calendar:
                    raise DraftError(
                        409,
                        "duplicate_publication",
                        "This draft and effective calendar have already been published.",
                    )
            identity = str(uuid4())
            created = now()
            payload = encode(
                {
                    "draft": draft.model_dump(mode="json"),
                    "calendar": command.calendar.model_dump(mode="json"),
                    "review": report,
                }
            )
            db.execute(
                "INSERT INTO published_versions "
                "(id,tenant,dataset,period_id,revision,draft_id,actor,"
                "created_at,idempotency_key,request_hash,payload,checksum) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identity,
                    tenant,
                    command.dataset,
                    draft.period_id,
                    revision + 1,
                    draft.id,
                    actor,
                    created,
                    command.idempotency_key,
                    digest(value),
                    payload,
                    digest(payload),
                ),
            )
            db.execute(
                "INSERT INTO publication_heads VALUES (?,?,?,?) "
                "ON CONFLICT(tenant,dataset,period_id) "
                "DO UPDATE SET revision=excluded.revision",
                (tenant, command.dataset, draft.period_id, revision + 1),
            )
            return self.summary(
                db.execute("SELECT * FROM published_versions WHERE id=?", (identity,)).fetchone(),
                db,
            )

    def calendar(self, tenant, dataset, period, start, end, viewer):
        with self.drafts.connection() as db:
            return self.project(db, tenant, dataset, period, start, end, viewer)

    def history(self, tenant, dataset, period):
        with self.drafts.connection() as db:
            return [self.summary(r, db) for r in reversed(self.rows(db, tenant, dataset, period))]
