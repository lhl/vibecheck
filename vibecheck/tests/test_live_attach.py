from __future__ import annotations

import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
import pytest
import pytest_asyncio

from vibecheck.app import create_app
from vibecheck.bridge import SessionManager, VibeRuntime
from vibecheck.tests.asgi_ws import websocket_session


class FakeVibeConfig:
    @classmethod
    def load(cls):
        return cls()


class FakeToolArgs(BaseModel):
    command: str


class FakeUserMessageEvent:
    def __init__(self, content: str, message_id: str) -> None:
        self.content = content
        self.message_id = message_id


class FakeToolCallEvent:
    def __init__(self, tool_name: str, args: FakeToolArgs, tool_call_id: str) -> None:
        self.tool_name = tool_name
        self.args = args
        self.tool_call_id = tool_call_id


class FakeToolResult:
    def __init__(self, output: str) -> None:
        self.output = output

    def model_dump(self, mode: str = "json") -> dict[str, str]:
        _ = mode
        return {"output": self.output}


class FakeToolResultEvent:
    def __init__(self, tool_call_id: str, result: FakeToolResult | None = None, error: str | None = None) -> None:
        self.tool_call_id = tool_call_id
        self.result = result
        self.error = error


class FakeAssistantEvent:
    def __init__(self, content: str, message_id: str) -> None:
        self.content = content
        self.message_id = message_id


class FakeLiveAgentLoop:
    def __init__(self, *_args, **_kwargs) -> None:
        self.session_id = "live-session"
        self.message_observer = None
        self.approval_callback = None
        self.user_input_callback = None

    def set_approval_callback(self, callback) -> None:
        self.approval_callback = callback

    def set_user_input_callback(self, callback) -> None:
        self.user_input_callback = callback

    async def act(self, msg: str):
        yield FakeUserMessageEvent(content=msg, message_id="u-1")
        args = FakeToolArgs(command="echo hello")
        yield FakeToolCallEvent(tool_name="bash", args=args, tool_call_id="tc-live")
        decision, _feedback = await self.approval_callback("bash", args, "tc-live")
        if decision == "yes":
            yield FakeToolResultEvent(tool_call_id="tc-live", result=FakeToolResult("approved"))
        else:
            yield FakeToolResultEvent(tool_call_id="tc-live", error="denied")
        yield FakeAssistantEvent(content="done", message_id="a-1")


@pytest_asyncio.fixture
async def live_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[AsyncClient, SessionManager, object]:
    monkeypatch.setenv("VIBECHECK_PSK", "dev-psk")

    manager = SessionManager(logs_root=tmp_path / "logs")
    runtime = VibeRuntime(
        agent_loop_cls=FakeLiveAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes="yes",
        approval_no="no",
        ask_result_cls=None,
        answer_cls=None,
    )
    loop = FakeLiveAgentLoop(FakeVibeConfig.load())
    bridge = manager.attach("live-session")
    bridge.attach_to_loop(loop, runtime)

    import vibecheck.bridge as bridge_module
    import vibecheck.routes.api as api_module
    import vibecheck.ws as ws_module

    monkeypatch.setattr(bridge_module, "session_manager", manager)
    monkeypatch.setattr(api_module, "session_manager", manager)
    monkeypatch.setattr(ws_module, "session_manager", manager)

    ws_module.manager._expected_psk = "dev-psk"
    ws_module.manager.rooms.clear()
    ws_module.manager.socket_to_session.clear()
    manager.set_connection_manager(ws_module.manager)

    app = create_app()
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    try:
        yield client, manager, app
    finally:
        await client.aclose()
        ws_module.manager.rooms.clear()
        ws_module.manager.socket_to_session.clear()
        manager.sessions.clear()


async def _read_until(websocket, predicate, *, max_messages: int = 20) -> list[dict]:
    seen: list[dict] = []
    for _ in range(max_messages):
        payload = await websocket.receive_json()
        seen.append(payload)
        if predicate(seen):
            return seen
    raise AssertionError("expected websocket messages were not observed")


async def _wait_until(predicate, *, timeout_seconds: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        if await predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


@pytest.mark.asyncio
async def test_live_attach_flow_with_rest_and_websocket(live_client) -> None:
    client, _manager, app = live_client
    headers = {"X-PSK": "dev-psk"}

    message_response = await client.post(
        "/api/sessions/live-session/message",
        headers=headers,
        json={"content": "trigger tool"},
    )
    assert message_response.status_code == 200

    async def approval_is_pending() -> bool:
        response = await client.get("/api/sessions/live-session", headers=headers)
        pending = response.json().get("pending_approval", [])
        return "tc-live" in pending

    await _wait_until(approval_is_pending)

    async with websocket_session(app, "/ws/events/live-session?psk=dev-psk") as websocket:
        connected = await websocket.receive_json()
        state = await websocket.receive_json()
        backlog = await _read_until(
            websocket,
            lambda msgs: any(msg.get("type") == "approval_request" for msg in msgs),
        )

    assert connected["type"] == "connected"
    assert state["type"] == "state"
    assert state["state"] in {"idle", "waiting_approval"}
    assert any(msg.get("type") == "tool_call" for msg in backlog)
    assert any(msg.get("type") == "approval_request" for msg in backlog)

    detail = await client.get("/api/sessions/live-session", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["attach_mode"] == "live"
    assert detail.json()["controllable"] is True

    approve_response = await client.post(
        "/api/sessions/live-session/approve",
        headers=headers,
        json={"call_id": "tc-live", "approved": True},
    )
    assert approve_response.status_code == 200

    async def approval_is_resolved() -> bool:
        response = await client.get("/api/sessions/live-session", headers=headers)
        payload = response.json()
        return payload.get("pending_approval", []) == [] and any(
            event.get("type") == "approval_resolution" for event in payload.get("backlog", [])
        )

    await _wait_until(approval_is_resolved)
