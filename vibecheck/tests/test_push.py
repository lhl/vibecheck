from __future__ import annotations

import asyncio
import json
from pathlib import Path

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from vibecheck.app import create_app
from vibecheck.bridge import session_manager


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
    assert calls[0]["vapid_claims"] == {"sub": "mailto:tests@example.com"}

    assert bridge.resolve_approval("tc-push-1", approved=True)
    await task


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
