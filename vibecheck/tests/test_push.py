from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
from pathlib import Path

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from vibecheck.app import create_app
from vibecheck.bridge import session_manager
from vibecheck.events import ApprovalRequestEvent


@pytest.fixture
def push_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest_asyncio.fixture
async def push_client(psk: str, push_home: Path) -> AsyncClient:
    _ = psk, push_home
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_push_subscribe_and_unsubscribe_round_trip(
    push_client: AsyncClient,
    psk: str,
    push_home: Path,
) -> None:
    _ = push_home
    subscription = {
        "endpoint": "https://example.com/push/abc",
        "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
    }

    subscribe = await push_client.post(
        "/api/push/subscribe",
        headers={"X-PSK": psk},
        json=subscription,
    )
    assert subscribe.status_code == 200

    unsubscribe = await push_client.post(
        "/api/push/unsubscribe",
        headers={"X-PSK": psk},
        json={"endpoint": subscription["endpoint"]},
    )
    assert unsubscribe.status_code == 200


@pytest.mark.asyncio
async def test_push_sends_notification_on_approval_request(
    push_client: AsyncClient,
    psk: str,
    push_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = push_home

    monkeypatch.setenv("VIBECHECK_VAPID_SUB", "mailto:tests@example.com")

    calls: list[dict[str, object]] = []

    async def fake_webpush(*, subscription_info, data=None, vapid_private_key=None, vapid_claims=None, **_kwargs):
        calls.append(
            {
                "subscription_info": subscription_info,
                "data": data,
                "vapid_private_key": vapid_private_key,
                "vapid_claims": vapid_claims,
            }
        )

    import vibecheck.push as push_module

    monkeypatch.setattr(push_module, "webpush_async", fake_webpush)

    async def fake_copy(_tool_name: str, _args: dict[str, object]) -> str:
        return "Please approve (test)"

    monkeypatch.setattr(push_module, "generate_notification_copy", fake_copy)

    subscription = {
        "endpoint": "https://example.com/push/abc",
        "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
    }
    subscribe = await push_client.post(
        "/api/push/subscribe",
        headers={"X-PSK": psk},
        json=subscription,
    )
    assert subscribe.status_code == 200

    bridge = session_manager.attach("push-session")

    task = asyncio.create_task(
        bridge.request_approval(
            call_id="tc-push-1",
            tool_name="bash",
            args={"command": "echo hi"},
        )
    )
    await asyncio.sleep(0)

    for _ in range(100):
        if calls:
            break
        await asyncio.sleep(0)

    assert calls, "expected pywebpush.webpush to be called"
    payload = calls[0]["data"]
    assert isinstance(payload, str) and "requireInteraction" in payload
    decoded = json.loads(payload)
    assert decoded["body"] == "Please approve (test)"
    assert decoded["call_id"] == "tc-push-1", "payload must include call_id for call-bound actions"
    assert calls[0]["vapid_claims"] == {"sub": "mailto:tests@example.com"}

    assert bridge.resolve_approval("tc-push-1", approved=True)
    await task


@pytest.mark.asyncio
async def test_push_sends_idle_escalation_after_waiting_for_approval(
    push_client: AsyncClient,
    psk: str,
    push_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = push_home

    import vibecheck.push as push_module

    manager = push_module._current_push_manager
    assert manager is not None

    now = [datetime(2026, 2, 28, 12, 0, 0)]
    manager.intensity._now_fn = lambda: now[0]  # type: ignore[attr-defined]
    manager.intensity.level = 4

    calls: list[dict[str, object]] = []

    async def fake_webpush(*, subscription_info, data=None, **_kwargs):
        calls.append({"subscription_info": subscription_info, "data": data})

    monkeypatch.setattr(push_module, "webpush_async", fake_webpush)

    async def fake_copy(_tool_name: str, _args: dict[str, object]) -> str:
        return "Approve (test)"

    monkeypatch.setattr(push_module, "generate_notification_copy", fake_copy)

    subscription = {
        "endpoint": "https://example.com/push/idle",
        "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
    }
    subscribe = await push_client.post(
        "/api/push/subscribe",
        headers={"X-PSK": psk},
        json=subscription,
    )
    assert subscribe.status_code == 200

    bridge = session_manager.attach("push-session-idle")

    task = asyncio.create_task(
        bridge.request_approval(
            call_id="tc-push-idle-1",
            tool_name="bash",
            args={"command": "echo hi"},
        )
    )
    await asyncio.sleep(0)

    for _ in range(100):
        if calls:
            break
        await asyncio.sleep(0)

    assert calls, "expected initial approval push to be sent"
    calls.clear()

    for _ in range(100):
        if "push-session-idle" in manager._idle_sessions:  # type: ignore[attr-defined]
            break
        await asyncio.sleep(0)

    assert "push-session-idle" in manager._idle_sessions  # type: ignore[attr-defined]

    now[0] += timedelta(minutes=5)
    await manager._send_idle_escalation_if_needed()

    assert calls, "expected idle escalation push to be sent"
    payload = calls[0]["data"]
    decoded = json.loads(payload)
    assert decoded["title"].startswith("💤")
    assert "idle for 5min" in decoded["body"]
    assert decoded["url"].endswith("sid=push-session-idle")

    assert bridge.resolve_approval("tc-push-idle-1", approved=True)
    await task


@pytest.mark.asyncio
async def test_push_prunes_subscription_when_endpoint_is_gone(
    push_client: AsyncClient,
    psk: str,
    push_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = push_home

    import vibecheck.push as push_module

    manager = push_module._current_push_manager
    assert manager is not None

    subscription = {
        "endpoint": "https://example.com/push/gone",
        "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
    }
    subscribe = await push_client.post(
        "/api/push/subscribe",
        headers={"X-PSK": psk},
        json=subscription,
    )
    assert subscribe.status_code == 200

    class _DummyResponse:
        status = 410

    async def fake_webpush(*_args, **_kwargs):
        raise push_module.WebPushException("gone", response=_DummyResponse())

    monkeypatch.setattr(push_module, "webpush_async", fake_webpush)

    async def fake_copy(_tool_name: str, _args: dict[str, object]) -> str:
        return "Approve (test)"

    monkeypatch.setattr(push_module, "generate_notification_copy", fake_copy)

    await manager.send_for_event(
        "session-gone",
        ApprovalRequestEvent(call_id="tc-gone-1", tool_name="bash", args={}),
    )

    endpoints = {item.get("endpoint") for item in manager._load_subscriptions()}
    assert subscription["endpoint"] not in endpoints


@pytest.mark.asyncio
async def test_push_subscriptions_file_is_restricted_to_owner(
    push_client: AsyncClient,
    psk: str,
    push_home: Path,
) -> None:
    _ = push_home

    subscription = {
        "endpoint": "https://example.com/push/perms",
        "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
    }

    subscribe = await push_client.post(
        "/api/push/subscribe",
        headers={"X-PSK": psk},
        json=subscription,
    )
    assert subscribe.status_code == 200

    path = push_home / ".vibecheck" / "push_subscriptions.json"
    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600


@pytest.mark.asyncio
async def test_push_idle_escalation_covers_multiple_sessions(
    push_client: AsyncClient,
    psk: str,
    push_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When two sessions are waiting, idle escalation fires for both."""
    _ = push_home

    import vibecheck.push as push_module

    manager = push_module._current_push_manager
    assert manager is not None

    now = [datetime(2026, 2, 28, 12, 0, 0)]
    manager.intensity._now_fn = lambda: now[0]  # type: ignore[attr-defined]
    manager.intensity.level = 4

    calls: list[dict[str, object]] = []

    async def fake_webpush(*, subscription_info, data=None, **_kwargs):
        calls.append({"subscription_info": subscription_info, "data": data})

    monkeypatch.setattr(push_module, "webpush_async", fake_webpush)

    async def fake_copy(_tool_name: str, _args: dict[str, object]) -> str:
        return "Approve (test)"

    monkeypatch.setattr(push_module, "generate_notification_copy", fake_copy)

    subscription = {
        "endpoint": "https://example.com/push/multi-idle",
        "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
    }
    subscribe = await push_client.post(
        "/api/push/subscribe",
        headers={"X-PSK": psk},
        json=subscription,
    )
    assert subscribe.status_code == 200

    bridge_a = session_manager.attach("session-a")
    bridge_b = session_manager.attach("session-b")

    task_a = asyncio.create_task(
        bridge_a.request_approval(call_id="tc-a", tool_name="bash", args={"command": "echo a"})
    )
    await asyncio.sleep(0)
    task_b = asyncio.create_task(
        bridge_b.request_approval(call_id="tc-b", tool_name="bash", args={"command": "echo b"})
    )
    await asyncio.sleep(0)

    for _ in range(100):
        if "session-a" in manager._idle_sessions and "session-b" in manager._idle_sessions:
            break
        await asyncio.sleep(0)

    assert "session-a" in manager._idle_sessions
    assert "session-b" in manager._idle_sessions

    calls.clear()
    now[0] += timedelta(minutes=5)
    await manager._send_idle_escalation_if_needed()

    # Should have sent escalation for both sessions
    idle_tags = set()
    for call in calls:
        payload_str = call["data"]
        decoded = json.loads(payload_str)
        idle_tags.add(decoded.get("tag", ""))

    assert "idle:session-a" in idle_tags, "expected idle escalation for session-a"
    assert "idle:session-b" in idle_tags, "expected idle escalation for session-b"

    assert bridge_a.resolve_approval("tc-a", approved=True)
    assert bridge_b.resolve_approval("tc-b", approved=True)
    await task_a
    await task_b


def test_vapid_keypair_regenerates_when_keys_file_is_corrupt(
    push_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.push as push_module

    storage_dir = push_home / ".vibecheck"
    storage_dir.mkdir(parents=True, exist_ok=True)
    keys_path = storage_dir / "vapid_keys.json"
    keys_path.write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(
        push_module,
        "_generate_vapid_keypair",
        lambda: push_module.VapidKeypair(public_key="public", private_key="private"),
    )

    manager = push_module.PushManager(storage_dir=storage_dir)
    keypair = manager.get_or_create_vapid_keypair()
    assert keypair.public_key == "public"
    assert keypair.private_key == "private"

    payload = json.loads(keys_path.read_text(encoding="utf-8"))
    assert payload["public_key"] == "public"
    assert payload["private_key"] == "private"

    assert (keys_path.stat().st_mode & 0o777) == 0o600
