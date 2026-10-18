"""Atomic immutable publication versions and a durable, ordered event log.

Uses the draft database's transaction boundary. Publication never mutates a saved draft.
"""

import json
from datetime import timedelta
from uuid import uuid4

from classync_contracts.calendar import AcademicCalendar
from classync_contracts.scheduling import DraftDetail

from .draft_repository import DraftError, digest, encode, now, verified_result
from .occurrences import dated_occurrences

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


def overlap(a, b):
    return a["starts_at"] < b["ends_at"] and b["starts_at"] < a["ends_at"]


class PublicationRepository:
    def __init__(self, drafts):
        self.drafts = drafts
        with drafts.connection(write=True) as db:
            for sql in SCHEMA:
                db.execute(sql)

    def decode(self, row):
        if digest(row["payload"]) != row["checksum"]:
            raise DraftError(409, "publication_integrity", "Published version integrity failed.")
        payload = json.loads(row["payload"])
        payload["draft"] = DraftDetail.model_validate(payload["draft"])
        payload["calendar"] = AcademicCalendar.model_validate(payload["calendar"])
        return payload

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

    def expanded(self, rows, start, end):
        decoded = [(row, self.decode(row)) for row in rows]
        latest = {}
        for row, p in decoded:
            day = max(start, p["calendar"].effective_start)
            while day <= min(end, p["calendar"].effective_end):
                latest[(row["period_id"], day.isoformat())] = row["id"]
                day += timedelta(days=1)
        result = []
        for row, p in decoded:
            for event in dated_occurrences(
                p["draft"].input_snapshot,
                p["draft"].generation_result.assignments,
                p["calendar"],
                start,
                end,
            ):
                if latest.get((row["period_id"], event["date"])) == row["id"]:
                    result.append(
                        {
                            **event,
                            "version": row["id"],
                            "period_id": row["period_id"],
                            "buffer": p["draft"].input_snapshot.transition_buffer_minutes,
                            "students": [
                                enrollment.student_id
                                for enrollment in p["draft"].input_snapshot.enrollments
                                if event["offering_id"] in enrollment.offering_ids
                            ],
                        }
                    )
        return sorted(result, key=lambda o: (o["starts_at"], o["id"]))

    def conflicts(self, events):
        grouped = {}
        loads = {}
        for event in events:
            for kind in ["room", "teacher", "section"]:
                grouped.setdefault((kind, event[kind]["id"]), []).append(event)
            for student in event.get("students", []):
                grouped.setdefault(("student", student), []).append(event)
            from datetime import datetime

            begin = datetime.fromisoformat(event["starts_at"])
            minutes = int((datetime.fromisoformat(event["ends_at"]) - begin).total_seconds() / 60)
            for label, key, limit in [
                ("day", begin.date().isoformat(), event.get("max_daily")),
                ("week", str(begin.date().isocalendar()[:2]), event.get("max_weekly")),
            ]:
                identity = (event["teacher"]["id"], label, key)
                loads[identity] = loads.get(identity, 0) + minutes
                if limit is not None and loads[identity] > limit:
                    raise DraftError(
                        422,
                        "publication_workload",
                        "An effective-dated revision exceeds the teacher workload limit.",
                    )
        for (kind, _), items in grouped.items():
            active = []
            for event in sorted(items, key=lambda e: e["starts_at"]):
                from datetime import datetime

                active = [
                    a
                    for a in active
                    if datetime.fromisoformat(a["ends_at"])
                    + timedelta(minutes=max(a.get("buffer", 0), event.get("buffer", 0)))
                    > datetime.fromisoformat(event["starts_at"])
                ]
                if active:
                    raise DraftError(
                        422,
                        "publication_conflict",
                        f"{kind.title()} conflict between {active[0]['id']} and {event['id']}.",
                    )
                active.append(event)

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
        verified_result(draft.input_snapshot, draft.generation_result)
        if not draft.input_snapshot.all_intended_offerings_supplied:
            raise DraftError(
                422,
                "incomplete_scope",
                "Declare the complete intended offering scope before publication.",
            )
        synthetic = draft.input_snapshot.synthetic
        if (
            synthetic != (command.dataset == "synthetic")
            or (synthetic and any(r.source != "synthetic" for r in draft.input_snapshot.rooms))
            or (not synthetic and any(r.source == "synthetic" for r in draft.input_snapshot.rooms))
        ):
            raise DraftError(
                422,
                "dataset_mismatch",
                "Synthetic and institutional publication datasets cannot be mixed.",
            )
        if command.calendar.published_version:
            raise DraftError(422, "client_version", "Published version is assigned by the server.")
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
            start, end = command.calendar.effective_start, command.calendar.effective_end
            # At most 63 days per expansion call, across the whole effective interval.
            impacted = []
            combined = []
            day = start
            while day <= end:
                stop = min(day + timedelta(days=62), end)
                retained = [
                    e for e in self.expanded(rows, day, stop) if e["period_id"] != draft.period_id
                ]
                fresh = dated_occurrences(
                    draft.input_snapshot,
                    draft.generation_result.assignments,
                    command.calendar,
                    day,
                    stop,
                )
                fresh = [
                    {**e, "buffer": draft.input_snapshot.transition_buffer_minutes} for e in fresh
                ]
                combined.extend(retained + fresh)
                if len(combined) > 100000:
                    raise DraftError(
                        413,
                        "publication_scope_limit",
                        "Limit publication to 100,000 dated occurrences per review.",
                    )
                self.restrictions(db, tenant, command.dataset, fresh)
                impacted += fresh
                day = stop + timedelta(days=1)
            self.conflicts(combined)
            report = {
                "status": "ready-for-review",
                "current_revision": revision,
                "sections": len({e["section"]["id"] for e in impacted}),
                "teachers": len({e["teacher"]["id"] for e in impacted}),
                "rooms": len({e["room"]["id"] for e in impacted}),
                "occurrences": len(impacted),
            }
            if not impacted:
                raise DraftError(
                    422,
                    "empty_publication",
                    "No instructional occurrences fall in this effective interval.",
                )
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

    def summary(self, row, db):
        payload = self.decode(row)
        return {
            "id": row["id"],
            "sequence": row["sequence"],
            "revision": row["revision"],
            "period_id": row["period_id"],
            "draft_id": row["draft_id"],
            "actor": row["actor"],
            "created_at": row["created_at"],
            "dataset": row["dataset"],
            "status": "published"
            if row["revision"] == self.head(db, row["tenant"], row["dataset"], row["period_id"])
            else "superseded",
            "calendar": payload["calendar"].model_dump(mode="json"),
            "review": payload["review"],
        }

    def project(self, db, tenant, dataset, period, start, end, viewer):
        rows = self.rows(db, tenant, dataset, period)
        if not rows:
            raise DraftError(
                404, "not_published", "No timetable has been published for this period."
            )
        decoded = [self.decode(r) for r in rows]
        if dataset == "institutional" and viewer["role"] != "administrator":
            eligible = (
                any(
                    e.student_id == viewer["uid"]
                    for p in decoded
                    for e in p["draft"].input_snapshot.enrollments
                )
                if viewer["role"] == "student"
                else any(
                    a.teacher_id == viewer.get("faculty_id")
                    for p in decoded
                    for a in p["draft"].generation_result.assignments
                )
            )
            if not eligible:
                raise DraftError(
                    403,
                    "projection_forbidden",
                    "This identity is not assigned to the published period.",
                )
        by_version = {r["id"]: p for r, p in zip(rows, decoded, strict=True)}
        events = self.expanded(rows, start, end)
        if viewer["role"] == "student":

            def enrolled(event):
                source = by_version[event["version"]]["draft"].input_snapshot
                if dataset == "synthetic" and viewer.get("mock_section"):
                    return event["section"]["id"] == viewer["mock_section"]
                return any(
                    e.student_id == viewer["uid"] and event["offering_id"] in e.offering_ids
                    for e in source.enrollments
                )

            events = [e for e in events if enrolled(e)]
        if viewer["role"] == "teacher":
            events = [e for e in events if e["teacher"]["id"] == viewer.get("faculty_id")]
        latest = decoded[-1]
        source = latest["draft"].input_snapshot
        # Role projections contain only the selected identity's sessions.
        sections = (
            [s.model_dump() for s in source.sections]
            if dataset == "synthetic" or viewer["role"] == "administrator"
            else []
        )
        teachers = (
            [t.model_dump() for t in source.teachers]
            if dataset == "synthetic" or viewer["role"] == "administrator"
            else []
        )
        for e in events:
            e.pop("buffer", None)
            e.pop("max_daily", None)
            e.pop("max_weekly", None)
            e.pop("students", None)
        calendar = latest["calendar"].model_dump(mode="json")
        calendar["published_version"] = rows[-1]["id"]
        return {
            "version": rows[-1]["id"],
            "sequence": rows[-1]["sequence"],
            "revision": rows[-1]["revision"],
            "status": "published",
            "dataset": dataset,
            "calendar": calendar,
            "sections": sections,
            "teachers": teachers,
            "occurrences": events,
        }

    def calendar(self, tenant, dataset, period, start, end, viewer):
        with self.drafts.connection() as db:
            return self.project(db, tenant, dataset, period, start, end, viewer)

    def history(self, tenant, dataset, period):
        with self.drafts.connection() as db:
            return [self.summary(r, db) for r in reversed(self.rows(db, tenant, dataset, period))]
