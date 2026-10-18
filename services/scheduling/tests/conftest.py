import pytest

from services.scheduling.app import main


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        main.settings, "scheduling_database_path", str(tmp_path / "scheduling.sqlite3")
    )
