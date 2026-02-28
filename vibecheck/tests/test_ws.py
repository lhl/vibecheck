from __future__ import annotations

import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

from vibecheck.app import create_app
from vibecheck.tests.asgi_ws import websocket_session
from vibecheck.events import AssistantEvent
from vibecheck import ws as ws_module


class DummyWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


@pytest.fixture
def ws_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIBECHECK_PSK", "dev-psk")
    ws_module.manager._expected_psk = "dev-psk"
    ws_module.manager.rooms.clear()
    ws_module.manager.socket_to_session.clear()
    ws_module.session_manager.sessions.clear()

    app = create_app()
    try:
        yield app
    finally:
        ws_module.manager.rooms.clear()
        ws_module.manager.socket_to_session.clear()
        ws_module.session_manager.sessions.clear()


@pytest.mark.asyncio
async def test_ws_rejects_invalid_psk(ws_app) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        async with websocket_session(ws_app, "/ws/events/session-1?psk=bad"):
            pass

    assert exc.value.code == 4401


@pytest.mark.asyncio
async def test_ws_connects_with_valid_psk_and_sends_connected_event(ws_app) -> None:
    ws_module.session_manager.attach("session-2")

    async with websocket_session(ws_app, "/ws/events/session-2?psk=dev-psk") as websocket:
        connected = await websocket.receive_json()
        state = await websocket.receive_json()

    assert connected["type"] == "connected"
    assert connected["session_id"] == "session-2"
    assert isinstance(connected["id"], str) and len(connected["id"]) == 8
    assert isinstance(connected["timestamp"], float)
    assert state["type"] == "state"
    assert state["state"] == "idle"


def test_broadcast_targets_only_subscribers_in_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECHECK_PSK", "dev-psk")
    manager = ws_module.ConnectionManager()
    alpha_one = DummyWebSocket()
    alpha_two = DummyWebSocket()
    beta_one = DummyWebSocket()

    manager.rooms["alpha"] = {alpha_one, alpha_two}
    manager.rooms["beta"] = {beta_one}
    manager.socket_to_session = {
        alpha_one: "alpha",
        alpha_two: "alpha",
        beta_one: "beta",
    }

    asyncio.run(manager.broadcast("alpha", AssistantEvent(content="hello alpha")))

    assert len(alpha_one.messages) == 1
    assert len(alpha_two.messages) == 1
    assert alpha_one.messages[0]["type"] == "assistant"
    assert beta_one.messages == []


def test_disconnect_removes_client_from_room(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECHECK_PSK", "dev-psk")
    manager = ws_module.ConnectionManager()
    socket = DummyWebSocket()
    manager.rooms["room-a"] = {socket}
    manager.socket_to_session = {socket: "room-a"}

    asyncio.run(manager.disconnect(socket))

    assert manager.rooms == {}
    assert manager.socket_to_session == {}


@pytest.mark.asyncio
async def test_backlog_is_delivered_on_connect(ws_app) -> None:
    bridge = ws_module.session_manager.attach("session-backlog")
    bridge.add_event(AssistantEvent(content="from backlog"))

    async with websocket_session(ws_app, "/ws/events/session-backlog?psk=dev-psk") as websocket:
        connected = await websocket.receive_json()
        state = await websocket.receive_json()
        backlog_event = await websocket.receive_json()

    assert connected["type"] == "connected"
    assert connected["session_id"] == "session-backlog"
    assert state["type"] == "state"
    assert backlog_event["type"] == "assistant"
    assert backlog_event["content"] == "from backlog"


@pytest.mark.asyncio
async def test_ws_rejects_unknown_session_and_does_not_attach(ws_app) -> None:
    async with websocket_session(ws_app, "/ws/events/ghost-session?psk=dev-psk") as websocket:
        with pytest.raises(WebSocketDisconnect) as exc:
            await websocket.receive_json()

    assert exc.value.code == 4404
    assert "ghost-session" not in ws_module.session_manager.sessions


@pytest.mark.asyncio
async def test_two_sessions_get_independent_backlogs(ws_app) -> None:
    session_a = ws_module.session_manager.attach("session-a")
    session_b = ws_module.session_manager.attach("session-b")
    session_a.add_event(AssistantEvent(content="only-a"))
    session_b.add_event(AssistantEvent(content="only-b"))

    async with websocket_session(ws_app, "/ws/events/session-a?psk=dev-psk") as websocket_a:
        await websocket_a.receive_json()  # connected
        await websocket_a.receive_json()  # state
        backlog_a = await websocket_a.receive_json()

    async with websocket_session(ws_app, "/ws/events/session-b?psk=dev-psk") as websocket_b:
        await websocket_b.receive_json()  # connected
        await websocket_b.receive_json()  # state
        backlog_b = await websocket_b.receive_json()

    assert backlog_a["content"] == "only-a"
    assert backlog_b["content"] == "only-b"
