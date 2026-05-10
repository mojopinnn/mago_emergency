"""
pytest 로드 순서: 스케줄러 기동을 막은 뒤 main 임포트.
"""
import sys
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

patch("scheduler.start", MagicMock()).start()
patch("scheduler.stop", MagicMock()).start()

import pytest


@pytest.fixture(autouse=True)
def reset_store():
    import store

    store.reset_for_testing()
    yield


@pytest.fixture(autouse=True)
def mock_push_and_shotgrid_defaults(request):
    with ExitStack() as stack:
        stack.enter_context(patch("push.send_push", return_value=True))
        stack.enter_context(patch("shotgrid_client.update_user_push_token"))
        stack.enter_context(patch("shotgrid_client.get_users_by_role", return_value=[]))
        stack.enter_context(patch("main._notify_cc_users_push", MagicMock()))
        stack.enter_context(patch("scheduler._send_cc_escalation", new=AsyncMock()))
        if not request.node.get_closest_marker("real_follow_up_notify"):
            stack.enter_context(patch("main._notify_follow_up_recipients", MagicMock()))
        yield


@pytest.fixture
def env_keys(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "BGMO_test_public_key_placeholder")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "RUk_test_private_key_placeholder")
    monkeypatch.setenv("VAPID_EMAIL", "mailto:test@example.com")
    monkeypatch.setenv("SHOTGRID_URL", "https://teststudio.shotgrid.autodesk.com")
    monkeypatch.setenv("SHOTGRID_SCRIPT_NAME", "test_script")
    monkeypatch.setenv("SHOTGRID_API_KEY", "test_api_key")


@pytest.fixture
def client(env_keys):
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as c:
        yield c
