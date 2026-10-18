import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import httpx
import pytest
from classync_contracts.scheduling import SaveDraftRequest
from fastapi.testclient import TestClient

from services.gateway.app import main as gateway
from services.scheduling.app import main
from services.scheduling.app.draft_repository import (
    DraftError,
    DraftRepository,
    digest,
    encode,
    now,
)
from services.scheduling.app.engine import generate_week
from services.scheduling.tests.test_engine import tiny


@pytest.fixture
def repo(tmp_path):
    value = DraftRepository(tmp_path / "drafts.sqlite3")
    value.migrate()
    return value


@pytest.fixture
def candidate():
    inputs = tiny()
    return inputs, generate_week(inputs)


def request(result, **kwargs):
    return SaveDraftRequest(
        run_id=result.run_id,
        input_hash=result.input_hash,
        title="Review week",
        idempotency_key="test-key-1234",
        **kwargs,
    )


def seed(repo, candidate):
    inputs, result = candidate
    repo.remember_run(inputs, result, "sandbox", "development-sandbox")
    return request(result)


def test_save_retrieve_exact_snapshot_and_new_process(repo, candidate):
    body = seed(repo, candidate)
    draft, created = repo.save(body, "sandbox", "development-sandbox")
    assert created
    assert draft.generation_result == candidate[1]
    assert draft.input_snapshot == candidate[0]
    assert draft.period_id == candidate[0].period_id
    assert draft.data_version == candidate[0].data_version
    assert draft.required_minutes == draft.allocated_minutes == 180
    assert draft.source == "synthetic-preview" and not draft.published
    script = """
import sys
from services.scheduling.app.draft_repository import DraftRepository
repo = DraftRepository(sys.argv[1]); repo.migrate()
print(repo.get(sys.argv[2], 'sandbox', 'development-sandbox').model_dump_json())
"""
    reopened = subprocess.check_output(
        [sys.executable, "-c", script, str(repo.path), draft.id], text=True
    )
    assert json.loads(reopened) == draft.model_dump(mode="json")
    listing = repo.list("sandbox", "development-sandbox", limit=1)
    assert [d.id for d in listing.drafts] == [draft.id] and not listing.has_more


def test_idempotent_concurrent_saves_no_overwrite(repo, candidate):
    body = seed(repo, candidate)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: repo.save(body, "sandbox", "development-sandbox"), range(4))
        )
    assert len({d.id for d, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    other_key = body.model_copy(update={"idempotency_key": "another-key"})
    assert not repo.save(other_key, "sandbox", "development-sandbox")[1]
    with pytest.raises(DraftError) as caught:
        repo.save(body.model_copy(update={"title": "Overwrite"}), "sandbox", "development-sandbox")
    assert caught.value.status == 409
    assert repo.list("sandbox", "development-sandbox").drafts[0].title == body.title


@pytest.mark.parametrize(
    "alter", ["infeasible", "unknown", "incomplete", "forged", "minutes", "hash"]
)
def test_invalid_server_result_cannot_be_registered_or_saved(repo, candidate, alter):
    inputs, original = candidate
    result = deepcopy(original)
    if alter in {"infeasible", "unknown"}:
        result.solver_status = alter
    elif alter == "incomplete":
        result.total_offerings_scheduled = 0
    elif alter == "forged":
        result.validation.hard_conflict_count = 9
    elif alter == "minutes":
        result.assignments[0].end -= 30
    else:
        result.input_hash = "0" * 64
    with pytest.raises(DraftError, match="complete validated"):
        repo.remember_run(inputs, result, "sandbox", "development-sandbox")
    # Recomputed checksum is not a substitute for independent validation at save time.
    payload = encode(
        {"inputs": inputs.model_dump(mode="json"), "result": result.model_dump(mode="json")}
    )
    with repo.connection(write=True) as db:
        db.execute(
            "INSERT INTO solver_runs VALUES (?, 'sandbox', 'development-sandbox', ?, 1, ?, ?)",
            (result.run_id, now(), payload, digest(payload)),
        )
    with pytest.raises(DraftError):
        repo.save(request(original), "sandbox", "development-sandbox")
    assert not repo.list("sandbox", "development-sandbox").drafts


def test_transaction_failure_then_retry(repo, candidate):
    body = seed(repo, candidate)
    with repo.connection(write=True) as db:
        db.execute(
            "CREATE TRIGGER fail_save BEFORE INSERT ON scheduling_drafts "
            "BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
    with pytest.raises(DraftError) as caught:
        repo.save(body, "sandbox", "development-sandbox")
    assert caught.value.status == 503
    assert not repo.list("sandbox", "development-sandbox").drafts
    with repo.connection(write=True) as db:
        db.execute("DROP TRIGGER fail_save")
    assert repo.save(body, "sandbox", "development-sandbox")[1]


def test_missing_scope_expired_version_and_corruption(repo, candidate):
    body = seed(repo, candidate)
    for scope, owner in [("administrator", "development-sandbox"), ("sandbox", "other")]:
        with pytest.raises(DraftError) as caught:
            repo.save(body, scope, owner)
        assert caught.value.status == 404
    with repo.connection(write=True) as db:
        db.execute("UPDATE solver_runs SET created_at='2000-01-01T00:00:00+00:00'")
    with pytest.raises(DraftError) as caught:
        repo.save(body, "sandbox", "development-sandbox")
    assert caught.value.status == 410
    with repo.connection(write=True) as db:
        db.execute("UPDATE solver_runs SET created_at='2099-01-01T00:00:00+00:00'")
    draft, _ = repo.save(body, "sandbox", "development-sandbox")
    with pytest.raises(DraftError) as caught:
        repo.get("missing", "sandbox", "development-sandbox")
    assert caught.value.status == 404
    with repo.connection(write=True) as db:
        db.execute("DROP TRIGGER immutable_draft")
        db.execute("UPDATE scheduling_drafts SET checksum='corrupt'")
    with pytest.raises(DraftError) as caught:
        repo.get(draft.id, "sandbox", "development-sandbox")
    assert caught.value.code == "snapshot_integrity"
    with repo.connection(write=True) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(DraftError) as caught:
        repo.migrate()
    assert caught.value.code == "database_version"


def test_migration_idempotent_and_database_unavailable(repo, tmp_path):
    repo.migrate()
    with sqlite3.connect(repo.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    broken = tmp_path / "broken.sqlite3"
    broken.write_text("not a SQLite database")
    with pytest.raises(DraftError) as caught:
        DraftRepository(broken).migrate()
    assert caught.value.status == 503


def test_incompatible_snapshot_and_immutable_storage(repo, candidate):
    body = seed(repo, candidate)
    draft, _ = repo.save(body, "sandbox", "development-sandbox")
    with pytest.raises(DraftError):
        with repo.connection(write=True) as db:
            db.execute("UPDATE scheduling_drafts SET title='Changed'")
    assert repo.get(draft.id, "sandbox", "development-sandbox").title == body.title
    with repo.connection(write=True) as db:
        db.execute("DROP TRIGGER immutable_draft")
        payload = draft.model_dump(mode="json")
        payload["schema_version"] = 2
        value = encode(payload)
        db.execute("UPDATE scheduling_drafts SET payload=?, checksum=?", (value, digest(value)))
    with pytest.raises(DraftError) as caught:
        repo.get(draft.id, "sandbox", "development-sandbox")
    assert caught.value.status == 409


def test_new_run_creates_separate_draft_and_old_snapshot_is_unchanged(repo, candidate):
    from services.scheduling.app.catalog import synthetic_scenario

    first_body = seed(repo, candidate)
    first, _ = repo.save(first_body, "sandbox", "development-sandbox")
    inputs = synthetic_scenario()
    inputs.options.time_limit_seconds = 8.0
    result = generate_week(inputs)
    repo.remember_run(inputs, result, "sandbox", "development-sandbox")
    second_body = request(result).model_copy(
        update={"idempotency_key": "second-key", "title": "New batch"}
    )
    second, _ = repo.save(second_body, "sandbox", "development-sandbox")
    assert second.id != first.id
    assert repo.get(first.id, "sandbox", "development-sandbox") == first
    assert (
        repo.get(second.id, "sandbox", "development-sandbox").generation_result.assignments
        == result.assignments
    )
    assert second.offerings_scheduled == 12 and second.allocated_minutes == 2160
    assert repo.list("sandbox", "development-sandbox", limit=1).has_more


@pytest.fixture
def api(monkeypatch):
    for config in (gateway.settings, main.settings):
        monkeypatch.setattr(config, "classsync_env", "development")
        monkeypatch.setattr(config, "enable_scheduling_sandbox", True)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        gateway.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.ASGITransport(app=main.app), **kw),
    )
    return TestClient(gateway.app)


def test_real_gateway_draft_workflow_and_forgery(api):
    prefix = "/api/v1/scheduling/sandbox"
    run = api.post(prefix + "/generate", json=tiny().model_dump(mode="json")).json()["data"]
    body = {
        "run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "title": "API week",
        "idempotency_key": "api-save-123",
    }
    forged = api.post(
        prefix + "/drafts", json={**body, "assignments": [], "validation": {"valid": True}}
    )
    assert forged.status_code == 422
    saved = api.post(prefix + "/drafts", json=body)
    assert saved.status_code == 201, saved.text
    draft = saved.json()["data"]
    assert draft["generation_result"]["assignments"] == run["assignments"]
    assert api.post(prefix + "/drafts", json=body).status_code == 200
    assert api.get(prefix + "/drafts").json()["data"]["drafts"][0]["id"] == draft["id"]
    assert api.get(prefix + "/drafts/" + draft["id"]).json()["data"] == draft
    assert api.get(prefix + "/drafts/00000000-0000-0000-0000-000000000000").status_code == 404
    assert api.post(prefix + "/publish", json={}).status_code == 404
    wrong = {**body, "input_hash": "0" * 64}
    assert api.post(prefix + "/drafts", json=wrong).status_code == 409
    for suffix in ("drafts", "drafts/" + draft["id"]):
        assert api.get("/api/v1/scheduling/" + suffix).status_code == 401
    assert (
        api.post(
            "/api/v1/scheduling/drafts", json=body, headers={"X-Role": "administrator"}
        ).status_code
        == 401
    )


def test_gateway_database_failure_is_explicit_and_retry_is_safe(api, tmp_path, monkeypatch):
    prefix = "/api/v1/scheduling/sandbox"
    run = api.post(prefix + "/generate", json=tiny().model_dump(mode="json")).json()["data"]
    body = {
        "run_id": run["run_id"],
        "input_hash": run["input_hash"],
        "title": "Retry save",
        "idempotency_key": "retry-key-123",
    }
    original_path = main.settings.scheduling_database_path
    blocked_path = tmp_path / "directory-not-database"
    blocked_path.mkdir()
    monkeypatch.setattr(main.settings, "scheduling_database_path", str(blocked_path))
    response = api.post(prefix + "/drafts", json=body)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "persistence_unavailable"
    assert response.json()["error"]["requestId"]
    monkeypatch.setattr(main.settings, "scheduling_database_path", original_path)
    assert api.post(prefix + "/drafts", json=body).status_code == 201
    assert len(api.get(prefix + "/drafts").json()["data"]["drafts"]) == 1


def test_protected_owner_isolation_and_sandbox_gating(api, monkeypatch):
    from classync_contracts import scheduling_security

    monkeypatch.setattr(scheduling_security, "initialize_firebase", lambda *_: None)
    identity = {"uid": "admin-a", "role": "administrator"}
    monkeypatch.setattr(scheduling_security.auth, "verify_id_token", lambda *_, **__: identity)
    headers = {"Authorization": "Bearer verified-test"}
    prefix = "/api/v1/scheduling"
    run = api.post(
        prefix + "/generate", headers=headers, json=tiny().model_dump(mode="json")
    ).json()["data"]
    saved = api.post(
        prefix + "/drafts",
        headers=headers,
        json={
            "run_id": run["run_id"],
            "input_hash": run["input_hash"],
            "title": "Private draft",
            "idempotency_key": "private-key",
        },
    ).json()["data"]
    assert api.get(prefix + "/sandbox/drafts").json()["data"]["drafts"] == []
    assert api.get(prefix + "/sandbox/drafts/" + saved["id"]).status_code == 404
    identity["uid"] = "admin-b"
    assert api.get(prefix + "/drafts", headers=headers).json()["data"]["drafts"] == []
    assert api.get(prefix + "/drafts/" + saved["id"], headers=headers).status_code == 404
    identity["role"] = "teacher"
    assert api.get(prefix + "/drafts", headers=headers).status_code == 403
    for config in (gateway.settings, main.settings):
        monkeypatch.setattr(config, "classsync_env", "production")
    assert api.get(prefix + "/sandbox/drafts").status_code == 403


def test_calendar_discovery_excludes_entered_and_other_owner_drafts(api, repo, monkeypatch):
    monkeypatch.setattr(main, "repository", lambda: repo)
    allowed = []
    for index, (synthetic, owner) in enumerate(
        [
            (True, "development-academic-sandbox"),
            (False, "development-academic-sandbox"),
            (True, "other-owner"),
            (True, "development-academic-sandbox"),
        ]
    ):
        inputs = tiny()
        inputs.period_id = f"review-test-{index}"
        inputs.synthetic = synthetic
        if not synthetic:
            inputs.rooms[0].source = "administrator-supplied"
        result = generate_week(inputs)
        repo.remember_run(inputs, result, "academic-sandbox", owner)
        saved, _ = repo.save(
            SaveDraftRequest(
                run_id=result.run_id,
                input_hash=result.input_hash,
                title=f"Review {index}",
                idempotency_key=f"review-key-{index}",
            ),
            "academic-sandbox",
            owner,
        )
        if synthetic and owner == "development-academic-sandbox":
            allowed.append(saved.id)
        elif not synthetic:
            blocked = saved.id
    endpoint = "/api/v1/scheduling/sandbox/calendar-samples"
    response = api.get(endpoint + "?limit=1")
    assert response.status_code == 200, response.text
    first = response.json()["data"]
    second = api.get(endpoint + "?limit=1&offset=1").json()["data"]
    assert first["has_more"] and not second["has_more"]
    assert {first["drafts"][0]["id"], second["drafts"][0]["id"]} == set(allowed)
    assert "input_snapshot" not in first["drafts"][0]
    denied = api.get(
        f"/api/v1/scheduling/sandbox/calendar/{blocked}?start=2026-10-01&end=2026-10-31"
    )
    assert denied.status_code == 403
    assert api.post(endpoint).status_code == 404
    monkeypatch.setattr(gateway.settings, "classsync_env", "production")
    assert api.get(endpoint).status_code == 403
