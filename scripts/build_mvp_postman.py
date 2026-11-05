"""Generate credential-free Postman artifacts; never execute institutional/cloud requests."""

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "api"


def request(name, method, path, status, body=None, capture=None, protected=True):
    tests = [f"pm.test('HTTP {status}', () => pm.response.to.have.status({status}));"]
    if capture:
        tests.append("if (pm.response.code < 300) { const d = pm.response.json().data;")
        tests.extend(
            f"pm.environment.set('{variable}', d.{field});" for variable, field in capture.items()
        )
        tests.append("}")
    value = {
        "method": method,
        "url": "{{base_url}}" + path,
        "header": [{"key": "X-ClassSync-Role", "value": "{{workspace_role}}"}],
    }
    if body is not None:
        value["header"].append({"key": "Content-Type", "value": "application/json"})
        value["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    if not protected:
        value["auth"] = {"type": "noauth"}
    return {
        "name": name,
        "request": value,
        "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}],
    }


def build():
    preferences = {"calendar_view": "week", "compact": False}
    patch = {
        "expected_revision": "{{preference_revision}}",
        "expected_generation": "{{preference_generation}}",
        "compact": True,
    }
    create = request(
        "Create private preferences",
        "POST",
        "/api/v1/coursework/preferences",
        201,
        preferences,
        {"preference_revision": "revision", "preference_generation": "generation"},
    )
    update = request(
        "Update the current generation",
        "PATCH",
        "/api/v1/coursework/preferences",
        200,
        patch,
        {"preference_revision": "revision"},
    )
    update["request"]["body"]["raw"] = update["request"]["body"]["raw"].replace(
        '"{{preference_revision}}"', "{{preference_revision}}"
    )
    core = [
        request(
            "Reject missing token", "GET", "/api/v1/coursework/preferences", 401, protected=False
        ),
        request("Current verified membership", "GET", "/api/v1/auth/me", 200),
        request("Onboarding status", "GET", "/api/v1/auth/onboarding", 200),
        request("Permitted published periods", "GET", "/api/v1/timetables/periods", 200),
        request(
            "Permitted current timetable",
            "GET",
            "/api/v1/timetables/calendar/{{academic_period_id}}?start={{week_start}}&end={{week_end}}",
            200,
        ),
        request(
            "Permitted room metadata", "GET", "/api/v1/timetables/rooms/{{academic_period_id}}", 200
        ),
        request("Audience-scoped notices", "GET", "/api/v1/community/announcements", 200),
    ]
    cloud = [
        create,
        request(
            "Duplicate preferences are rejected",
            "POST",
            "/api/v1/coursework/preferences",
            409,
            preferences,
        ),
        request("Read own preferences", "GET", "/api/v1/coursework/preferences", 200),
        update,
        request(
            "Delete current preference generation",
            "DELETE",
            "/api/v1/coursework/preferences?expected_revision={{preference_revision}}&expected_generation={{preference_generation}}",
            200,
        ),
        request("Deleted preferences are absent", "GET", "/api/v1/coursework/preferences", 404),
        request(
            "Upload synthetic private text",
            "POST",
            "/api/v1/coursework/files",
            201,
            {
                "purpose": "synthetic-course-demo",
                "text": "Synthetic coursework text. No personal academic data.",
            },
            {"file_id": "id"},
        ),
        request(
            "Download own private attachment", "GET", "/api/v1/coursework/files/{{file_id}}", 200
        ),
        request(
            "Delete own private attachment", "DELETE", "/api/v1/coursework/files/{{file_id}}", 200
        ),
        request("Deleted attachment is absent", "GET", "/api/v1/coursework/files/{{file_id}}", 404),
        request(
            "Fixed-topic advisory only",
            "POST",
            "/api/v1/coursework/advisory",
            200,
            {"topic": "study-planning"},
        ),
    ]
    cloud_guard = [
        "if (pm.environment.get('approved_cloud_qualification') !== 'true') {",
        "pm.execution.skipRequest();",
        "throw new Error('Approved cloud configuration and credentials are required.');",
        "}",
    ]
    pending = [
        request("Pending account status", "GET", "/api/v1/auth/onboarding", 200),
        request("Pending identity has no institutional role", "GET", "/api/v1/auth/me", 403),
        request(
            "Unverified claim is denied",
            "POST",
            "/api/v1/auth/student-claims",
            403,
            {"student_id": "synthetic-postman-student"},
        ),
        request(
            "Public faculty escalation is denied",
            "POST",
            "/api/v1/auth/faculty-invitations",
            403,
            {"faculty_id": "synthetic-faculty", "email": "synthetic@example.test"},
        ),
        request(
            "Unverified scanner access is denied",
            "POST",
            "/api/v1/auth/registration-documents/manual",
            403,
        ),
    ]
    emulator_signup = request(
        "Create disposable pending account",
        "POST",
        "",
        200,
        {
            "email": "{{synthetic_email}}",
            "password": "{{synthetic_password}}",
            "returnSecureToken": True,
        },
        protected=False,
    )
    emulator_signup["request"]["url"] = (
        "{{auth_emulator_url}}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=local-emulator-only"
    )
    emulator_signup["event"][0]["script"]["exec"].append(
        "if (pm.response.code === 200) {"
        "pm.variables.set('pending_token', pm.response.json().idToken); }"
    )
    duplicate_signup = deepcopy(emulator_signup)
    duplicate_signup["name"] = "Duplicate emulator email rejected"
    duplicate_signup["event"][0]["script"]["exec"] = [
        "pm.test('HTTP 400 duplicate', () => pm.response.to.have.status(400));"
    ]
    local_guard = [
        "if (pm.environment.get('approved_disposable_qualification') !== 'true') {",
        "pm.execution.skipRequest();",
        "throw new Error('Disposable qualification approval required'); }",
        "for (const name of ['base_url', 'auth_emulator_url']) {",
        "if (!/^http:\\/\\/127\\.0\\.0\\.1:\\d+$/.test(pm.variables.get(name))) {",
        "pm.execution.skipRequest();",
        "throw new Error('Owned loopback services required'); }",
        "}",
        "const destination = pm.variables.replaceIn(pm.request.url.toString());",
        "if (!/^http:\\/\\/127\\.0\\.0\\.1:\\d+\\//.test(destination)) {",
        "pm.execution.skipRequest(); throw new Error('Owned loopback destination required'); }",
        "const ownedOrigins = ['base_url', 'auth_emulator_url'].map(n => pm.environment.get(n));",
        "if (!ownedOrigins.some(origin => destination.startsWith(origin + '/'))) {",
        "pm.execution.skipRequest(); throw new Error('Exact owned destination required'); }",
        "if (!pm.variables.get('synthetic_email')) {",
        "const id = pm.variables.replaceIn('{{$guid}}');",
        "pm.variables.set('synthetic_email', 'postman-' + id + '@example.test');",
        "pm.variables.set('synthetic_password', 'Local-only-' + id + '!'); }",
    ]
    operations = [
        request("Academic inputs", "GET", "/api/v1/academic/periods/{{academic_period_id}}", 200),
        request(
            "Readiness blockers",
            "GET",
            "/api/v1/scheduling/academic/{{academic_period_id}}/readiness",
            200,
        ),
        request(
            "Generate validated timetable",
            "POST",
            "/api/v1/scheduling/academic/{{academic_period_id}}/generate",
            200,
            {"expected_revision": "{{academic_revision}}"},
        ),
        request(
            "Publication history", "GET", "/api/v1/timetables/history/{{academic_period_id}}", 200
        ),
        request(
            "Approve verified student claim",
            "PATCH",
            "/api/v1/auth/student-claims/{{student_uid}}",
            200,
            {"approve": True, "verification_reference": "{{approved_verification_reference}}"},
        ),
        request(
            "Issue scoped faculty invitation",
            "POST",
            "/api/v1/auth/faculty-invitations",
            201,
            {"faculty_id": "{{faculty_id}}", "email": "{{teacher_email}}", "expires_in_hours": 1},
            {"invitation_id": "id", "invitation_token": "token"},
        ),
        request(
            "Revoke unused invitation",
            "DELETE",
            "/api/v1/auth/faculty-invitations/{{invitation_id}}",
            200,
        ),
    ]
    scanner = [
        request(
            "Create manual review",
            "POST",
            "/api/v1/auth/registration-documents/manual",
            201,
            capture={"scan_id": "id"},
        ),
        request(
            "Read own extraction", "GET", "/api/v1/auth/registration-documents/{{scan_id}}", 200
        ),
        request(
            "Review and match published enrollment",
            "POST",
            "/api/v1/auth/registration-documents/{{scan_id}}/review",
            200,
            {
                "academic_year": "{{academic_year}}",
                "semester": "first",
                "student_identifier": "{{synthetic_student_id}}",
                "program": "Synthetic",
                "courses": [{"code": "{{synthetic_course_code}}", "section": "2"}],
            },
        ),
        request(
            "Delete private extraction",
            "DELETE",
            "/api/v1/auth/registration-documents/{{scan_id}}",
            204,
        ),
        request(
            "Deleted extraction denied",
            "GET",
            "/api/v1/auth/registration-documents/{{scan_id}}",
            404,
        ),
    ]
    upload = request(
        "Scan synthetic PDF",
        "POST",
        "/api/v1/auth/registration-documents",
        201,
        capture={"scan_id": "id"},
    )
    upload["request"]["header"].append({"key": "Content-Type", "value": "application/pdf"})
    upload["request"]["body"] = {"mode": "file", "file": {"src": "{{synthetic_pdf_path}}"}}
    scanner.insert(0, upload)
    operations[2]["request"]["body"]["raw"] = operations[2]["request"]["body"]["raw"].replace(
        '"{{academic_revision}}"', "{{academic_revision}}"
    )
    for action in ("review", "publish"):
        item = request("Publication " + action, "POST", "/api/v1/timetables/" + action, 200)
        item["request"]["header"].append({"key": "Content-Type", "value": "application/json"})
        item["request"]["body"] = {
            "mode": "raw",
            "raw": "{{publication_command}}",
            "options": {"raw": {"language": "json"}},
        }
        operations.append(item)
    mutation_guard = [
        "if (pm.environment.get('approved_synthetic_journey') !== 'true') {",
        "pm.execution.skipRequest();",
        "throw new Error('Approved synthetic journey required'); }",
    ]
    approved_destination = [
        "const approvedBase = pm.environment.get('base_url');",
        "const actualTarget = pm.variables.replaceIn(pm.request.url.toString());",
        "if (pm.variables.get('base_url') !== approvedBase ||",
        "!actualTarget.startsWith(approvedBase + '/')) {",
        "pm.execution.skipRequest(); throw new Error('Approved destination required'); }",
    ]
    cloud_guard.extend(approved_destination)
    mutation_guard.extend(approved_destination)

    def as_role(item, role, token):
        item["request"]["auth"] = {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{" + token + "}}", "type": "string"}],
        }
        item["request"]["header"][0]["value"] = role
        return item

    journey = [
        as_role(
            request(
                "Verified Student submits claim",
                "POST",
                "/api/v1/auth/student-claims",
                201,
                {"student_id": "{{synthetic_student_id}}"},
            ),
            "student",
            "student_token",
        ),
        as_role(
            request(
                "Duplicate claim denied",
                "POST",
                "/api/v1/auth/student-claims",
                409,
                {"student_id": "{{synthetic_student_id}}"},
            ),
            "student",
            "student_token",
        ),
        deepcopy(operations[4]),
        deepcopy(operations[5]),
        as_role(
            request(
                "Teacher accepts approved invitation",
                "POST",
                "/api/v1/auth/faculty-invitations/accept",
                200,
                {"token": "{{invitation_token}}"},
            ),
            "teacher",
            "teacher_token",
        ),
        as_role(
            request(
                "Invitation replay denied",
                "POST",
                "/api/v1/auth/faculty-invitations/accept",
                403,
                {"token": "{{invitation_token}}"},
            ),
            "teacher",
            "teacher_token",
        ),
        deepcopy(operations[0]),
        deepcopy(operations[1]),
        deepcopy(operations[2]),
        deepcopy(operations[-2]),
        deepcopy(operations[-1]),
    ]
    for role in ("student", "teacher"):
        item = as_role(
            request(
                role + " published classes",
                "GET",
                "/api/v1/timetables/calendar/{{academic_period_id}}?start={{week_start}}&end={{week_end}}",
                200,
            ),
            role,
            role + "_token",
        )
        item["event"][0]["script"]["exec"].append(
            "pm.test('Published assigned classes', () => { const d=pm.response.json().data;"
            "pm.expect(d.status).to.eql('published');pm.expect(d.occurrences.length).to.be.above(0);});"
        )
        journey.append(item)
    journey.extend(
        as_role(deepcopy(item), "student", "student_token") for item in [scanner[0], *scanner[2:]]
    )
    reviewed_item = next(
        item for item in journey if item["name"] == "Review and match published enrollment"
    )
    reviewed_item["event"][0]["script"]["exec"].append(
        "pm.test('Verified enrollment matched', () => { const d=pm.response.json().data;"
        "pm.expect(d.status).to.eql('matched'); });"
    )
    wrong_term = deepcopy(reviewed_item)
    wrong_term["name"] = "Wrong term never invents schedule"
    wrong_term["request"]["body"]["raw"] = wrong_term["request"]["body"]["raw"].replace(
        "{{academic_year}}", "2025-2026"
    )
    wrong_term["event"][0]["script"]["exec"][-1] = (
        "pm.test('Wrong term pending', () => { const d=pm.response.json().data;"
        "pm.expect(d.status).to.eql('wrong-term'); });"
    )
    journey.insert(journey.index(reviewed_item) + 1, wrong_term)
    journey.extend(
        [
            as_role(
                request(
                    "Student cannot create Teacher invitation",
                    "POST",
                    "/api/v1/auth/faculty-invitations",
                    403,
                    {"faculty_id": "{{faculty_id}}", "email": "{{teacher_email}}"},
                ),
                "student",
                "student_token",
            ),
            as_role(
                request(
                    "Teacher cannot review Student claims",
                    "GET",
                    "/api/v1/auth/student-claims",
                    403,
                ),
                "teacher",
                "teacher_token",
            ),
        ]
    )
    collection = {
        "info": {
            "name": "ClassSync MVP — verified core and optional course APIs",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": (
                "No stored credentials. Core reads require approved memberships. "
                "Cloud is UNQUALIFIED until approved staging execution. "
                "Mocks are not cloud evidence."
            ),
        },
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{id_token}}", "type": "string"}],
        },
        "item": [
            {"name": "Core authorized reads and explicit401", "item": core},
            {
                "name": "Approved cloud qualification — not run locally",
                "item": cloud,
                "event": [
                    {
                        "listen": "prerequest",
                        "script": {"type": "text/javascript", "exec": cloud_guard},
                    }
                ],
            },
            {
                "name": "Disposable emulator pending-account boundaries",
                "item": [emulator_signup, duplicate_signup, *pending],
                "auth": {
                    "type": "bearer",
                    "bearer": [{"key": "token", "value": "{{pending_token}}", "type": "string"}],
                },
                "event": [
                    {
                        "listen": "prerequest",
                        "script": {"type": "text/javascript", "exec": local_guard},
                    }
                ],
            },
            {
                "name": "Administrator synthetic workflow — run selected steps",
                "item": operations,
                "event": [
                    {
                        "listen": "prerequest",
                        "script": {"type": "text/javascript", "exec": mutation_guard},
                    }
                ],
            },
            {
                "name": "Student synthetic scanner and enrollment matching",
                "item": scanner,
                "event": [
                    {
                        "listen": "prerequest",
                        "script": {"type": "text/javascript", "exec": mutation_guard},
                    }
                ],
            },
            {
                "name": "Disposable connected HTTP acceptance",
                "item": journey,
                "event": [
                    {
                        "listen": "prerequest",
                        "script": {"type": "text/javascript", "exec": local_guard + mutation_guard},
                    }
                ],
            },
        ],
    }
    values = {
        "base_url": "http://127.0.0.1:8000",
        "workspace_role": "student",
        "id_token": "",
        "academic_period_id": "",
        "week_start": "",
        "week_end": "",
        "preference_revision": "",
        "preference_generation": "",
        "file_id": "",
        "approved_cloud_qualification": "false",
        "approved_disposable_qualification": "false",
        "auth_emulator_url": "",
        "approved_synthetic_journey": "false",
        **dict.fromkeys(
            [
                "student_uid",
                "approved_verification_reference",
                "faculty_id",
                "teacher_email",
                "invitation_id",
                "invitation_token",
                "scan_id",
                "academic_year",
                "academic_revision",
                "publication_command",
                "student_token",
                "teacher_token",
                "synthetic_student_id",
                "synthetic_course_code",
                "synthetic_pdf_path",
            ],
            "",
        ),
    }
    environment = {
        "name": "ClassSync — local or approved staging template",
        "_postman_variable_scope": "environment",
        "values": [
            {
                "key": key,
                "value": value,
                "enabled": True,
                "type": "secret" if key.endswith("token") else "default",
            }
            for key, value in values.items()
        ],
    }
    ROOT.mkdir(parents=True, exist_ok=True)
    for filename, value in (
        ("ClassSync.postman_collection.json", collection),
        ("ClassSync.postman_environment.json", environment),
    ):
        (ROOT / filename).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
