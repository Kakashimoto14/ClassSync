from io import BytesIO
from unittest.mock import Mock

import pytest
from classync_contracts.scheduling import GenerationInput, scheduling_input_hash
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from services.gateway.app import main
from services.gateway.app.registration import RegistrationStore, match_review
from services.gateway.app.registration_parser import parse_pages
from services.gateway.app.registration_processing import process_document
from services.gateway.app.registration_schema import RegistrationReview
from services.gateway.app.registration_worker import pdf_text
from services.scheduling.app.catalog import synthetic_scenario

from .registration_fixtures import pdf_bytes

HEADERS = {"Authorization": "Bearer e30.e30.synthetic-signature"}


def reviewed(**changes):
    return RegistrationReview.model_validate(
        {
            "academic_year": "2026-2027",
            "semester": "first",
            "student_identifier": "SYN-001",
            "program": "SYNTHETIC",
            "year_level": 2,
            "courses": [{"code": "TEST101", "description": "Invented seminar", "section": "2"}],
            **changes,
        }
    )


def published(code="TEST101", section="SYNTHETIC 2A", period="synthetic-period"):
    return [{"id": period, "calendar": {"academic_year": "2026-2027", "semester": "first"}}], {
        period: {
            "occurrences": [
                {
                    "offering_id": "synthetic-offering",
                    "subject": {
                        "id": "opaque-subject-key",
                        "code": code,
                        "name": "Invented seminar",
                        "code_source": "academic-record",
                    },
                    "section": {"id": "synthetic-section", "name": section},
                }
            ]
        }
    }


def test_digital_pdf_returns_only_academic_fields_and_raw_section():
    result = parse_pages(pdf_text(pdf_bytes(), 5), "digital-pdf")
    assert set(result["fields"]) == {
        "academic_year",
        "semester",
        "student_identifier",
        "program",
        "year_level",
    }
    assert result["fields"]["academic_year"]["value"] == "2026-2027"
    assert result["fields"]["student_identifier"]["value"] == "SYN-001"
    assert len(result["courses"]) == 2
    assert result["courses"][0]["section"]["value"] == "2"
    assert result["courses"][0]["code"]["confidence"] is None
    assert "DO NOT EXTRACT" not in str(result)
    assert all(
        result["courses"][0][field]["review_required"]
        for field in ("code", "section", "description")
    )


@pytest.mark.parametrize(
    "data", [b"%PDF-malformed\n%%EOF", pdf_bytes(active=True), pdf_bytes(pages=6)]
)
def test_rejects_malformed_active_and_overpage_pdfs(data):
    with pytest.raises((ValueError, PdfReadError)):
        pdf_text(data, 5)


def test_rejects_encrypted_pdf():
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(BytesIO(pdf_bytes())))
    writer.encrypt("invented-fixture-password")
    buffer = BytesIO()
    writer.write(buffer)
    with pytest.raises(ValueError, match="encrypted_or_page_limit"):
        pdf_text(buffer.getvalue(), 5)


def test_actual_bounded_private_worker_and_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "services.gateway.app.registration_processing.tempfile.tempdir", str(tmp_path)
    )
    result = process_document(pdf_bytes(), ".pdf", max_pages=5, timeout=20)
    assert len(result["courses"]) == 2
    assert not list(tmp_path.iterdir())


def test_current_subject_code_extension_preserves_legacy_hash():
    inputs = synthetic_scenario()
    legacy = inputs.model_dump(mode="json")
    original = scheduling_input_hash(inputs)
    assert all("subject_code" not in row for row in legacy["offerings"])
    restored = GenerationInput.model_validate(legacy)
    assert scheduling_input_hash(restored) == original
    restored.offerings[0].subject_code = "TEST101"
    assert restored.model_dump()["offerings"][0]["subject_code"] == "TEST101"
    assert scheduling_input_hash(restored) != original


def test_match_requires_published_course_code_and_uses_authorized_enrollment_not_numeric_guess():
    periods, calendars = published()
    result = match_review(reviewed(), periods=periods, calendars=calendars)
    assert result["status"] == "matched"
    row = result["courses"][0]
    assert row["document_section"] == "2"
    assert row["offering"]["section"]["name"] == "SYNTHETIC 2A"
    assert row["section_source"] == "verified-enrollment"
    assert row["document_section_verified"] is False
    assert "starts_at" not in row and "room" not in row
    calendars["synthetic-period"]["occurrences"][0]["subject"]["code_source"] = "legacy-identifier"
    assert (
        match_review(reviewed(), periods=periods, calendars=calendars)["status"] == "pending-match"
    )


def test_wrong_term_unmatched_named_section_and_ambiguous_offering_stay_pending():
    periods, calendars = published()
    assert (
        match_review(reviewed(semester="second"), periods=periods, calendars=calendars)["status"]
        == "wrong-term"
    )
    assert match_review(reviewed(), periods=[], calendars={})["status"] == "unassigned"
    wrong_section = reviewed(courses=[{"code": "TEST101", "section": "SYNTHETIC 2B"}])
    assert (
        match_review(wrong_section, periods=periods, calendars=calendars)["status"]
        == "pending-match"
    )
    event = calendars["synthetic-period"]["occurrences"][0]
    calendars["synthetic-period"]["occurrences"].append({**event, "offering_id": "other-offering"})
    assert (
        match_review(reviewed(), periods=periods, calendars=calendars)["courses"][0]["status"]
        == "ambiguous"
    )


def test_scan_cache_scopes_tenant_user_expiration_and_explicit_erasure():
    now = [0]
    store = RegistrationStore(clock=lambda: now[0], capacity=2)
    item = store.save("a", "first", {"fields": {}}, 60)
    for tenant, uid in [("b", "first"), ("a", "other")]:
        with pytest.raises(HTTPException) as error:
            store.read(item["id"], tenant, uid)
        assert error.value.status_code == 404
    now[0] = 61
    with pytest.raises(HTTPException):
        store.read(item["id"], "a", "first")
    assert not store.entries
    item = store.save("a", "first", {"fields": {}}, 60)
    store.read(item["id"], "a", "first", delete=True)
    assert not store.entries


@pytest.fixture
def api(identity_adapters, monkeypatch):
    verifier, _ = identity_adapters(main, uid="scanner-route-fixture")
    repository = Mock()
    repository.status.return_value = {"membership_state": None}
    monkeypatch.setattr(main.app.state, "onboarding_repository", repository, raising=False)
    main.registration_routes.registration_store.entries.clear()
    main.registration_routes.registration_store.buckets.clear()
    return TestClient(main.app), verifier, repository


def test_upload_route_auth_mime_size_and_no_store(api, monkeypatch):
    client, _, _ = api
    assert (
        client.post("/api/v1/auth/registration-documents", content=pdf_bytes()).status_code == 401
    )
    assert (
        client.post(
            "/api/v1/auth/registration-documents",
            headers={**HEADERS, "Content-Type": "text/html"},
            content=b"<script>",
        ).status_code
        == 415
    )
    monkeypatch.setattr(main.settings, "registration_max_bytes", 1024)
    result = client.post(
        "/api/v1/auth/registration-documents",
        headers={**HEADERS, "Content-Type": "application/pdf"},
        content=b"x" * 1025,
    )
    assert result.status_code == 413
    assert result.headers["Cache-Control"] == "no-store"


def test_unverified_and_revoked_users_cannot_upload(api, monkeypatch):
    from classync_contracts.identity import VerifiedPrincipal

    client, verifier, repository = api
    monkeypatch.setattr(verifier, "verify", lambda _: VerifiedPrincipal(uid="unverified"))
    assert (
        client.post("/api/v1/auth/registration-documents/manual", headers=HEADERS).status_code
        == 403
    )
    monkeypatch.setattr(
        verifier, "verify", lambda _: VerifiedPrincipal(uid="revoked", email_verified=True)
    )
    repository.status.return_value = {"membership_state": "revoked"}
    assert (
        client.post("/api/v1/auth/registration-documents/manual", headers=HEADERS).status_code
        == 403
    )


def test_private_manual_review_and_foreign_document_reads_are_denied(api, monkeypatch):
    from classync_contracts.identity import VerifiedPrincipal

    client, verifier, _ = api
    result = client.post("/api/v1/auth/registration-documents/manual", headers=HEADERS)
    assert result.status_code == 201
    scan = result.json()["data"]
    monkeypatch.setattr(
        verifier, "verify", lambda _: VerifiedPrincipal(uid="another-user", email_verified=True)
    )
    assert (
        client.get("/api/v1/auth/registration-documents/" + scan["id"], headers=HEADERS).status_code
        == 404
    )
    assert (
        client.delete(
            "/api/v1/auth/registration-documents/" + scan["id"], headers=HEADERS
        ).status_code
        == 404
    )


def test_program_does_not_capture_adjacent_private_or_financial_labels():
    result = parse_pages(
        ["Program: SYNTHETIC Tuition: PRIVATE-FEE Name: PRIVATE-PERSON"], "local-ocr"
    )
    assert result["fields"]["program"]["value"] == "SYNTHETIC"
    assert "PRIVATE" not in str(result)


def test_blank_document_section_is_not_marked_verified():
    periods, calendars = published()
    result = match_review(
        reviewed(courses=[{"code": "TEST101", "section": ""}]), periods=periods, calendars=calendars
    )
    assert result["courses"][0]["document_section_verified"] is False


def test_review_json_is_bounded_before_parsing(api):
    client, _, _ = api
    scan = client.post("/api/v1/auth/registration-documents/manual", headers=HEADERS).json()["data"]
    path = "/api/v1/auth/registration-documents/" + scan["id"] + "/review"
    assert (
        client.post(
            path, headers={"Content-Type": "application/json"}, content=b"x" * 65000
        ).status_code
        == 401
    )
    assert (
        client.post(
            path, headers={**HEADERS, "Content-Type": "application/json"}, content=b"x" * 65000
        ).status_code
        == 413
    )


def test_review_repository_restores_review_without_extraction_and_fails_closed(api, monkeypatch):
    client, _, _ = api
    reviews = Mock()
    reviews.read.return_value = None
    monkeypatch.setattr(main.app.state, "registration_review_repository", reviews, raising=False)
    start = client.post("/api/v1/auth/registration-documents/manual", headers=HEADERS)
    assert start.status_code == 201
    scan = start.json()["data"]
    path = f"/api/v1/auth/registration-documents/{scan['id']}"
    payload = reviewed().model_dump(mode="json")
    assert client.post(f"{path}/review", headers=HEADERS, json=payload).status_code == 200
    key, tenant, uid, deadline, submitted = reviews.save.call_args.args
    assert (str(key), tenant, uid, deadline.isoformat(), submitted.model_dump()) == (
        scan["id"], main.settings.institutional_tenant_id, "scanner-route-fixture",
        scan["expires_at"], payload,
    )

    unavailable = HTTPException(503, "Reviewed scans are temporarily unavailable.")
    reviews.read.side_effect = unavailable
    assert client.get(path, headers=HEADERS).status_code == 503
    assert client.delete(path, headers=HEADERS).status_code == 503
    reviews.erase.assert_not_called()

    main.registration_routes.registration_store.entries.clear()
    reviews.read.side_effect = None
    reviews.read.return_value = {**scan, "method": "reviewed", "reviewed": {
        **payload, "student_identifier": "",
    }}
    restored = client.get(path, headers=HEADERS)
    assert restored.status_code == 200
    assert restored.json()["data"]["reviewed"]["student_identifier"] == ""
    assert client.delete(path, headers=HEADERS).status_code == 204
    reviews.erase.assert_called_once_with(key, tenant, uid, deadline)


@pytest.mark.parametrize("change", [None, {"revision": 2}, {"student_id": "OTHER-STUDENT"}])
def test_match_response_requires_the_original_student_binding(
    api, identity_adapters, monkeypatch, change,
):
    client, _, onboarding = api
    _, memberships = identity_adapters(main, role="student", student_id="SYN-001")
    onboarding.status.return_value = {"membership_state": "active"}
    start = client.post("/api/v1/auth/registration-documents/manual", headers=HEADERS)
    assert start.status_code == 201
    scan_id = start.json()["data"]["id"]
    periods, calendars = published()
    periods[0]["calendar"].update(effective_start="2026-10-01", effective_end="2026-10-05")

    def upstream(path, **kwargs):
        if path == "/api/v1/timetables/periods":
            return Mock(**{"json.return_value": {"periods": periods}})
        assert path == "/api/v1/timetables/calendar/synthetic-period"
        if change is not None:
            memberships.membership = memberships.membership.model_copy(update=change)
        return Mock(**{"json.return_value": {
            "status": "published", "version": 1, **calendars["synthetic-period"],
        }})

    transport = Mock()
    transport.__enter__ = Mock(return_value=transport)
    transport.__exit__ = Mock(return_value=False)
    transport.get.side_effect = upstream
    monkeypatch.setattr("services.gateway.app.registration.httpx.Client", lambda **_: transport)
    response = client.post(
        f"/api/v1/auth/registration-documents/{scan_id}/review", headers=HEADERS,
        json=reviewed().model_dump(mode="json"),
    )
    if change is None:
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "matched"
    else:
        assert response.status_code == 403
        assert "synthetic-offering" not in response.text


def test_mixed_pdf_with_selectable_header_still_attempts_local_ocr(tmp_path, monkeypatch):
    from services.gateway.app import registration_worker as worker

    from .registration_fixtures import TEXT

    file = tmp_path / "synthetic-mixed.pdf"
    file.write_bytes(pdf_bytes())
    monkeypatch.setattr(worker, "pdf_text", lambda *_: ["Invented selectable header " * 20])
    ocr = Mock(return_value=[TEXT])
    monkeypatch.setattr(worker, "local_ocr", ocr)
    assert worker.extract(file, 5)["method"] == "local-ocr"
    ocr.assert_called_once()


def test_schedule_link_opens_first_actual_published_class_not_empty_partial_week():
    periods, calendars = published()
    periods[0]["calendar"]["effective_start"] = "2026-10-01"
    event = calendars["synthetic-period"]["occurrences"][0]
    event["date"] = "2026-10-12"
    calendars["synthetic-period"]["occurrences"].append({**event, "date": "2026-10-05"})
    result = match_review(reviewed(), periods=periods, calendars=calendars)
    assert result["periods"][0]["start"] == "2026-10-05"
