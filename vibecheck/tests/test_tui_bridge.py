from __future__ import annotations

import asyncio

import pytest

from vibecheck.bridge import SessionBridge
from vibecheck.events import AssistantEvent
from vibecheck.tui_bridge import TuiBridge


class RecordingConnectionManager:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def broadcast(self, session_id: str, event) -> None:
        payload = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
        self.events.append((session_id, payload))


class RecordingEventHandler:
    def __init__(self) -> None:
        self.events: list[tuple[object, dict]] = []

    async def handle_event(self, event, **kwargs) -> None:
        self.events.append((event, kwargs))


async def _wait_until(predicate, *, attempts: int = 100) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition was not met in time")


@pytest.mark.asyncio
async def test_tui_bridge_forwards_event_to_textual_handler() -> None:
    handler = RecordingEventHandler()
    bridge = TuiBridge(handler)

    await bridge.on_bridge_event(AssistantEvent(content="hello"))

    assert len(handler.events) == 1
    event, kwargs = handler.events[0]
    assert event.type == "assistant"
    assert event.content == "hello"
    assert kwargs["loading_active"] is False


@pytest.mark.asyncio
async def test_tui_bridge_forwards_raw_event_to_textual_handler() -> None:
    class RawEvent:
        type = "raw_event"

    handler = RecordingEventHandler()
    bridge = TuiBridge(handler)

    await bridge.on_bridge_raw_event(RawEvent())

    assert len(handler.events) == 1
    event, _kwargs = handler.events[0]
    assert event.type == "raw_event"


@pytest.mark.asyncio
async def test_session_bridge_tees_events_to_websocket_and_tui() -> None:
    manager = RecordingConnectionManager()
    session_bridge = SessionBridge("s1", connection_manager=manager)

    handler = RecordingEventHandler()
    tui_bridge = TuiBridge(handler)
    session_bridge.add_event_listener(tui_bridge.on_bridge_event)

    task = asyncio.create_task(
        session_bridge.request_approval("tc-1", "bash", {"command": "npm test"})
    )
    await _wait_until(lambda: bool(handler.events))

    ws_events = [event["type"] for _, event in manager.events]
    tui_events = [event.type for event, _ in handler.events]

    assert "approval_request" in ws_events
    assert "approval_request" in tui_events

    assert session_bridge.resolve_approval("tc-1", approved=True)
    await task


@pytest.mark.asyncio
async def test_tui_bridge_receives_waiting_approval_state_change() -> None:
    session_bridge = SessionBridge("s2")
    handler = RecordingEventHandler()
    session_bridge.add_event_listener(TuiBridge(handler).on_bridge_event)

    task = asyncio.create_task(
        session_bridge.request_approval("tc-2", "bash", {"command": "ls"})
    )

    await _wait_until(
        lambda: any(
            event.type == "state" and getattr(event, "state", "") == "waiting_approval"
            for event, _ in handler.events
        )
    )

    assert session_bridge.resolve_approval("tc-2", approved=False)
    await task


@pytest.mark.asyncio
async def test_tui_bridge_mounts_remote_user_message_after_dispatch() -> None:
    class UserMessageEvent:
        def __init__(self, content: str) -> None:
            self.content = content
            self.message_id = "m1"

    calls: list[str] = []

    class Handler:
        async def handle_event(self, _event, **_kwargs) -> None:
            calls.append("dispatch")

    async def mount_user_message(content: str) -> None:
        calls.append(f"mount:{content}")

    bridge = TuiBridge(Handler(), mount_user_message=mount_user_message)

    await bridge.on_bridge_raw_event(UserMessageEvent("hello"))

    assert calls == ["dispatch", "mount:hello"]


@pytest.mark.asyncio
async def test_tui_bridge_skips_mount_for_locally_marked_user_message() -> None:
    class UserMessageEvent:
        def __init__(self, content: str) -> None:
            self.content = content
            self.message_id = "m1"

    mounted: list[str] = []

    async def mount_user_message(content: str) -> None:
        mounted.append(content)

    handler = RecordingEventHandler()
    bridge = TuiBridge(handler, mount_user_message=mount_user_message)
    bridge.mark_local_user_message("hello")

    await bridge.on_bridge_raw_event(UserMessageEvent("hello"))

    assert mounted == []


@pytest.mark.asyncio
async def test_tui_bridge_user_message_is_noop_when_mount_callback_missing() -> None:
    class UserMessageEvent:
        def __init__(self, content: str) -> None:
            self.content = content
            self.message_id = "m1"

    handler = RecordingEventHandler()
    bridge = TuiBridge(handler)

    await bridge.on_bridge_raw_event(UserMessageEvent("hello"))

    assert len(handler.events) == 1


@pytest.mark.asyncio
async def test_tui_bridge_local_prompt_marks_are_fifo_one_shot() -> None:
    class UserMessageEvent:
        def __init__(self, content: str) -> None:
            self.content = content
            self.message_id = "m1"

    mounted: list[str] = []

    async def mount_user_message(content: str) -> None:
        mounted.append(content)

    handler = RecordingEventHandler()
    bridge = TuiBridge(handler, mount_user_message=mount_user_message)

    bridge.mark_local_user_message("hello")
    bridge.mark_local_user_message("hello")

    await bridge.on_bridge_raw_event(UserMessageEvent("hello"))
    await bridge.on_bridge_raw_event(UserMessageEvent("hello"))
    await bridge.on_bridge_raw_event(UserMessageEvent("hello"))

    assert mounted == ["hello"]
