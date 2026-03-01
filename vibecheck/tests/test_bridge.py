from __future__ import annotations

import asyncio
import functools
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from vibecheck.bridge import SessionBridge, SessionManager, VibeRuntime
from vibecheck.events import AssistantEvent


class RecordingConnectionManager:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def broadcast(self, session_id: str, event) -> None:
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
        self.events.append((session_id, payload))


class FakeApprovalResponse:
    YES = "yes"
    NO = "no"


class FakeToolArgs(BaseModel):
    model_config = ConfigDict(strict=True)
    command: str


class FakeChoice:
    def __init__(self, label: str) -> None:
        self.label = label


class FakeQuestion:
    def __init__(self, question: str, options: list[FakeChoice]) -> None:
        self.question = question
        self.options = options


class FakeAskUserQuestionArgs:
    def __init__(self) -> None:
        self.questions = [
            FakeQuestion("Continue?", [FakeChoice("yes"), FakeChoice("no")]),
        ]


class FakeAnswer:
    def __init__(self, question: str, answer: str, is_other: bool = False) -> None:
        self.question = question
        self.answer = answer
        self.is_other = is_other


class FakeAskUserQuestionResult:
    def __init__(self, answers: list[FakeAnswer], cancelled: bool = False) -> None:
        self.answers = answers
        self.cancelled = cancelled


class FakeToolResult:
    def __init__(self, answer: str, command: str) -> None:
        self.answer = answer
        self.command = command

    def model_dump(self, mode: str = "json") -> dict[str, str]:
        _ = mode
        return {"answer": self.answer, "command": self.command}


class FakeObservedMessage:
    def __init__(self, role: str, content: str, message_id: str) -> None:
        self.role = role
        self.content = content
        self.message_id = message_id


class FakeUserMessageEvent:
    def __init__(self, content: str, message_id: str) -> None:
        self.content = content
        self.message_id = message_id


class FakeToolCallEvent:
    def __init__(self, tool_name: str, args: FakeToolArgs, tool_call_id: str) -> None:
        self.tool_name = tool_name
        self.args = args
        self.tool_call_id = tool_call_id


class FakeToolResultEvent:
    def __init__(self, tool_call_id: str, result: FakeToolResult | None = None, error: str | None = None) -> None:
        self.tool_call_id = tool_call_id
        self.result = result
        self.error = error


class FakeAssistantEvent:
    def __init__(self, content: str, message_id: str | None = None) -> None:
        self.content = content
        self.message_id = message_id


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

    def set_approval_callback(self, callback) -> None:
        self.approval_callback = callback

    def set_user_input_callback(self, callback) -> None:
        self.user_input_callback = callback

    async def act(self, msg: str):
        if self.message_observer:
            self.message_observer(
                FakeObservedMessage(
                    role="user",
                    content=msg,
                    message_id="m-user-1",
                )
            )
        yield FakeUserMessageEvent(content=msg, message_id="m-user-1")
        if self.message_observer:
            self.message_observer(
                FakeObservedMessage(
                    role="assistant",
                    content="observer-ping",
                    message_id="m-observer-1",
                )
            )

        args = FakeToolArgs(command="ls -la")
        yield FakeToolCallEvent(tool_name="bash", args=args, tool_call_id="tc-1")
        approval, _feedback = await self.approval_callback("bash", args, "tc-1")
        if approval == FakeApprovalResponse.NO:
            yield FakeToolResultEvent(tool_call_id="tc-1", error="denied")
            return

        response = await self.user_input_callback(FakeAskUserQuestionArgs())
        answer = response.answers[0].answer
        yield FakeToolResultEvent(
            tool_call_id="tc-1",
            result=FakeToolResult(answer=answer, command=args.command),
        )
        if self.message_observer:
            self.message_observer(
                FakeObservedMessage(
                    role="assistant",
                    content=f"done {answer}",
                    message_id="m-assistant-1",
                )
            )
        yield FakeAssistantEvent(content=f"done {answer}", message_id="m-assistant-1")


class FakeAgentLoopNoUserEcho(FakeAgentLoop):
    async def act(self, msg: str):
        _ = msg
        if self.message_observer:
            self.message_observer(
                FakeObservedMessage(
                    role="user",
                    content=msg,
                    message_id="m-user-1",
                )
            )
        if self.message_observer:
            self.message_observer(
                FakeObservedMessage(
                    role="assistant",
                    content="observer-ping",
                    message_id="m-observer-1",
                )
            )

        args = FakeToolArgs(command="ls -la")
        yield FakeToolCallEvent(tool_name="bash", args=args, tool_call_id="tc-1")
        approval, _feedback = await self.approval_callback("bash", args, "tc-1")
        if approval == FakeApprovalResponse.NO:
            yield FakeToolResultEvent(tool_call_id="tc-1", error="denied")
            return

        response = await self.user_input_callback(FakeAskUserQuestionArgs())
        answer = response.answers[0].answer
        yield FakeToolResultEvent(
            tool_call_id="tc-1",
            result=FakeToolResult(answer=answer, command=args.command),
        )
        if self.message_observer:
            self.message_observer(
                FakeObservedMessage(
                    role="assistant",
                    content=f"done {answer}",
                    message_id="m-assistant-1",
                )
            )
        yield FakeAssistantEvent(content=f"done {answer}", message_id="m-assistant-1")


async def _wait_until(predicate, *, attempts: int = 100) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not met in time")


@pytest.mark.asyncio
async def test_session_bridge_approval_flow_broadcasts_and_resolves() -> None:
    manager = RecordingConnectionManager()
    bridge = SessionBridge("s1", connection_manager=manager)

    task = asyncio.create_task(bridge.request_approval("tc-1", "bash", {"command": "npm test"}))
    await asyncio.sleep(0)

    assert bridge.state == "waiting_approval"
    assert bridge.resolve_approval(
        "tc-1",
        approved=True,
        edited_args={"command": "npm test -- -u"},
        source="api_test",
    )
    result = await task

    assert result["approved"] is True
    assert result["edited_args"] == {"command": "npm test -- -u"}
    assert bridge.state == "running"
    assert any(event["type"] == "approval_request" for _, event in manager.events)
    resolution_events = [event for _, event in manager.events if event["type"] == "approval_resolution"]
    assert resolution_events
    assert resolution_events[-1]["source"] == "api_test"


@pytest.mark.asyncio
async def test_session_bridge_input_flow_resolves() -> None:
    bridge = SessionBridge("s2")

    task = asyncio.create_task(bridge.request_input("req-1", "continue?", ["yes", "no"]))
    await asyncio.sleep(0)

    assert bridge.state == "waiting_input"
    assert bridge.resolve_input("req-1", "yes")
    assert await task == "yes"
    assert bridge.state == "running"


def test_session_bridge_backlog_is_capped() -> None:
    bridge = SessionBridge("s3")
    for i in range(60):
        bridge.add_event(AssistantEvent(content=f"message-{i}"))

    backlog = bridge.backlog()
    assert len(backlog) == 50
    assert backlog[0].content == "message-10"
    assert backlog[-1].content == "message-59"


def test_session_manager_discover_attach_detach_and_fleet_status(tmp_path: Path) -> None:
    logs_root = tmp_path / "logs" / "session"
    session_a = logs_root / "session_a"
    session_b = logs_root / "session_b"
    session_a.mkdir(parents=True)
    session_b.mkdir(parents=True)

    (session_a / "meta.json").write_text(
        json.dumps({"session_id": "a", "start_time": "2026-02-28T00:00:00Z"}),
        encoding="utf-8",
    )
    (session_b / "meta.json").write_text(
        json.dumps({"session_id": "b", "start_time": "2026-02-28T01:00:00Z"}),
        encoding="utf-8",
    )

    manager = SessionManager(logs_root=logs_root)
    discovered = manager.discover()
    assert {item["id"] for item in discovered} == {"a", "b"}

    bridge_a = manager.attach("a")
    bridge_a.state = "running"
    bridge_b = manager.attach("b")
    bridge_b.state = "waiting_input"

    summary = manager.fleet_status()
    assert summary["total"] == 2
    assert summary["running"] == 1
    assert summary["waiting"] == 1
    assert summary["idle"] == 0

    manager.detach("a")
    assert "a" not in manager.sessions


def test_session_manager_get_raises_for_unknown_session() -> None:
    manager = SessionManager(logs_root=Path("/tmp/does-not-matter"))
    with pytest.raises(KeyError):
        manager.get("missing")


@pytest.mark.asyncio
async def test_start_session_wires_agent_loop_callbacks_and_processes_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    manager = RecordingConnectionManager()
    bridge = SessionBridge("live-session", connection_manager=manager)

    run_task = asyncio.create_task(bridge.start_session("hello"))
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.state == "waiting_approval"
    assert bridge.resolve_approval("tc-1", approved=True)

    await _wait_until(lambda: len(bridge.pending_input) == 1)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")

    await run_task
    assert bridge.state == "idle"

    event_types = [event["type"] for _, event in manager.events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert any(
        event["type"] == "assistant" and "done yes" in event["content"]
        for _, event in manager.events
    )

    bridge.stop()


@pytest.mark.asyncio
async def test_streaming_assistant_chunks_do_not_create_duplicate_chat_bubbles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    class FakeStreamingAgentLoop:
        def __init__(self, _config, message_observer=None, enable_streaming: bool = False) -> None:
            _ = enable_streaming
            self.message_observer = message_observer
            self.approval_callback = None
            self.user_input_callback = None

        def set_approval_callback(self, callback) -> None:
            self.approval_callback = callback

        def set_user_input_callback(self, callback) -> None:
            self.user_input_callback = callback

        async def act(self, msg: str):
            if self.message_observer:
                self.message_observer(FakeObservedMessage(role="user", content=msg, message_id="u-1"))
            yield FakeUserMessageEvent(content=msg, message_id="u-1")

            # Streaming chunks (should not surface as separate bubbles in the PWA).
            yield FakeAssistantEvent(content="Under", message_id=None)
            yield FakeAssistantEvent(content="stood.", message_id="a-1")

            # Final aggregated message appended to history.
            if self.message_observer:
                self.message_observer(
                    FakeObservedMessage(role="assistant", content="Understood.", message_id="a-1")
                )

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeStreamingAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    manager = RecordingConnectionManager()
    bridge = SessionBridge("streaming", connection_manager=manager)

    await bridge.start_session("hello")

    assistant_contents = [
        event["content"] for _, event in manager.events if event["type"] == "assistant"
    ]
    assert "Understood." in assistant_contents
    assert "Under" not in assistant_contents

    bridge.stop()


@pytest.mark.asyncio
async def test_wire_message_observer_does_not_double_invoke_bridge_observer() -> None:
    class Messages:
        def __init__(self, observer) -> None:
            self._observer = observer

    manager = RecordingConnectionManager()
    bridge = SessionBridge("observer-dedupe", connection_manager=manager)

    existing = bridge._on_message_observed
    existing_list_observer = bridge._on_message_observed

    class Loop:
        def __init__(self) -> None:
            self.message_observer = existing
            self.messages = Messages(existing_list_observer)

        def set_approval_callback(self, _callback) -> None:
            return None

        def set_user_input_callback(self, _callback) -> None:
            return None

    bridge.attach_to_loop(Loop(), vibe_runtime=None)

    bridge._agent_loop.message_observer(  # noqa: SLF001
        FakeObservedMessage(role="assistant", content="hi", message_id=None)
    )
    await _wait_until(
        lambda: len([event for _, event in manager.events if event["type"] == "assistant"]) >= 1
    )
    await asyncio.sleep(0)

    assistant_events = [event for _, event in manager.events if event["type"] == "assistant"]
    assert len(assistant_events) == 1
    assert assistant_events[0]["content"] == "hi"

    bridge.stop()


@pytest.mark.asyncio
async def test_inject_message_lazily_starts_agent_loop_when_runtime_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    manager = RecordingConnectionManager()
    bridge = SessionBridge("lazy-live", connection_manager=manager)

    bridge.inject_message("from-api")
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval("tc-1", approved=True)

    await _wait_until(lambda: len(bridge.pending_input) == 1)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")
    await _wait_until(lambda: bridge.state == "idle")

    event_types = [event["type"] for _, event in manager.events]
    user_messages = [
        event for _, event in manager.events if event["type"] == "user_message" and event["content"] == "from-api"
    ]
    assert len(user_messages) == 1
    assert bridge.messages_to_inject[-1] == "from-api"
    assert "tool_call" in event_types
    assert "tool_result" in event_types

    bridge.stop()


@pytest.mark.asyncio
async def test_inject_message_broadcasts_user_message_even_when_agent_loop_does_not_echo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoopNoUserEcho,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    manager = RecordingConnectionManager()
    bridge = SessionBridge("lazy-echo", connection_manager=manager)

    assert bridge.inject_message("from-api")
    await _wait_until(
        lambda: any(
            event["type"] == "user_message" and event["content"] == "from-api" for _, event in manager.events
        )
    )

    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval("tc-1", approved=True)
    await _wait_until(lambda: len(bridge.pending_input) == 1)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")
    await _wait_until(lambda: bridge.state == "idle")

    user_messages = [
        event for _, event in manager.events if event["type"] == "user_message" and event["content"] == "from-api"
    ]
    assert len(user_messages) == 1

    bridge.stop()


@pytest.mark.asyncio
async def test_local_user_message_dedupe_does_not_suppress_unrelated_same_content_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoopNoUserEcho,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    manager = RecordingConnectionManager()
    bridge = SessionBridge("dedupe-scope", connection_manager=manager)

    assert bridge.inject_message("ok")
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval("tc-1", approved=True)
    await _wait_until(lambda: len(bridge.pending_input) == 1)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")
    await _wait_until(lambda: bridge.state == "idle")

    bridge._on_message_observed(FakeObservedMessage(role="user", content="ok", message_id="m-user-2"))
    await asyncio.sleep(0)

    user_messages = [
        event for _, event in manager.events if event["type"] == "user_message" and event["content"] == "ok"
    ]
    assert len(user_messages) == 2

    bridge.stop()


@pytest.mark.asyncio
async def test_edited_args_are_applied_to_tool_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    manager = RecordingConnectionManager()
    bridge = SessionBridge("edit-args", connection_manager=manager)

    run_task = asyncio.create_task(bridge.start_session("hello"))
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval("tc-1", approved=True, edited_args={"command": "pwd"})

    await _wait_until(lambda: len(bridge.pending_input) == 1)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")

    await run_task
    tool_results = [event for _, event in manager.events if event["type"] == "tool_result"]
    assert any('"command": "pwd"' in event["output"] for event in tool_results)

    bridge.stop()


@pytest.mark.asyncio
async def test_invalid_edited_args_deny_execution_and_do_not_mutate_tool_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    manager = RecordingConnectionManager()
    bridge = SessionBridge("edit-args-invalid", connection_manager=manager)

    run_task = asyncio.create_task(bridge.start_session("hello"))
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval(
        "tc-1",
        approved=True,
        edited_args={"command": {"bad": "type"}},
    )

    await run_task
    assert bridge.pending_input == {}
    assert bridge.state == "idle"

    tool_results = [event for _, event in manager.events if event["type"] == "tool_result"]
    assert any(event["is_error"] is True and "denied" in event["output"] for event in tool_results)
    assert not any('"command":' in event["output"] for event in tool_results)

    bridge.stop()


def test_attach_to_loop_sets_live_mode_and_wires_callbacks() -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    fake_loop = FakeAgentLoop(FakeVibeConfig.load())
    bridge = SessionBridge("live-1")

    bridge.attach_to_loop(fake_loop, runtime)

    assert bridge.attach_mode == "live"
    assert bridge.controllable is True
    assert fake_loop.approval_callback is not None
    assert fake_loop.user_input_callback is not None
    assert callable(fake_loop.message_observer)
    assert bridge.state_payload()["attach_mode"] == "live"
    assert bridge.state_payload()["controllable"] is True


def test_session_manager_attaches_discovered_sessions_as_observe_only(tmp_path: Path) -> None:
    logs_root = tmp_path / "logs" / "session"
    session_dir = logs_root / "session_a"
    session_dir.mkdir(parents=True)
    (session_dir / "meta.json").write_text(
        json.dumps({"session_id": "session-a", "start_time": "2026-02-28T00:00:00Z"}),
        encoding="utf-8",
    )

    manager = SessionManager(logs_root=logs_root)
    observed = manager.attach("session-a")
    managed = manager.attach("new-session")

    assert observed.attach_mode == "observe_only"
    assert observed.controllable is False
    assert managed.attach_mode == "managed"
    assert managed.controllable is True


@pytest.mark.asyncio
async def test_attach_to_loop_uses_existing_loop_for_message_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )

    manager = RecordingConnectionManager()
    bridge = SessionBridge("live-2", connection_manager=manager)
    fake_loop = FakeAgentLoop(FakeVibeConfig.load())
    bridge.attach_to_loop(fake_loop, runtime)

    assert bridge.inject_message("from-live")
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval("tc-1", approved=True)
    await _wait_until(lambda: len(bridge.pending_input) == 1)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")
    await _wait_until(lambda: bridge.state == "idle")

    event_types = [event["type"] for _, event in manager.events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "assistant" in event_types


@pytest.mark.asyncio
async def test_raw_event_listener_receives_unconverted_agent_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    bridge = SessionBridge("raw-events")
    raw_kinds: list[str] = []

    async def record_raw(event: object) -> None:
        raw_kinds.append(event.__class__.__name__)

    bridge.add_raw_event_listener(record_raw)
    assert bridge.inject_message("hello raw")
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval("tc-1", approved=True)
    await _wait_until(lambda: len(bridge.pending_input) == 1)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")
    await _wait_until(lambda: bridge.state == "idle")

    assert "FakeUserMessageEvent" in raw_kinds
    assert "FakeToolCallEvent" in raw_kinds
    assert "FakeToolResultEvent" in raw_kinds

    bridge.stop()


@pytest.mark.asyncio
async def test_local_callbacks_can_resolve_approval_and_input_without_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = bridge_module.VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    monkeypatch.setattr(bridge_module, "load_vibe_runtime", lambda: runtime)

    manager = RecordingConnectionManager()
    bridge = SessionBridge("local-callbacks", connection_manager=manager)
    loop = FakeAgentLoop(FakeVibeConfig.load())

    async def local_approval(_tool: str, _args: object, _call_id: str) -> tuple[str, None]:
        return (FakeApprovalResponse.YES, None)

    async def local_input(_args: object) -> str:
        return "yes"

    bridge.attach_to_loop(
        loop,
        runtime,
        approval_callback=local_approval,
        input_callback=local_input,
    )

    assert bridge.inject_message("handled locally")
    await _wait_until(lambda: bridge.state == "idle")
    assert bridge.pending_approval == {}
    assert bridge.pending_input == {}

    event_types = [event["type"] for _, event in manager.events]
    assert "approval_request" in event_types
    assert "approval_resolution" in event_types
    assert "input_request" in event_types
    assert "input_resolution" in event_types


@pytest.mark.asyncio
async def test_mobile_resolution_does_not_leave_local_pending_state_stuck() -> None:
    class CancellationSensitiveOwner:
        def __init__(self) -> None:
            self._pending_approval = None
            self._pending_question = None
            self.switch_to_input_calls = 0

        async def approval_callback(self, _tool: str, _args: object, _call_id: str):
            self._pending_approval = asyncio.get_running_loop().create_future()
            result = await self._pending_approval
            self._pending_approval = None
            return result

        async def input_callback(self, _args: object):
            self._pending_question = asyncio.get_running_loop().create_future()
            result = await self._pending_question
            self._pending_question = None
            return result

        async def _switch_to_input_app(self) -> None:
            self.switch_to_input_calls += 1

    owner = CancellationSensitiveOwner()
    manager = RecordingConnectionManager()
    bridge = SessionBridge("mobile-first", connection_manager=manager)
    loop = FakeAgentLoop(FakeVibeConfig.load())
    runtime = VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    bridge.attach_to_loop(
        loop,
        runtime,
        approval_callback=owner.approval_callback,
        input_callback=owner.input_callback,
    )

    assert bridge.inject_message("mobile first")
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    await _wait_until(lambda: owner._pending_approval is not None)
    assert bridge.resolve_approval("tc-1", approved=True)
    await _wait_until(lambda: owner._pending_approval is None)
    await _wait_until(lambda: owner.switch_to_input_calls >= 1)

    await _wait_until(lambda: len(bridge.pending_input) == 1)
    await _wait_until(lambda: owner._pending_question is not None)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")
    await _wait_until(lambda: owner._pending_question is None)
    await _wait_until(lambda: owner.switch_to_input_calls >= 2)
    await _wait_until(lambda: bridge.state == "idle")


@pytest.mark.asyncio
async def test_settle_local_state_resolves_wrapped_and_partial_callbacks() -> None:
    class Owner:
        def __init__(self) -> None:
            self._pending_approval = None
            self._pending_question = None
            self.switch_to_input_calls = 0

        async def approval_callback(self, _tool: str, _args: object, _call_id: str):
            return (FakeApprovalResponse.YES, None)

        async def input_callback(self, _args: object):
            return "yes"

        async def _switch_to_input_app(self) -> None:
            self.switch_to_input_calls += 1

    owner = Owner()
    bridge = SessionBridge("wrapped-owner")

    async def wrapped_approval(tool: str, args: object, call_id: str):
        return await owner.approval_callback(tool, args, call_id)

    def invoke_input(callback, args: object):
        return callback(args)

    wrapped_input = functools.partial(invoke_input, owner.input_callback)
    bridge.configure_local_callbacks(
        approval_callback=wrapped_approval,
        input_callback=wrapped_input,
    )

    owner._pending_approval = asyncio.get_running_loop().create_future()
    bridge._settle_local_approval_state(approved=True)
    assert owner._pending_approval.done()

    owner._pending_question = asyncio.get_running_loop().create_future()
    bridge._settle_local_input_state(response="yes")
    assert owner._pending_question.done()

    await _wait_until(lambda: owner.switch_to_input_calls >= 2)


@pytest.mark.asyncio
async def test_settle_local_state_schedules_follow_up_ui_reset() -> None:
    class Owner:
        def __init__(self) -> None:
            self._pending_approval = None
            self.switch_to_input_calls = 0

        async def approval_callback(self, _tool: str, _args: object, _call_id: str):
            return (FakeApprovalResponse.YES, None)

        async def _switch_to_input_app(self) -> None:
            self.switch_to_input_calls += 1

    owner = Owner()
    bridge = SessionBridge("follow-up-reset")
    bridge.configure_local_callbacks(approval_callback=owner.approval_callback, input_callback=None)

    owner._pending_approval = asyncio.get_running_loop().create_future()
    bridge._settle_local_approval_state(approved=True)

    await _wait_until(lambda: owner.switch_to_input_calls >= 2)


@pytest.mark.asyncio
async def test_late_local_approval_task_skips_after_mobile_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    gate = asyncio.Event()
    real_create_task = bridge_module.asyncio.create_task

    def delayed_create_task(coro, *args, **kwargs):
        code = getattr(coro, "cr_code", None)
        if code is not None and code.co_name == "_resolve_with_local_approval":
            async def delayed() -> object:
                await gate.wait()
                return await coro

            return real_create_task(delayed(), *args, **kwargs)
        return real_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(bridge_module.asyncio, "create_task", delayed_create_task)

    class Owner:
        def __init__(self) -> None:
            self._pending_approval = None
            self.calls = 0

        async def approval_callback(self, _tool: str, _args: object, _call_id: str):
            self.calls += 1
            self._pending_approval = asyncio.get_running_loop().create_future()
            result = await self._pending_approval
            self._pending_approval = None
            return result

    owner = Owner()
    bridge = SessionBridge("late-approval")
    bridge.attach_to_loop(
        FakeAgentLoop(FakeVibeConfig.load()),
        runtime,
        approval_callback=owner.approval_callback,
        input_callback=None,
    )

    assert bridge.inject_message("mobile-first approval")
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval("tc-1", approved=True)

    gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert owner.calls == 0
    assert owner._pending_approval is None

    if bridge.pending_input:
        request_id = next(iter(bridge.pending_input.keys()))
        assert bridge.resolve_input(request_id=request_id, response="yes")
    await _wait_until(lambda: bridge.state == "idle")
    bridge.stop()


@pytest.mark.asyncio
async def test_late_local_input_task_skips_after_mobile_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.bridge as bridge_module

    runtime = VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes=FakeApprovalResponse.YES,
        approval_no=FakeApprovalResponse.NO,
        ask_result_cls=FakeAskUserQuestionResult,
        answer_cls=FakeAnswer,
    )
    gate = asyncio.Event()
    real_create_task = bridge_module.asyncio.create_task

    def delayed_create_task(coro, *args, **kwargs):
        code = getattr(coro, "cr_code", None)
        if code is not None and code.co_name == "_resolve_with_local_input":
            async def delayed() -> object:
                await gate.wait()
                return await coro

            return real_create_task(delayed(), *args, **kwargs)
        return real_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(bridge_module.asyncio, "create_task", delayed_create_task)

    class Owner:
        def __init__(self) -> None:
            self._pending_question = None
            self.calls = 0

        async def input_callback(self, _args: object):
            self.calls += 1
            self._pending_question = asyncio.get_running_loop().create_future()
            result = await self._pending_question
            self._pending_question = None
            return result

    owner = Owner()
    bridge = SessionBridge("late-input")
    bridge.attach_to_loop(
        FakeAgentLoop(FakeVibeConfig.load()),
        runtime,
        approval_callback=None,
        input_callback=owner.input_callback,
    )

    assert bridge.inject_message("mobile-first input")
    await _wait_until(lambda: "tc-1" in bridge.pending_approval)
    assert bridge.resolve_approval("tc-1", approved=True)
    await _wait_until(lambda: len(bridge.pending_input) == 1)
    request_id = next(iter(bridge.pending_input.keys()))
    assert bridge.resolve_input(request_id=request_id, response="yes")

    gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert owner.calls == 0
    assert owner._pending_question is None
    await _wait_until(lambda: bridge.state == "idle")
    bridge.stop()


# ---- Stats event tests ----


class FakeStats:
    def __init__(
        self,
        session_prompt_tokens: int = 0,
        session_completion_tokens: int = 0,
        input_price_per_million: float = 0.0,
        output_price_per_million: float = 0.0,
        steps: int = 0,
    ) -> None:
        self.session_prompt_tokens = session_prompt_tokens
        self.session_completion_tokens = session_completion_tokens
        self.input_price_per_million = input_price_per_million
        self.output_price_per_million = output_price_per_million
        self.steps = steps


def test_build_stats_event_with_remote_model() -> None:
    bridge = SessionBridge("stats-remote")
    loop = type("Loop", (), {"stats": FakeStats(
        session_prompt_tokens=10000,
        session_completion_tokens=2000,
        input_price_per_million=0.40,
        output_price_per_million=2.00,
        steps=5,
    )})()
    bridge._agent_loop = loop
    event = bridge._build_stats_event()
    assert event is not None
    assert event.type == "stats"
    assert event.prompt_tokens == 10000
    assert event.completion_tokens == 2000
    assert event.total_tokens == 12000
    assert event.steps == 5
    assert event.is_local is False
    expected_cost = (10000 / 1_000_000) * 0.40 + (2000 / 1_000_000) * 2.00
    assert abs(event.session_cost - expected_cost) < 1e-9


def test_build_stats_event_local_model_is_free() -> None:
    bridge = SessionBridge("stats-local")
    loop = type("Loop", (), {"stats": FakeStats(
        session_prompt_tokens=50000,
        session_completion_tokens=10000,
        input_price_per_million=0.0,
        output_price_per_million=0.0,
        steps=10,
    )})()
    bridge._agent_loop = loop
    event = bridge._build_stats_event()
    assert event is not None
    assert event.is_local is True
    assert event.session_cost == 0.0
    assert event.total_tokens == 60000


def test_build_stats_event_no_agent_loop() -> None:
    bridge = SessionBridge("stats-none")
    assert bridge._build_stats_event() is None


def test_build_stats_event_no_stats_attr() -> None:
    bridge = SessionBridge("stats-no-attr")
    bridge._agent_loop = object()
    assert bridge._build_stats_event() is None


def test_state_payload_includes_stats_when_loop_has_stats() -> None:
    bridge = SessionBridge("stats-payload")
    loop = type("Loop", (), {"stats": FakeStats(
        session_prompt_tokens=1000,
        session_completion_tokens=500,
        input_price_per_million=0.40,
        output_price_per_million=2.00,
        steps=2,
    )})()
    bridge._agent_loop = loop
    payload = bridge.state_payload()
    assert "stats" in payload
    stats = payload["stats"]
    assert stats["type"] == "stats"
    assert stats["prompt_tokens"] == 1000
    assert stats["completion_tokens"] == 500
    assert stats["total_tokens"] == 1500
    assert stats["is_local"] is False


def test_state_payload_no_stats_without_agent_loop() -> None:
    bridge = SessionBridge("stats-no-loop")
    payload = bridge.state_payload()
    assert "stats" not in payload


@pytest.mark.asyncio
async def test_broadcast_stats_sends_event() -> None:
    cm = RecordingConnectionManager()
    bridge = SessionBridge("stats-broadcast", connection_manager=cm)
    loop = type("Loop", (), {"stats": FakeStats(
        session_prompt_tokens=100,
        session_completion_tokens=50,
        steps=1,
    )})()
    bridge._agent_loop = loop
    bridge._broadcast_stats()
    await asyncio.sleep(0)  # let background task run
    stats_events = [e for _, e in cm.events if e.get("type") == "stats"]
    assert len(stats_events) == 1
    assert stats_events[0]["total_tokens"] == 150
    assert stats_events[0]["is_local"] is True
