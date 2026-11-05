"""Image-local Linux qualification. Synthetic files only; no original DB/cloud access."""

import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from fastapi import HTTPException


def probe(service):
    if os.name != "posix" or service not in {"gateway", "academic", "scheduling"}:
        raise ValueError("An actual Linux service image is required")
    importlib.import_module(f"services.{service}.app.main")
    result = {"service": service, "platform": "linux", "import": True}
    if service == "scheduling":
        from services.scheduling.app.engine import generate_week
        from services.scheduling.app.validation import validate_timetable
        from services.scheduling.tests.test_engine import tiny

        inputs = tiny()
        generated = generate_week(inputs)
        assert generated.solver_status in {"optimal", "feasible"}
        assert validate_timetable(inputs, generated.assignments).valid
        result["solver_and_independent_validation"] = True
    if service == "gateway":
        from scripts.registration_local_qualification import fixture_images, scanned_pdf
        from services.gateway.app.registration_ocr import image_dimensions
        from services.gateway.app.registration_processing import process_document
        from services.gateway.tests.registration_fixtures import pdf_bytes

        with tempfile.TemporaryDirectory(prefix="classsync-linux-control-") as folder:
            root = Path(folder)
            fixture_images(root)
            jpeg = root / "synthetic-registration.jpg"
            cases = [
                ("digital", pdf_bytes(), ".pdf"),
                ("png", (root / "synthetic-registration.png").read_bytes(), ".png"),
                ("jpeg", jpeg.read_bytes(), ".jpg"),
                ("scanned-pdf", scanned_pdf(jpeg.read_bytes(), *image_dimensions(jpeg)), ".pdf"),
            ]
            observed = []
            before = set(Path(tempfile.gettempdir()).glob("classsync-private-registration-*"))
            for name, data, suffix in cases:
                value = process_document(data, suffix, max_pages=5, timeout=20)
                assert value["courses"] and len(value["courses"]) <= 60
                assert value["method"] == ("digital-pdf" if name == "digital" else "local-ocr")
                observed.append(
                    {
                        "kind": name,
                        "method": value["method"],
                        "courses": len(value["courses"]),
                        "manual_review_required": True,
                    }
                )
            for data, suffix in [
                (b"unsupported", ".txt"),
                (b"\x89PNG\r\n\x1a\ninvalid", ".png"),
                (pdf_bytes(pages=6), ".pdf"),
                (pdf_bytes(active=True), ".pdf"),
            ]:
                try:
                    process_document(data, suffix, max_pages=5, timeout=20)
                except HTTPException as error:
                    assert error.status_code == 422
                else:
                    raise AssertionError("Unsafe document accepted")
            assert (
                set(Path(tempfile.gettempdir()).glob("classsync-private-registration-*")) == before
            )
            result.update({"scanner": observed, "unsafe_files_denied": 4, "private_cleanup": True})
    return result


def service_health(mode):
    import httpx

    expected = {
        "/health": 200,
        "/api/v1/auth/me": 401,
        "/api/v1/services/academic/health": 503 if mode == "outage" else 200,
        "/api/v1/services/scheduling/health": 200,
    }
    deadline = time.monotonic() + 15
    with httpx.Client(base_url="http://127.0.0.1:8080", trust_env=False, timeout=3) as client:
        while True:
            try:
                observed = {path: client.get(path).status_code for path in expected}
                if observed == expected:
                    return {"service_communication": mode, "statuses": observed}
            except httpx.HTTPError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("Container health/auth/communication qualification failed")
            time.sleep(0.1)


if __name__ == "__main__":
    if sys.argv[1:] == ["--health"]:
        result = service_health("ready")
    elif sys.argv[1:] == ["--academic-outage"]:
        result = service_health("outage")
    elif not sys.argv[1:]:
        result = probe(os.environ.get("CLASSSYNC_SERVICE", "gateway"))
    else:
        raise ValueError("Unknown qualification operation")
    print(json.dumps(result))
