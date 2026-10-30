"""Shared publication validation and projections; storage supplied by rows/head ports.

No database connection, provider configuration or publication authority is created.
SQLite and PostgreSQL repositories share these exact domain rules.
"""

import json
from datetime import timedelta

from classync_contracts.calendar import AcademicCalendar
from classync_contracts.scheduling import scheduling_input_hash

from .draft_rules import DraftError, DraftSnapshot, digest, encode, verified_result
from .occurrences import dated_occurrences


def overlap(a, b):
    return a["starts_at"] < b["ends_at"] and b["starts_at"] < a["ends_at"]


class PublicationRules:
    """Composition requires scoped rows/head storage ports; pure checks need neither."""

    @staticmethod
    def validate_academic_scope(command, draft, snapshot, checked):
        if (
            snapshot.period.revision != command.expected_academic_revision
            or not checked.ready
            or checked.inputs is None
        ):
            raise DraftError(
                409,
                "academic_version_conflict",
                "Academic records changed or are no longer ready. Revalidate the saved scope.",
            )
        if scheduling_input_hash(checked.inputs) != draft.input_hash:
            raise DraftError(
                409,
                "academic_input_changed",
                "Saved draft does not match the current academic constraints. "
                "Generate a new revision.",
            )
        saved = snapshot.period.calendar
        if saved is None:
            raise DraftError(
                422, "publication_calendar", "The academic period requires a semester calendar"
            )
        calendar = command.calendar
        if (
            calendar.academic_year != saved.academic_year
            or calendar.semester != saved.semester
            or calendar.instructional_days != saved.instructional_days
            or not saved.effective_start
            <= calendar.effective_start
            <= calendar.effective_end
            <= saved.effective_end
        ):
            raise DraftError(
                422,
                "publication_calendar",
                "Publication dates must stay within the saved academic semester",
            )

    def decode(self, row):
        if digest(row["payload"]) != row["checksum"]:
            raise DraftError(409, "publication_integrity", "Published version integrity failed.")
        try:
            payload = json.loads(row["payload"])
            raw = payload["draft"]
            encoded = encode(raw)
            payload["draft"] = DraftSnapshot().detail(
                {
                    "schema_version": 1,
                    "payload": encoded,
                    "checksum": digest(encoded),
                    "id": raw["id"],
                    "run_id": raw["run_id"],
                    "title": raw["title"],
                    "created_at": raw["created_at"],
                    "owner": raw["creator"],
                    "scope": "academic-sandbox"
                    if raw["source"] == "development-entered"
                    else "administrator",
                }
            )
            draft = payload["draft"]
            for key, expected in (
                ("draft_id", draft.id),
                ("period_id", draft.period_id),
                ("owner_uid", draft.creator),
            ):
                if key in row.keys() and row[key] != expected:
                    raise ValueError("Stored publication envelope differs")
            payload["calendar"] = AcademicCalendar.model_validate(payload["calendar"])
            if not isinstance(payload["review"], dict):
                raise ValueError("Stored review must be an object")
            return payload
        except (ValueError, KeyError, TypeError, DraftError) as error:
            raise DraftError(
                409, "publication_integrity", "Stored publication is corrupt or incompatible."
            ) from error

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
        limits = {}
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
                # Every supplied limit applies to the combined teacher load. A later
                # revision's larger or absent cap cannot erase an earlier constraint.
                if limit is not None:
                    limits[identity] = min(limits.get(identity, limit), limit)
                if identity in limits and loads[identity] > limits[identity]:
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
                    e.student_id == viewer.get("student_id")
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
                    e.student_id
                    == (
                        viewer.get("student_id")
                        if dataset == "institutional"
                        else viewer.get("uid")
                    )
                    and event["offering_id"] in e.offering_ids
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

    def validate_candidate(self, command, draft):
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

    def review_scope(self, db, tenant, command, draft, rows, revision):
        start, end = command.calendar.effective_start, command.calendar.effective_end
        # A partial-week replacement retains older sessions outside its effective
        # dates. Count the entire affected ISO weeks against supplied weekly caps.
        # Include adjacent days too: the supported transition buffer (at most
        # 120 minutes) can cross midnight at an ISO-week boundary.
        review_start = start - timedelta(days=start.weekday() + 1)
        review_end = end + timedelta(days=7 - end.weekday())
        # At most 63 days per expansion call, across the whole effective interval.
        impacted = []
        combined = []
        day = review_start
        while day <= review_end:
            stop = min(day + timedelta(days=62), review_end)
            retained = [
                e for e in self.expanded(rows, day, stop)
                if e["period_id"] != draft.period_id
                or not start.isoformat() <= e["date"] <= end.isoformat()
            ]
            fresh = dated_occurrences(
                draft.input_snapshot,
                draft.generation_result.assignments,
                command.calendar,
                day,
                stop,
            )
            fresh = [{**e, "buffer": draft.input_snapshot.transition_buffer_minutes} for e in fresh]
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
        return report
