from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from vibecheck.app import create_app
from vibecheck.bridge import SessionManager, VibeRuntime
from vibecheck.events import AssistantEvent

LONG_TITLE = "0123456789" * 6
TRIMMED_TITLE = LONG_TITLE[:50]


class FakeApprovalResponse:
    YES = "yes"
    NO = "no"


class FakeSessionLogger:
    def __init__(self) -> None:
        self.resumed: tuple[str, Path] | None = None

    def resume_existing_session(self, session_id: str, session_dir: Path) -> None:
        self.resumed = (session_id, session_dir)


class FakeVibeConfig:
    @classmethod
    def load(cls):
        return cls()


class FakeAgentLoop:
    def __init__(self, _config, message_observer=None, enable_streaming: bool = False) -> None:
        _ = enable_streaming
        self.message_observer = message_observer
        self.approval_callback = None
        self.user_input_callback = None
        self.messages: list[object] = []
        self.session_id = "fake-session"
        self.session_logger = FakeSessionLogger()

    def set_approval_callback(self, callback) -> None:
        self.approval_callback = callback

    def set_user_input_callback(self, callback) -> None:
        self.user_input_callback = callback

    async def act(self, _msg: str):
        if False:  # pragma: no cover
            yield None


class FakeToolCallEvent:
    def __init__(self, tool_name: str, args: dict[str, object], tool_call_id: str) -> None:
        self.tool_name = tool_name
        self.args = args
        self.tool_call_id = tool_call_id


class FakeToolResultEvent:
    def __init__(self, tool_call_id: str) -> None:
        self.tool_call_id = tool_call_id
        self.result = None
        self.error = None


class FakeDiffAgentLoop:
    def __init__(self, _config, message_observer=None, enable_streaming: bool = False) -> None:
        _ = enable_streaming
        self.message_observer = message_observer
        self.approval_callback = None
        self.user_input_callback = None

    def set_approval_callback(self, callback) -> None:
        self.approval_callback = callback

    def set_user_input_callback(self, callback) -> None:
        self.user_input_callback = callback

    async def act(self, _msg: str):
        args = {"path": "file.txt", "content": "after", "overwrite": True}
        yield FakeToolCallEvent(tool_name="write_file", args=args, tool_call_id="tc-1")
        Path("file.txt").write_text("after", encoding="utf-8")
        yield FakeToolResultEvent(tool_call_id="tc-1")


@pytest_asyncio.fixture
async def sessions_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> AsyncIterator[tuple[AsyncClient, SessionManager]]:
    monkeypatch.setenv("VIBECHECK_PSK", "dev-psk")

    logs_root = tmp_path / ".vibe" / "logs" / "session"
    session_dir = logs_root / "session_a"
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(
        json.dumps(
            {
                "session_id": "session-a",
                "start_time": "2026-02-28T00:00:00Z",
                "end_time": "2026-02-28T00:01:00Z",
                "title": LONG_TITLE,
            }
        ),
        encoding="utf-8",
    )
    (session_dir / "messages.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "content": "Hello"}),
                json.dumps({"role": "assistant", "content": "Hi there"}),
            ]
        )
        + "\n",
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
async def test_sessions_list_includes_title_from_meta(sessions_client) -> None:
    client, _ = sessions_client

    response = await client.get("/api/sessions", headers={"X-PSK": "dev-psk"})

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "session-a"
    assert payload[0]["title"] == TRIMMED_TITLE


@pytest.mark.asyncio
async def test_resume_reattaches_bridge_and_returns_backlog(
    monkeypatch: pytest.MonkeyPatch, sessions_client
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=None,
        answer_cls=None,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    client, manager = sessions_client

    response = await client.post("/api/sessions/session-a/resume", headers={"X-PSK": "dev-psk"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "session-a"
    assert payload["attach_mode"] == "managed"
    assert payload["controllable"] is True

    backlog_types = [event["type"] for event in payload["backlog"]]
    assert "user_message" in backlog_types
    assert "assistant" in backlog_types

    bridge = manager.get("session-a")
    assert bridge.controllable is True


@pytest.mark.asyncio
async def test_resume_already_attached_session_is_noop(
    monkeypatch: pytest.MonkeyPatch, sessions_client
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=None,
        answer_cls=None,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    client, manager = sessions_client

    bridge = manager.attach("session-a", attach_mode="managed")
    bridge.add_event(AssistantEvent(content="existing backlog"))

    first = await client.post("/api/sessions/session-a/resume", headers={"X-PSK": "dev-psk"})
    second = await client.post("/api/sessions/session-a/resume", headers={"X-PSK": "dev-psk"})

    assert first.status_code == 200
    assert second.status_code == 200

    payload = second.json()
    assert any(
        event["type"] == "assistant" and "existing backlog" in event.get("content", "")
        for event in payload["backlog"]
    )


@pytest.mark.asyncio
async def test_diffs_endpoint_returns_before_after_structured_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sessions_client
) -> None:
    import vibecheck.bridge as bridge_module

    monkeypatch.chdir(tmp_path)
    Path("file.txt").write_text("before", encoding="utf-8")

    runtime = VibeRuntime(
        agent_loop_cls=FakeDiffAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=None,
        answer_cls=None,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    client, manager = sessions_client

    bridge = manager.attach("managed-1", attach_mode="managed")
    await bridge.start_session("run tool")

    response = await client.get("/api/sessions/managed-1/diffs", headers={"X-PSK": "dev-psk"})
    assert response.status_code == 200

    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["call_id"] == "tc-1"
    assert payload[0]["tool_name"] == "write_file"
    assert payload[0]["before"] == "before"
    assert payload[0]["after"] == "after"


@pytest.mark.asyncio
async def test_resume_unknown_session_returns_404(sessions_client) -> None:
    client, _ = sessions_client

    response = await client.post("/api/sessions/does-not-exist/resume", headers={"X-PSK": "dev-psk"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_diffs_endpoint_returns_empty_list_when_no_diffs(sessions_client) -> None:
    client, _ = sessions_client

    response = await client.get("/api/sessions/session-a/diffs", headers={"X-PSK": "dev-psk"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_resume_calls_session_logger_even_without_message_history(
    monkeypatch: pytest.MonkeyPatch, sessions_client
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=None,
        answer_cls=None,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    client, manager = sessions_client

    logs_root = manager.logs_root
    session_dir = logs_root / "session_empty"
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(
        json.dumps(
            {
                "session_id": "session-empty",
                "start_time": "2026-02-28T00:02:00Z",
                "end_time": "2026-02-28T00:03:00Z",
                "title": "Empty history session",
            }
        ),
        encoding="utf-8",
    )

    response = await client.post("/api/sessions/session-empty/resume", headers={"X-PSK": "dev-psk"})

    assert response.status_code == 200

    bridge = manager.get("session-empty")
    assert bridge._agent_loop is not None
    assert bridge._agent_loop.session_id == "session-empty"
    assert bridge._agent_loop.session_logger.resumed == ("session-empty", session_dir)
