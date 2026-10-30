import asyncio
from datetime import date
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers

from services.scheduling.app import main
from services.scheduling.app import publication_api as api


@pytest.mark.parametrize("change", ["revoked", "outage", "record_reassigned"])
def test_open_institutional_stream_stops_on_membership_change(
    identity_adapters, monkeypatch, change
):
    _, memberships = identity_adapters(main, "student")

    class Publication:
        calls = 0

        def calendar(self, *args):
            self.calls += 1
            return {"sequence": self.calls, "version": "synthetic-version"}

    publication = Publication()
    monkeypatch.setattr(api, "settings_and_repo", lambda: (main.settings, publication))

    async def connected():
        return False

    request = SimpleNamespace(
        app=main.app,
        headers=Headers({"Authorization": "Bearer e30.e30.synthetic-signature"}),
        is_disconnected=connected,
    )

    async def consume():
        response = await api.stream(
            "synthetic-period",
            request,
            False,
            date(2026, 10, 1),
            date(2026, 10, 31),
            "student",
            "",
            "",
            0,
        )
        first = await anext(response.body_iterator)
        assert "schedule-version" in first
        if change == "revoked":
            memberships.membership = memberships.membership.model_copy(update={"state": "revoked"})
        elif change == "outage":
            memberships.error = RuntimeError("synthetic repository offline")
        else:
            memberships.membership = memberships.membership.model_copy(
                update={
                    "student_id": "other-student",
                    "revision": 2,
                }
            )
        assert [frame async for frame in response.body_iterator] == []

    asyncio.run(consume())
    assert publication.calls == 2  # preflight + first frame; no post-revocation data read
