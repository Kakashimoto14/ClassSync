from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.gateway.app import main
from services.gateway.app.announcements import NoticeEdit, NoticeInput

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}
BODY = {"title": "Synthetic notice", "body": "Invented qualification text", "audience": ["student"]}


def test_announcement_identity_role_and_no_fallback(identity_adapters, monkeypatch):
    client = TestClient(main.app)
    identity_adapters(main, role="student")
    monkeypatch.delattr(main.app.state, "announcements_repository", raising=False)
    assert client.get("/api/v1/community/announcements").status_code == 401
    assert client.get("/api/v1/community/announcements", headers=HEADERS).status_code == 503
    assert (
        client.post("/api/v1/community/announcements", headers=HEADERS, json=BODY).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/community/announcements",
            headers={**HEADERS, "X-ClassSync-Role": "administrator"},
            json=BODY,
        ).status_code
        == 403
    )


def test_announcement_admin_crud_preserves_revision_and_no_store(identity_adapters, monkeypatch):
    identity_adapters(main, role="administrator")
    repo = Mock()
    repo.list.return_value = {"announcements": []}
    repo.create.return_value = {"id": str(uuid4()), **BODY, "revision": 1}
    repo.change.return_value = {"revision": 2}
    monkeypatch.setattr(main.app.state, "announcements_repository", repo, raising=False)
    client = TestClient(main.app)
    path = "/api/v1/community/announcements"
    read = client.get(path, headers=HEADERS)
    assert read.status_code == 200 and read.headers["cache-control"] == "no-store"
    created = client.post(path, headers=HEADERS, json=BODY)
    assert created.status_code == 201
    notice = created.json()["data"]["id"]
    assert (
        client.patch(
            path + "/" + notice, headers=HEADERS, json={**BODY, "expected_revision": 1}
        ).status_code
        == 200
    )
    assert repo.change.call_args.args[2] == 1
    assert (
        client.delete(path + "/" + notice + "?expected_revision=2", headers=HEADERS).status_code
        == 200
    )
    assert repo.change.call_args.args[2] == 2
    assert client.delete(path + "/" + notice, headers=HEADERS).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"tenant_id": "other"},
        {"created_by": "other"},
        {"revision": 1},
        {"audience": []},
        {"audience": ["administrator", "administrator"]},
        {"audience": ["public"]},
        {"body": "x" * 3001},
        {"title": " "},
    ],
)
def test_notice_rejects_untrusted_scope_and_unbounded_content(change):
    with pytest.raises(ValidationError):
        NoticeInput.model_validate({**BODY, **change})


def test_notice_edit_requires_strict_revision():
    with pytest.raises(ValidationError):
        NoticeEdit.model_validate({**BODY, "expected_revision": True})
