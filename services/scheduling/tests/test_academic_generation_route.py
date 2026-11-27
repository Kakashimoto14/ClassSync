"""Regression: POST /api/v1/scheduling/academic/{period}/generate with stored room restrictions.

Production returned HTTP 500 (`AttributeError: 'list' object has no attribute 'effective_start'`)
because `generate_academic` passed the calendar and the restriction list to
`with_room_restrictions` in swapped positions. These tests drive the real route, readiness,
restriction lookup, projection and solver; only identity and the academic source are replaced.
"""

import json
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from services.academic.app.fixtures import import_fixture
from services.academic.app.repository import AcademicRepository
from services.scheduling.app import main
from services.scheduling.app import publication_api as api
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.draft_repository import DraftRepository
from services.scheduling.app.occurrences import ZONE
from services.scheduling.app.publication_repository import PublicationRepository
from services.scheduling.tests.test_calendar import configuration

TENANT = "route-tenant"


@pytest.fixture
def route(tmp_path, monkeypatch):
    academic = AcademicRepository(tmp_path / "academic.db")
    academic.migrate()
    snapshot = import_fixture(academic, configuration(), "sandbox", "test")
    drafts = DraftRepository(tmp_path / "scheduling.db")
    drafts.migrate()
    publication = PublicationRepository(drafts)
    captured = {}

    def remember_run(inputs, result):
        captured["inputs"], captured["result"] = inputs, result

    monkeypatch.setattr(main, "academic_scope", lambda *_: ("administrator", "admin"))
    monkeypatch.setattr(
        main, "connected_repository", lambda *_: SimpleNamespace(remember_run=remember_run)
    )
    monkeypatch.setattr(main, "persisted_academic_snapshot", lambda *_: snapshot)
    monkeypatch.setattr(main.settings, "scheduling_database_url", None)
    monkeypatch.setattr(api, "settings_and_repo", lambda: (main.settings, publication))
    monkeypatch.setattr(
        api, "require_administrator", lambda *_: {"uid": "admin", "tenant_id": TENANT}
    )

    def generate():
        return TestClient(main.app).post(
            f"/api/v1/scheduling/academic/{snapshot.period.id}/generate",
            json={"expected_revision": snapshot.period.revision},
        )

    def restrict(room_id, starts_at, ends_at):
        payload = {"id": "maintenance", "room_id": room_id, "dataset": "institutional",
                   "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat(),
                   "kind": "operational", "reason": "Route regression", "revision": 1}
        with drafts.connection(write=True) as db:
            db.execute(
                "INSERT INTO publication_room_restrictions VALUES (?,?,?,?)",
                (TENANT, "institutional", payload["id"], json.dumps(payload)),
            )

    return SimpleNamespace(snapshot=snapshot, generate=generate, restrict=restrict,
                           captured=captured)


def test_generation_without_any_room_restriction_succeeds(route):
    # The live production case: no stored restrictions at all.
    response = route.generate()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["solver_status"] in {"feasible", "optimal"}
    assert body["hard_conflict_count"] == 0
    # With nothing stored, generation input is exactly the readiness input.
    assert route.captured["inputs"] == academic_readiness(route.snapshot).inputs


def test_dated_restriction_becomes_a_weekly_block_and_is_avoided(route):
    baseline = route.generate()
    assert baseline.status_code == 200, baseline.text
    used = sorted({a["room_id"] for a in baseline.json()["assignments"]})
    calendar = route.snapshot.period.calendar
    # Close the most-used room for one whole week of the term: every weekday is blocked.
    room = max(used, key=lambda r: sum(a["room_id"] == r for a in baseline.json()["assignments"]))
    monday = calendar.effective_start + timedelta(days=(7 - calendar.effective_start.weekday()) % 7)
    begin = datetime.combine(monday, time(), ZONE)
    route.restrict(room, begin, begin + timedelta(days=7))

    response = route.generate()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["solver_status"] in {"feasible", "optimal"}, body["diagnostics"]
    assert room not in {a["room_id"] for a in body["assignments"]}
    blocked = next(r for r in route.captured["inputs"].rooms if r.id == room).blocked
    assert {(w.day, w.start, w.end) for w in blocked} >= {
        (day, 0, 1440) for day in calendar.instructional_days
    }
