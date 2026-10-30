import json

import pytest

from scripts.postgres_web_session_qualification import write_new_evidence


def test_web_session_evidence_never_overwrites_late_created_output(tmp_path):
    output = tmp_path / "evidence.json"
    assert not output.exists()  # Initial qualification preflight.
    output.write_text("sentinel created while the qualification ran", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_new_evidence(output, {"passed": True})
    assert output.read_text(encoding="utf-8") == "sentinel created while the qualification ran"
    fresh = tmp_path / "fresh.json"
    write_new_evidence(fresh, {"passed": True})
    assert json.loads(fresh.read_text(encoding="utf-8")) == {"passed": True}
