"""Run the reviewed local Postman collection inside the owned emulator qualification."""

import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx


def api(client, gateway, token, method, path, *, body=None, role="administrator", expected=200):
    headers = {"X-ClassSync-Role": role}
    if token:
        headers["Authorization"] = "Bearer " + token
    reply = client.request(method, gateway + path, headers=headers, json=body)
    if reply.status_code != expected:
        raise RuntimeError(
            f"Synthetic {method} qualification expected {expected}, got {reply.status_code}"
        )
    value = reply.json()
    return value.get("data", value)


def history(client, gateway, token, fixture):
    return api(client, gateway, token, "GET", "/api/v1/timetables/history/" + fixture["period"])[
        "versions"
    ]


def fresh_command(client, gateway, token, fixture):
    before = history(client, gateway, token, fixture)
    snapshot = api(client, gateway, token, "GET", "/api/v1/academic/periods/" + fixture["period"])
    generated = api(
        client,
        gateway,
        token,
        "POST",
        "/api/v1/scheduling/academic/" + fixture["period"] + "/generate",
        body={"expected_revision": snapshot["period"]["revision"]},
    )
    assert generated["solver_status"] in {"optimal", "feasible"}
    assert generated["validation"]["valid"] and generated["hard_conflict_count"] == 0
    draft = api(
        client,
        gateway,
        token,
        "POST",
        "/api/v1/scheduling/drafts",
        expected=201,
        body={
            "run_id": generated["run_id"],
            "input_hash": generated["input_hash"],
            "title": "Disposable Postman publication",
            "idempotency_key": "postman-save-" + uuid4().hex,
        },
    )
    assert draft["id"] not in {row["draft_id"] for row in before}
    assert history(client, gateway, token, fixture) == before
    return {
        "draft_id": draft["id"],
        "source": "administrator",
        "dataset": "institutional",
        "expected_version": max((row["revision"] for row in before), default=0),
        "expected_academic_revision": snapshot["period"]["revision"],
        "idempotency_key": "postman-publish-" + uuid4().hex,
        "calendar": snapshot["period"]["calendar"],
    }, before


def verify_publication(client, gateway, token, fixture, command, before, identities=None):
    after = history(client, gateway, token, fixture)
    assert len(after) == len(before) + 1
    current = max(after, key=lambda row: row["revision"])
    assert current["revision"] == command["expected_version"] + 1
    assert current["draft_id"] == command["draft_id"] and current["status"] == "published"

    def immutable(rows):
        return {row["id"]: {k: v for k, v in row.items() if k != "status"} for row in rows}

    assert all(immutable(after)[key] == value for key, value in immutable(before).items())
    replay = api(client, gateway, token, "POST", "/api/v1/timetables/publish", body=command)
    assert replay["id"] == current["id"]
    api(client, gateway, None, "POST", "/api/v1/timetables/publish", body=command, expected=401)
    stale = {**command, "idempotency_key": "stale-postman-" + uuid4().hex}
    api(client, gateway, token, "POST", "/api/v1/timetables/publish", body=stale, expected=409)
    for role, identity in (identities or {}).items():
        api(
            client,
            gateway,
            identity,
            "POST",
            "/api/v1/timetables/publish",
            body=command,
            role=role,
            expected=403,
        )
        view = api(
            client,
            gateway,
            identity,
            "GET",
            "/api/v1/timetables/calendar/" + fixture["period"] + "?start=2026-10-05&end=2026-10-11",
            role=role,
        )
        assert view["version"] == current["id"] and view["occurrences"]
    assert history(client, gateway, token, fixture) == after
    return {
        "revision": current["revision"],
        "history_entries": len(after),
        "immutable_history": True,
        "idempotent_replay": True,
        "denied_and_stale_no_writes": True,
        "current_role_projections": bool(identities),
    }


def connected_values(client, endpoint, gateway, project, fixture, token, root):
    def firebase(action, body):
        reply = client.post(
            endpoint + "/identitytoolkit.googleapis.com/v1/accounts:" + action,
            params={"key": "local-emulator-only"},
            json=body,
        )
        if reply.status_code != 200:
            raise RuntimeError("Synthetic emulator setup failed")
        return reply.json()

    identities = []
    for _ in range(2):
        email = "postman-verified-" + uuid4().hex + "@example.test"
        account = {
            "email": email,
            "password": "Local-emulator-password-42!",
            "returnSecureToken": True,
        }
        identity = firebase("signUp", account)
        firebase("sendOobCode", {"requestType": "VERIFY_EMAIL", "idToken": identity["idToken"]})
        codes = client.get(endpoint + f"/emulator/v1/projects/{project}/oobCodes").json()[
            "oobCodes"
        ]
        code = next(
            item["oobCode"]
            for item in reversed(codes)
            if item["email"] == email and item["requestType"] == "VERIFY_EMAIL"
        )
        firebase("update", {"oobCode": code})
        identities.append(firebase("signInWithPassword", account))
    reply = client.get(
        gateway + "/api/v1/academic/periods/" + fixture["period"],
        headers={"Authorization": "Bearer " + token, "X-ClassSync-Role": "administrator"},
    )
    if reply.status_code != 200:
        raise RuntimeError("Synthetic academic snapshot setup failed")
    snapshot = reply.json()
    snapshot = snapshot.get("data", snapshot)
    before = history(client, gateway, token, fixture)
    duplicate = {
        "draft_id": fixture["draft"],
        "source": "administrator",
        "dataset": "institutional",
        "expected_version": 1,
        "expected_academic_revision": snapshot["period"]["revision"],
        "idempotency_key": "duplicate-control-" + uuid4().hex,
        "calendar": snapshot["period"]["calendar"],
    }
    denied = api(
        client, gateway, token, "POST", "/api/v1/timetables/publish", body=duplicate, expected=409
    )
    assert "duplicate_publication" in json.dumps(denied)
    assert history(client, gateway, token, fixture) == before
    command, before = fresh_command(client, gateway, token, fixture)
    return {
        "student_token": identities[0]["idToken"],
        "teacher_token": identities[1]["idToken"],
        "student_uid": identities[0]["localId"],
        "teacher_email": identities[1]["email"],
        "faculty_id": fixture["faculty"],
        "synthetic_student_id": fixture["student"],
        "synthetic_course_code": fixture["codes"][0],
        "academic_year": "2026-2027",
        "academic_revision": str(snapshot["period"]["revision"]),
        "approved_verification_reference": "synthetic-authorized-disposable-fixture",
        "approved_synthetic_journey": "true",
        "synthetic_pdf_path": str(root / "synthetic-registration.pdf"),
        "publication_command": json.dumps(command),
        "_history_before": before,
    }


def qualify(root, *, gateway, endpoint, admin_email, fixture, project, complete=False):
    root = Path(root).resolve()
    if not root.name.startswith("classsync-auth-run-"):
        raise ValueError("Owned disposable qualification directory required")
    endpoint = "http://" + endpoint
    for url in (gateway, endpoint):
        parsed = urlparse(url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
            raise ValueError("Owned loopback providers required")
    binary = Path("var/m5-postman-portable/extracted/postman-cli.exe").resolve()
    if not binary.is_file():
        raise RuntimeError("Reviewed portable Postman runner is not available")
    with httpx.Client(trust_env=False, timeout=10) as client:
        response = client.post(
            endpoint + "/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
            params={"key": "local-emulator-only"},
            json={
                "email": admin_email,
                "password": "Local-emulator-password-42!",
                "returnSecureToken": True,
            },
        )
        if response.status_code != 200:
            raise RuntimeError("Synthetic administrator emulator login failed")
        token = response.json()["idToken"]
        additional = (
            connected_values(client, endpoint, gateway, project, fixture, token, root)
            if complete
            else {}
        )
    environment = json.loads(Path("docs/api/ClassSync.postman_environment.json").read_text())
    values = {
        "base_url": gateway,
        "auth_emulator_url": endpoint,
        "workspace_role": "administrator",
        "id_token": token,
        "academic_period_id": fixture["period"],
        "week_start": "2026-10-05",
        "week_end": "2026-10-11",
        "approved_disposable_qualification": "true",
    }
    values.update(additional)
    for entry in environment["values"]:
        if entry["key"] in values:
            entry["value"] = values[entry["key"]]
    env_file = root / "private-postman-environment.json"
    profile = root / "postman-profile"
    profile.mkdir()
    child = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("POSTMAN_", "GOOGLE_", "FIREBASE_", "GCLOUD_"))
    }
    child.update(
        USERPROFILE=str(profile),
        APPDATA=str(profile),
        LOCALAPPDATA=str(profile),
        HTTP_PROXY="http://127.0.0.1:9",
        HTTPS_PROXY="http://127.0.0.1:9",
        NO_PROXY="127.0.0.1,localhost",
        CI="true",
    )
    try:
        collection_path = Path("docs/api/ClassSync.postman_collection.json").resolve()
        arguments = [
            str(binary),
            "collection",
            "run",
            str(collection_path),
            "-e",
            str(env_file),
            "-i",
            "Core authorized reads and explicit401",
            "-i",
            "Disposable emulator pending-account boundaries",
        ]
        if complete:
            arguments.extend(["-i", "Disposable connected HTTP acceptance"])
        arguments.extend(
            [
                "--no-report-events",
                "--timeout",
                "45000",
                "--timeout-request",
                "10000",
                "--no-insecure-file-read",
            ]
        )

        def execute(command, phase):
            env_file.write_text(json.dumps(environment), encoding="utf-8")
            result = subprocess.run(
                command,
                cwd=root,
                env=child,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            output = (result.stdout + result.stderr).replace(token, "[REDACTED]")
            for name in ("student_token", "teacher_token"):
                if name in additional:
                    output = output.replace(additional[name], "[REDACTED]")
            (root / f"postman-{phase}-console.log").write_text(output, encoding="utf-8")
            if result.returncode:
                raise RuntimeError(
                    "Postman qualification failed; inspect private sanitized console"
                )

        publication = {}
        if complete:
            selected = deepcopy(json.loads(collection_path.read_text()))
            folder = selected["item"][5]
            folder["item"] = [
                item
                for item in folder["item"]
                if item["name"] in {"Publication review", "Publication publish"}
            ]
            assert len(folder["item"]) == 2
            selected["item"] = [folder]
            focused_path = root / "focused-publication-collection.json"
            focused_path.write_text(json.dumps(selected), encoding="utf-8")
            focused = [str(binary), "collection", "run", str(focused_path), "-e", str(env_file)]
            focused.extend(arguments[arguments.index("--no-report-events") :])
            command = json.loads(additional["publication_command"])
            with httpx.Client(trust_env=False, timeout=10) as client:
                api(client, gateway, token, "POST", "/api/v1/timetables/review", body=command)
                assert history(client, gateway, token, fixture) == additional["_history_before"]
            execute(focused, "publication-focused")
            with httpx.Client(trust_env=False, timeout=10) as client:
                publication["focused"] = verify_publication(
                    client, gateway, token, fixture, command, additional["_history_before"]
                )
                command, before = fresh_command(client, gateway, token, fixture)
            for entry in environment["values"]:
                if entry["key"] == "publication_command":
                    entry["value"] = json.dumps(command)
        execute(arguments, "local")
        if complete:
            with httpx.Client(trust_env=False, timeout=10) as client:
                publication["full"] = verify_publication(
                    client,
                    gateway,
                    token,
                    fixture,
                    command,
                    before,
                    {role: additional[role + "_token"] for role in ("student", "teacher")},
                )
        return {
            "runner": "Postman CLI 1.86.0",
            "folders": 3 if complete else 2,
            "requests": 14
            + (len(json.loads(collection_path.read_text())["item"][5]["item"]) if complete else 0),
            "exit_code": 0,
            "cloud_reporting": False,
            "environment_exported": False,
            "scope": "connected synthetic HTTP journey" if complete else "core/pending boundaries",
            "publication": publication,
        }
    finally:
        env_file.unlink(missing_ok=True)
