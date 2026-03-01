from __future__ import annotations

import time
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter


def _event_id() -> str:
    return uuid4().hex[:8]


class EventBase(BaseModel):
    type: str
    id: str = Field(default_factory=_event_id)
    timestamp: float = Field(default_factory=time.time)


class AssistantEvent(EventBase):
    type: Literal["assistant"] = "assistant"
    content: str


class ToolCallEvent(EventBase):
    type: Literal["tool_call"] = "tool_call"
    tool_name: str
    args: dict
    call_id: str


class ToolResultEvent(EventBase):
    type: Literal["tool_result"] = "tool_result"
    call_id: str
    output: str
    is_error: bool = False


class ApprovalRequestEvent(EventBase):
    type: Literal["approval_request"] = "approval_request"
    call_id: str
    tool_name: str
    args: dict


class ApprovalResolutionEvent(EventBase):
    type: Literal["approval_resolution"] = "approval_resolution"
    call_id: str
    approved: bool
    edited_args: dict | None = None
    source: str | None = None


class InputRequestEvent(EventBase):
    type: Literal["input_request"] = "input_request"
    request_id: str
    question: str
    options: list[str] = Field(default_factory=list)


class InputResolutionEvent(EventBase):
    type: Literal["input_resolution"] = "input_resolution"
    request_id: str
    response: str


class StateChangeEvent(EventBase):
    type: Literal["state"] = "state"
    state: Literal["idle", "running", "waiting_approval", "waiting_input", "disconnected"]
    attach_mode: Literal["live", "replay", "observe_only", "managed"] | None = None
    controllable: bool | None = None


class UserMessageEvent(EventBase):
    type: Literal["user_message"] = "user_message"
    content: str


class ConnectedEvent(EventBase):
    type: Literal["connected"] = "connected"
    session_id: str


class HeartbeatEvent(EventBase):
    type: Literal["heartbeat"] = "heartbeat"


Event = Annotated[
    AssistantEvent
    | ToolCallEvent
    | ToolResultEvent
    | ApprovalRequestEvent
    | ApprovalResolutionEvent
    | InputRequestEvent
    | InputResolutionEvent
    | StateChangeEvent
    | UserMessageEvent
    | ConnectedEvent
    | HeartbeatEvent,
    Field(discriminator="type"),
]

EventAdapter = TypeAdapter(Event)
