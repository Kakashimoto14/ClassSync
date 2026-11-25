import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from pydantic import SecretStr

from services.scheduling.app import advisor


class Settings:
    gemini_api_key = SecretStr("test-secret")
    gemini_model = "gemini-3.5-flash-lite"


def test_advisor_returns_clean_fallback_without_key():
    settings = Settings()
    settings.gemini_api_key = None
    result = asyncio.run(advisor._advise(settings, {"count": 1}, shape="health"))
    assert not result.available
    assert "Deterministic" in result.message


def test_advisor_validates_json_and_uses_ten_second_timeout(monkeypatch):
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["request"] = kwargs

            class Response:
                def raise_for_status(self):
                    return None

                async def aiter_bytes(self):
                    body = {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(
                                                {
                                                    "suggestions": [
                                                        {
                                                            "option_id": "opt-1",
                                                            "reason": "This room is free.",
                                                        }
                                                    ]
                                                }
                                            )
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                    yield json.dumps(body).encode()

            @asynccontextmanager
            async def response_stream():
                yield Response()

            return response_stream()

    monkeypatch.setattr(advisor.httpx, "AsyncClient", Client)
    prompt = {"alternatives": [{"option_id": "opt-1", "day": 1, "start": 480}]}
    candidate = advisor.Assignment(
        id="assignment-1",
        offering_id="offering-1",
        day=1,
        start=480,
        end=600,
        room_id="room-1",
        teacher_id="teacher-1",
        section_id="section-1",
        subject_id="subject-1",
    )
    result = asyncio.run(
        advisor._advise(
            Settings(), prompt, shape="conflict", option_assignments={"opt-1": candidate}
        )
    )
    assert result.available and result.suggestions[0].assignment.room_id == "room-1"
    assert result.suggestions[0].reason == "This room is free."
    assert captured["timeout"] == 10.0 and captured["trust_env"] is False
    assert captured["method"] == "POST"
    assert "/v1beta/models/gemini-3.5-flash-lite:generateContent" in captured["url"]
    assert captured["request"]["params"] == {"key": "test-secret"}


@pytest.mark.parametrize("failure", [httpx.TimeoutException("timeout"), ValueError("bad json")])
def test_advisor_provider_failures_are_clean(monkeypatch, failure):
    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            raise failure

    monkeypatch.setattr(advisor.httpx, "AsyncClient", Client)
    result = asyncio.run(advisor._advise(Settings(), {"count": 1}, shape="health"))
    assert not result.available
    assert "timeout" not in result.message.lower()
    assert "test-secret" not in result.message
