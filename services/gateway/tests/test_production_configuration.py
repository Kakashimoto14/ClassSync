import asyncio

import pytest

from services.gateway.app import main
from services.gateway.app.main import Settings, validate_production_frontend_origin


def test_production_frontend_origin_rejects_loopback_and_http():
    for origin in ("http://localhost:5173", "https://127.0.0.1:8443"):
        settings = Settings(classsync_env="production", classsync_web_url=origin)
        with pytest.raises(ValueError, match="HTTPS frontend origin"):
            validate_production_frontend_origin(settings)


def test_production_frontend_origin_accepts_https_origin():
    settings = Settings(
        classsync_env="production", classsync_web_url="https://classsync.example.edu"
    )

    validate_production_frontend_origin(settings)


def test_nonproduction_frontend_origin_keeps_local_development_supported():
    settings = Settings(classsync_env="development", classsync_web_url="http://localhost:5173")

    validate_production_frontend_origin(settings)


def test_gateway_startup_rejects_unconfigured_production_fallback(monkeypatch):
    monkeypatch.setattr(main.settings, "classsync_env", "production")
    monkeypatch.setattr(main.settings, "classsync_web_url", "http://localhost:5173")

    async def start():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(ValueError, match="HTTPS frontend origin"):
        asyncio.run(start())
