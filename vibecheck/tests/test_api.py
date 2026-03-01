from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from vibecheck.app import create_app
from vibecheck.bridge import SessionManager
from vibecheck.events import AssistantEvent


@pytest_asyncio.fixture
async def api_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[tuple[AsyncClient, SessionManager]]:
    monkeypatch.setenv("VIBECHECK_PSK", "dev-psk")

    logs_root = tmp_path / ".vibe" / "logs" / "session"
    session_dir = logs_root / "session_a"
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(
        json.dumps({"session_id": "session-a", "start_time": "2026-02-28T00:00:00Z"}),
        encoding="utf-8",
    )

    manager = SessionManager(logs_root=logs_root)

    import vibecheck.bridge as bridge_module
    import vibecheck.routes.api as api_module
    import vibecheck.ws as ws_module

    monkeypatch.setattr(bridge_module, "session_manager", manager)
    monkeypatch.setattr(api_module, "session_manager", manager)
    monkeypatch.setattr(ws_module, "session_manager", manager)
    manager.set_connection_manager(ws_module.manager)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, manager


@pytest.mark.asyncio
async def test_sessions_endpoint_lists_discovered_sessions(api_client) -> None:
    client, _ = api_client
    response = await client.get("/api/sessions", headers={"X-PSK": "dev-psk"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == "session-a"
    assert payload[0]["status"] == "disconnected"


@pytest.mark.asyncio
async def test_state_and_detail_endpoints(api_client) -> None:
    client, manager = api_client
    bridge = manager.attach("session-a")
    bridge.state = "running"
    bridge.add_event(AssistantEvent(content="hello from backlog"))

    state_response = await client.get("/api/sessions/session-a/state", headers={"X-PSK": "dev-psk"})
    assert state_response.status_code == 200
    assert state_response.json() == {
        "state": "running",
        "attach_mode": "observe_only",
        "controllable": False,
    }

    detail_response = await client.get("/api/sessions/session-a", headers={"X-PSK": "dev-psk"})
    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["id"] == "session-a"
    assert payload["state"] == "running"
    assert payload["backlog"][-1]["content"] == "hello from backlog"


@pytest.mark.asyncio
async def test_approve_pending_and_missing_cases(api_client) -> None:
    client, manager = api_client
    bridge = manager.attach("session-a")

    missing = await client.post(
        "/api/sessions/session-a/approve",
        headers={"X-PSK": "dev-psk"},
        json={"call_id": "nope", "approved": True},
    )
    assert missing.status_code == 404

    future: asyncio.Future = asyncio.get_running_loop().create_future()
    bridge.pending_approval["tc-1"] = future
    bridge.pending_approval_context["tc-1"] = {"tool_name": "bash", "args": {"command": "ls"}}
    bridge.state = "waiting_approval"

    resolved = await client.post(
        "/api/sessions/session-a/approve",
        headers={"X-PSK": "dev-psk"},
        json={"call_id": "tc-1", "approved": False, "edited_args": {"safe": True}},
    )
    assert resolved.status_code == 200
    assert await future == {"approved": False, "edited_args": {"safe": True}}


@pytest.mark.asyncio
async def test_approve_logs_notification_request_and_success_outcome(api_client, caplog: pytest.LogCaptureFixture) -> None:
    client, manager = api_client
    bridge = manager.attach("session-a")

    future: asyncio.Future = asyncio.get_running_loop().create_future()
    bridge.pending_approval["tc-1"] = future
    bridge.pending_approval_context["tc-1"] = {"tool_name": "bash", "args": {"command": "ls"}}
    bridge.state = "waiting_approval"

    with caplog.at_level(logging.WARNING, logger="vibecheck.routes.api"):
        response = await client.post(
            "/api/sessions/session-a/approve",
            headers={
                "X-PSK": "dev-psk",
                "X-Vibecheck-Notification-Action": "approve",
                "X-Vibecheck-Notification-Source": "sw_notificationclick",
            },
            json={"call_id": "tc-1", "approved": True},
        )

    assert response.status_code == 200
    assert await future == {"approved": True, "edited_args": None}
    assert "notification approval request session=session-a call_id=tc-1 approved=True action=approve source=sw_notificationclick" in caplog.text
    assert "notification approval outcome session=session-a call_id=tc-1 status=ok" in caplog.text


@pytest.mark.asyncio
async def test_approve_writes_notification_audit_file(api_client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, manager = api_client
    bridge = manager.attach("session-a")

    future: asyncio.Future = asyncio.get_running_loop().create_future()
    bridge.pending_approval["tc-1"] = future
    bridge.pending_approval_context["tc-1"] = {"tool_name": "bash", "args": {"command": "ls"}}
    bridge.state = "waiting_approval"

    audit_path = tmp_path / "notification-audit.log"
    monkeypatch.setenv("VIBECHECK_DEBUG", "1")
    monkeypatch.setenv("VIBECHECK_NOTIFICATION_AUDIT_LOG", str(audit_path))

    response = await client.post(
        "/api/sessions/session-a/approve",
        headers={
            "X-PSK": "dev-psk",
            "X-Vibecheck-Notification-Action": "approve",
            "X-Vibecheck-Notification-Source": "sw_notificationclick",
        },
        json={"call_id": "tc-1", "approved": True},
    )

    assert response.status_code == 200
    assert await future == {"approved": True, "edited_args": None}
    assert audit_path.exists()
    audit_text = audit_path.read_text(encoding="utf-8")
    assert "notification approval request session=session-a call_id=tc-1 approved=True action=approve source=sw_notificationclick" in audit_text
    assert "notification approval outcome session=session-a call_id=tc-1 status=ok" in audit_text


@pytest.mark.asyncio
async def test_approve_logs_notification_missing_outcome(api_client, caplog: pytest.LogCaptureFixture) -> None:
    client, manager = api_client
    manager.attach("session-a")

    with caplog.at_level(logging.WARNING, logger="vibecheck.routes.api"):
        response = await client.post(
            "/api/sessions/session-a/approve",
            headers={
                "X-PSK": "dev-psk",
                "X-Vibecheck-Notification-Action": "deny",
                "X-Vibecheck-Notification-Source": "sw_notificationclick",
            },
            json={"call_id": "missing", "approved": False},
        )

    assert response.status_code == 404
    assert "notification approval request session=session-a call_id=missing approved=False action=deny source=sw_notificationclick" in caplog.text
    assert "notification approval outcome session=session-a call_id=missing status=missing" in caplog.text


@pytest.mark.asyncio
async def test_approve_records_resolution_source_in_event_backlog(api_client) -> None:
    client, manager = api_client
    bridge = manager.attach("session-a")

    future: asyncio.Future = asyncio.get_running_loop().create_future()
    bridge.pending_approval["tc-source"] = future
    bridge.pending_approval_context["tc-source"] = {"tool_name": "bash", "args": {"command": "pwd"}}
    bridge.state = "waiting_approval"

    response = await client.post(
        "/api/sessions/session-a/approve",
        headers={
            "X-PSK": "dev-psk",
            "X-Vibecheck-Approval-Source": "pwa_ui",
        },
        json={"call_id": "tc-source", "approved": True},
    )
    assert response.status_code == 200
    assert await future == {"approved": True, "edited_args": None}

    resolution = next(
        event
        for event in reversed(bridge.backlog())
        if getattr(event, "type", "") == "approval_resolution" and getattr(event, "call_id", "") == "tc-source"
    )
    assert getattr(resolution, "source", None) == "pwa_ui"


@pytest.mark.asyncio
async def test_input_pending_and_missing_cases(api_client) -> None:
    client, manager = api_client
    bridge = manager.attach("session-a")

    missing = await client.post(
        "/api/sessions/session-a/input",
        headers={"X-PSK": "dev-psk"},
        json={"request_id": "req-missing", "response": "yes"},
    )
    assert missing.status_code == 404

    future: asyncio.Future = asyncio.get_running_loop().create_future()
    bridge.pending_input["req-1"] = future
    bridge.pending_input_context["req-1"] = {"question": "Continue?"}
    bridge.state = "waiting_input"

    resolved = await client.post(
        "/api/sessions/session-a/input",
        headers={"X-PSK": "dev-psk"},
        json={"request_id": "req-1", "response": "yes"},
    )
    assert resolved.status_code == 200
    assert await future == "yes"


@pytest.mark.asyncio
async def test_message_returns_503_when_runtime_unavailable(api_client) -> None:
    client, manager = api_client
    bridge = manager.attach("session-a")

    message_response = await client.post(
        "/api/sessions/session-a/message",
        headers={"X-PSK": "dev-psk"},
        json={"content": "hello"},
    )
    assert message_response.status_code == 503
    assert "runtime unavailable" in message_response.json()["detail"].lower()
    assert bridge.messages_to_inject[-1] == "hello"


@pytest.mark.asyncio
async def test_fleet_state_aggregates(api_client) -> None:
    client, manager = api_client
    bridge = manager.attach("session-a")
    bridge.state = "running"

    state_response = await client.get("/api/state", headers={"X-PSK": "dev-psk"})
    assert state_response.status_code == 200
    assert state_response.json() == {"total": 1, "running": 1, "waiting": 0, "idle": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/state", None),
        ("get", "/api/sessions", None),
        ("get", "/api/push/vapid-key", None),
        ("get", "/api/sessions/session-a/state", None),
        ("get", "/api/sessions/session-a", None),
        ("post", "/api/sessions/session-a/message", {"content": "hi"}),
        ("post", "/api/sessions/session-a/approve", {"call_id": "tc-1", "approved": True}),
        ("post", "/api/sessions/session-a/input", {"request_id": "req-1", "response": "ok"}),
        ("post", "/api/push/subscribe", {"endpoint": "https://example.com/push/abc", "keys": {"p256dh": "p", "auth": "a"}}),
        ("post", "/api/push/unsubscribe", {"endpoint": "https://example.com/push/abc"}),
        ("post", "/api/translate", {"text": "Hello", "target_lang": "ja"}),
        ("post", "/api/voice/transcribe", {"fake": "audio"}),
    ],
)
async def test_protected_endpoints_require_psk(api_client, method: str, path: str, json_body: dict | None) -> None:
    client, _ = api_client
    response = await client.request(method, path, json=json_body)
    assert response.status_code == 401
