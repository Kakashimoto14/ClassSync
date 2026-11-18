"""Server-side Cloudflare Turnstile verification for auth-sensitive routes."""

import httpx
from fastapi import HTTPException


async def verify_turnstile_token(token: str, settings) -> None:
    if not token or len(token) > 2048:
        raise HTTPException(422, "Human verification is required")
    if settings.turnstile_secret_key is None:
        if settings.classsync_env in {"test", "development"}:
            return
        raise HTTPException(503, "Human verification is unavailable")
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            result = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": settings.turnstile_secret_key.get_secret_value(),
                      "response": token},
            )
            result.raise_for_status()
            verified = result.json().get("success") is True
    except (httpx.HTTPError, ValueError, AttributeError) as error:
        raise HTTPException(503, "Human verification is unavailable") from error
    if not verified:
        raise HTTPException(403, "Human verification failed")
