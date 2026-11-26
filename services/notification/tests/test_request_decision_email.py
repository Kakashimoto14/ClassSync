from fastapi.testclient import TestClient
from pydantic import SecretStr

from services.notification.app import main
from services.notification.app.email_templates import render_request_decision_email

BODY = {
    "email": "Teacher.Demo@Example.edu",
    "decision": "approved",
    "subject_code": "IT 311",
    "section": "BSIT 3A",
    "class_date": "2026-11-09",
    "time_range": "08:00–09:30",
    "from_room": "Room 201",
    "to_room": "Lab 3",
    "note": "Projector replaced <b>today</b>",
}


def test_request_decision_email_requires_the_internal_service_token(monkeypatch):
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))
    client = TestClient(main.app)
    assert client.post("/internal/v1/request-decision-email", json=BODY).status_code == 403
    assert (
        client.post(
            "/internal/v1/request-decision-email",
            json=BODY,
            headers={"X-ClassSync-Service-Token": "wrong"},
        ).status_code
        == 403
    )


def test_request_decision_email_rejects_extra_fields_and_unknown_decisions(monkeypatch):
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))
    client = TestClient(main.app)
    headers = {"X-ClassSync-Service-Token": "internal"}
    for body in ({**BODY, "student_ids": ["x"]}, {**BODY, "decision": "fulfilled"}):
        assert (
            client.post("/internal/v1/request-decision-email", json=body, headers=headers)
            .status_code
            == 422
        )


def test_request_decision_email_delivers_escaped_content(monkeypatch):
    monkeypatch.setattr(main.settings, "notification_service_token", SecretStr("internal"))
    sent = {}

    async def deliver(email, subject, text, html):
        sent.update(email=email, subject=subject, text=text, html=html)

    monkeypatch.setattr(main, "deliver_email", deliver)
    response = TestClient(main.app).post(
        "/internal/v1/request-decision-email",
        json=BODY,
        headers={"X-ClassSync-Service-Token": "internal"},
    )
    assert response.status_code == 202
    assert sent["email"] == "teacher.demo@example.edu"
    assert sent["subject"] == "ClassSync · Classroom change approved"
    assert "<b>today</b>" not in sent["html"] and "&lt;b&gt;today&lt;/b&gt;" in sent["html"]
    assert "Lab 3" in sent["text"] and "/teacher/change-requests" in sent["text"]


def test_declined_template_states_the_timetable_is_unchanged():
    html, text = render_request_decision_email(
        decision="rejected",
        subject_code="IT 311",
        section="BSIT 3A",
        class_date="2026-11-09",
        time_range="08:00–09:30",
        from_room="Room 201",
        to_room="Lab 3",
        note="Lab is reserved",
        app_url="https://class-sync-bhiv.vercel.app",
    )
    assert "Classroom change declined" in html
    assert "stays in Room 201" in text and "not changed" in text
