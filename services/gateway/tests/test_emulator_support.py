import time

import firebase_admin
import pytest
from classync_contracts.token_verification import TokenErrorCode, TokenVerificationError

from services.testing.emulator_firebase import emulator_firebase


@pytest.mark.parametrize("project,endpoint", [
    ("real-project", "127.0.0.1:19099"), ("demo-test", "localhost:19099"),
    ("demo-test", "https://127.0.0.1:19099"), ("demo-test", "10.0.0.1:19099"),
    ("demo-test", "127.0.0.1:99999"), ("demo-test", "127.0.0.1:1024"),
])
def test_emulator_helper_rejects_nonlocal_or_nondemo_before_sdk(monkeypatch, project, endpoint):
    before = dict(firebase_admin._apps)
    with pytest.raises(ValueError):
        with emulator_firebase(monkeypatch, project=project, endpoint=endpoint):
            pytest.fail("Invalid configuration yielded adapter")
    assert firebase_admin._apps == before


def test_emulator_helper_cleans_sdk_app_when_caller_fails(monkeypatch):
    before = dict(firebase_admin._apps)
    with pytest.raises(RuntimeError, match="synthetic caller failure"):
        with emulator_firebase(monkeypatch, project="demo-test", endpoint="127.0.0.1:19099"):
            raise RuntimeError("synthetic caller failure")
    assert firebase_admin._apps == before


@pytest.mark.parametrize("changes,expected", [
    ({"exp": 1}, TokenErrorCode.EXPIRED),
    ({"exp": None}, TokenErrorCode.INVALID), ({"exp": "9999999999"}, TokenErrorCode.INVALID),
    ({"exp": True}, TokenErrorCode.INVALID), ({"iat": None}, TokenErrorCode.INVALID),
    ({"iat": int(time.time()) + 3600}, TokenErrorCode.INVALID),
    ({"auth_time": int(time.time()) + 3600}, TokenErrorCode.INVALID),
    ({"auth_time": "1"}, TokenErrorCode.INVALID), ({"firebase": []}, TokenErrorCode.INVALID),
    ({"firebase": None}, TokenErrorCode.INVALID),
])
def test_emulator_helper_validates_times_and_claim_shapes(monkeypatch, changes, expected):
    from services.testing import emulator_firebase as helper

    now = int(time.time())
    claims = {"uid": "synthetic", "sub": "synthetic", "aud": "demo-test",
              "iss": "https://securetoken.google.com/demo-test", "exp": now + 600,
              "iat": now - 10, "auth_time": now - 20, "firebase": {}}
    calls = []

    def verified(token, *, app, check_revoked):
        calls.append(check_revoked)
        return claims | changes

    monkeypatch.setattr(helper.auth, "verify_id_token", verified)
    with emulator_firebase(monkeypatch, project="demo-test", endpoint="127.0.0.1:19099") as sdk:
        with pytest.raises(TokenVerificationError) as caught:
            sdk[0].verify("synthetic-test-only")
    assert caught.value.code is expected
    assert calls == [True]
