"""Optional, bounded Gemini explanations for administrator schedule review."""

import json
import logging
import re
from typing import Literal

import httpx
from classync_contracts.scheduling import Assignment
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class Advice(BaseModel):
    available: bool
    message: str
    suggestions: list[str] = Field(default_factory=list, max_length=3)


class ConflictPrompt(BaseModel):
    assignment_id: str = Field(min_length=1, max_length=100)


class ConflictSuggestion(BaseModel):
    assignment: Assignment
    reason: str = Field(min_length=1, max_length=240)


class ConflictAdvice(BaseModel):
    available: bool
    message: str
    suggestions: list[ConflictSuggestion] = Field(default_factory=list, max_length=3)


class HealthPrompt(BaseModel):
    room_utilization_percent: int = Field(ge=0, le=100)
    faculty_load_min_hours: int = Field(ge=0)
    faculty_load_max_hours: int = Field(ge=0)
    faculty_load_average_hours: int = Field(ge=0)
    idle_gap_count: int = Field(ge=0)
    publish_ready: bool
    blocking_conflicts: int = Field(ge=0)


async def _advise(
    settings,
    prompt: dict,
    *,
    shape: Literal["conflict", "health"],
    option_assignments: dict[str, Assignment] | None = None,
) -> Advice | ConflictAdvice:
    response_model = ConflictAdvice if shape == "conflict" else Advice

    def unavailable(message):
        return response_model(available=False, message=message)

    key = settings.gemini_api_key
    if key is None or not key.get_secret_value().strip():
        return unavailable(
            "AI advice is not configured. Deterministic schedule checks remain available."
        )
    model = settings.gemini_model
    if not MODEL_PATTERN.fullmatch(model):
        logger.warning("scheduling_advisor_invalid_model")
        return unavailable(
            "AI advice is temporarily unavailable. Deterministic schedule checks remain available."
        )
    schema = (
        '{"suggestions":[{"option_id":"candidate id","reason":"brief reason"}]}'
        if shape == "conflict"
        else '{"suggestions":["short health observation"]}'
    )
    system = (
        "You advise a university scheduling administrator. The administrator makes every decision. "
        "Use only supplied facts, do not invent availability, and return JSON matching " + schema
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": json.dumps(prompt, separators=(",", ":"))}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 300,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            async with client.stream(
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": key.get_secret_value()},
                json=payload,
            ) as response:
                response.raise_for_status()
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(chunks) + len(chunk) > 16 * 1024:
                        raise ValueError("provider response exceeds size limit")
                    chunks.extend(chunk)
        text = json.loads(chunks)["candidates"][0]["content"]["parts"][0]["text"]
        value = json.loads(text)
        suggestions = value.get("suggestions")
        if not isinstance(suggestions, list) or not 1 <= len(suggestions) <= 3:
            raise ValueError("invalid response shape")
        if shape == "conflict":
            options = option_assignments or {}
            selected = []
            for item in suggestions:
                option = options.get(str(item.get("option_id")))
                reason = item.get("reason")
                if option is None or not isinstance(reason, str) or not reason.strip():
                    raise ValueError("unknown conflict option")
                selected.append(ConflictSuggestion(assignment=option, reason=reason[:240]))
            return ConflictAdvice(
                available=True,
                message="Suggestions are advisory. Apply creates a separately validated draft.",
                suggestions=selected,
            )
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 300 for item in suggestions
        ):
            raise ValueError("invalid suggestion")
        return Advice(
            available=True,
            message="AI suggestions are advisory; verify each change before saving.",
            suggestions=[item.strip() for item in suggestions],
        )
    except (
        httpx.HTTPError,
        AttributeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        ValidationError,
    ) as error:
        logger.info("scheduling_advisor_unavailable", extra={"reason_type": type(error).__name__})
        return unavailable(
            "AI advice is temporarily unavailable. Deterministic schedule checks remain available."
        )
