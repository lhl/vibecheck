from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from vibecheck.events import (
    ApprovalRequestEvent,
    AssistantEvent,
    EventAdapter,
    InputRequestEvent,
    StateChangeEvent,
    StatsEvent,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)


def test_event_round_trip_for_each_type() -> None:
    events = [
        AssistantEvent(content="hello"),
        ToolCallEvent(tool_name="bash", args={"command": "ls"}, call_id="tc-1"),
        ToolResultEvent(call_id="tc-1", output="ok"),
        ApprovalRequestEvent(call_id="tc-2", tool_name="bash", args={"command": "rm -rf /"}),
        InputRequestEvent(request_id="req-1", question="Continue?", options=["yes", "no"]),
        StateChangeEvent(state="running"),
        UserMessageEvent(content="please run tests"),
        StatsEvent(
            session_cost=0.0042,
            prompt_tokens=5000,
            completion_tokens=1000,
            total_tokens=6000,
            steps=3,
            is_local=False,
        ),
    ]

    for event in events:
        payload = event.model_dump(mode="json")
        restored = EventAdapter.validate_python(payload)
        assert restored == event


def test_discriminated_union_parsing() -> None:
    payload = {
        "type": "tool_call",
        "id": "abc12345",
        "timestamp": time.time(),
        "tool_name": "read_file",
        "args": {"path": "README.md"},
        "call_id": "tc-99",
    }
    parsed = EventAdapter.validate_python(payload)
    assert isinstance(parsed, ToolCallEvent)
    assert parsed.call_id == "tc-99"


def test_event_defaults_are_generated() -> None:
    event = AssistantEvent(content="generated defaults")
    assert len(event.id) == 8
    assert isinstance(event.timestamp, float)
    assert event.timestamp <= time.time()


def test_validation_error_for_bad_event_data() -> None:
    with pytest.raises(ValidationError):
        EventAdapter.validate_python(
            {
                "type": "tool_result",
                "id": "bad00123",
                "timestamp": time.time(),
                # missing required field: call_id
                "output": "hello",
            }
        )
