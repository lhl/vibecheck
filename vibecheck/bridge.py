from __future__ import annotations

import asyncio
from dataclasses import dataclass
import inspect
from importlib import import_module
import json
import logging
from collections import deque
from pathlib import Path
import sys
import time
from typing import Any, Callable, Literal
from uuid import uuid4

from vibecheck.events import (
    ApprovalRequestEvent,
    ApprovalResolutionEvent,
    AssistantEvent,
    Event,
    InputRequestEvent,
    InputResolutionEvent,
    StateChangeEvent,
    ToolCallEvent,
    ToolResultEvent,
    UserMessageEvent,
)

BridgeState = Literal["idle", "running", "waiting_approval", "waiting_input", "disconnected"]
AttachMode = Literal["live", "replay", "observe_only", "managed"]
EventListener = Callable[[Event], object]
RawEventListener = Callable[[object], object]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VibeRuntime:
    agent_loop_cls: type
    vibe_config_cls: type
    approval_yes: object
    approval_no: object
    ask_result_cls: type | None
    answer_cls: type | None


def _import_vibe_module(module_name: str):
    try:
        return import_module(module_name)
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parent.parent
        fallback = repo_root / "reference" / "mistral-vibe"
        fallback_str = str(fallback)
        if fallback.exists() and fallback_str not in sys.path:
            sys.path.append(fallback_str)
        return import_module(module_name)


def load_vibe_runtime() -> VibeRuntime:
    try:
        agent_loop_module = _import_vibe_module("vibe.core.agent_loop")
        config_module = _import_vibe_module("vibe.core.config")
        types_module = _import_vibe_module("vibe.core.types")
        ask_module = _import_vibe_module("vibe.core.tools.builtins.ask_user_question")
    except Exception as exc:  # pragma: no cover - exercised in integration envs
        raise RuntimeError(
            "Mistral Vibe runtime is not available. Install `vibe` or provide "
            "`reference/mistral-vibe` in this workspace."
        ) from exc

    return VibeRuntime(
        agent_loop_cls=agent_loop_module.AgentLoop,
        vibe_config_cls=config_module.VibeConfig,
        approval_yes=types_module.ApprovalResponse.YES,
        approval_no=types_module.ApprovalResponse.NO,
        ask_result_cls=getattr(ask_module, "AskUserQuestionResult", None),
        answer_cls=getattr(ask_module, "Answer", None),
    )


class SessionBridge:
    def __init__(
        self,
        session_id: str,
        connection_manager=None,
        attach_mode: AttachMode = "managed",
    ) -> None:
        self.session_id = session_id
        self.state: BridgeState = "idle"
        self.attach_mode: AttachMode = attach_mode
        self.pending_approval: dict[str, asyncio.Future] = {}
        self.pending_input: dict[str, asyncio.Future] = {}
        self.pending_approval_context: dict[str, dict[str, object]] = {}
        self.pending_input_context: dict[str, dict[str, object]] = {}
        self.event_backlog: deque[Event] = deque(maxlen=50)
        self.connection_manager = connection_manager
        self.messages_to_inject: list[str] = []
        self._event_listeners: set[EventListener] = set()
        self._raw_event_listeners: set[RawEventListener] = set()

        self._background_tasks: set[asyncio.Task[object]] = set()
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()
        self._message_worker_task: asyncio.Task[None] | None = None
        self._run_lock = asyncio.Lock()
        self._agent_loop: object | None = None
        self._vibe_runtime: VibeRuntime | None = None
        self._observed_message_ids: set[str] = set()
        self._local_user_message_echoes: deque[tuple[str, float]] = deque(maxlen=20)
        self._active_injected_message: str | None = None
        self._message_observer_hooked = False
        self._local_approval_callback: Callable[[str, object, str], object] | None = None
        self._local_input_callback: Callable[[object], object] | None = None
        self._local_approval_owner: object | None = None
        self._local_input_owner: object | None = None

    @property
    def controllable(self) -> bool:
        return self.attach_mode != "observe_only"

    @property
    def local_approval_callback(self) -> Callable[[str, object, str], object] | None:
        return self._local_approval_callback

    @property
    def local_input_callback(self) -> Callable[[object], object] | None:
        return self._local_input_callback

    def add_event_listener(self, listener: EventListener) -> None:
        self._event_listeners.add(listener)

    def remove_event_listener(self, listener: EventListener) -> None:
        self._event_listeners.discard(listener)

    def add_raw_event_listener(self, listener: RawEventListener) -> None:
        self._raw_event_listeners.add(listener)

    def remove_raw_event_listener(self, listener: RawEventListener) -> None:
        self._raw_event_listeners.discard(listener)

    def configure_local_callbacks(
        self,
        *,
        approval_callback: Callable[[str, object, str], object] | None,
        input_callback: Callable[[object], object] | None,
    ) -> None:
        self._local_approval_callback = approval_callback
        self._local_input_callback = input_callback
        self._local_approval_owner = self._resolve_callback_owner(
            approval_callback,
            pending_attr="_pending_approval",
            fallback_owner=self._local_approval_owner,
        )
        self._local_input_owner = self._resolve_callback_owner(
            input_callback,
            pending_attr="_pending_question",
            fallback_owner=self._local_input_owner,
        )

    def _resolve_callback_owner(
        self,
        callback: object,
        *,
        pending_attr: str,
        fallback_owner: object | None,
    ) -> object | None:
        if not callable(callback):
            return None

        visited: set[int] = set()
        to_visit: list[object] = [callback]
        while to_visit:
            current = to_visit.pop()
            current_id = id(current)
            if current_id in visited:
                continue
            visited.add(current_id)

            owner = getattr(current, "__self__", None)
            if owner is not None and hasattr(owner, pending_attr):
                return owner

            if hasattr(current, pending_attr):
                return current

            for attr_name in ("__wrapped__", "__func__", "func"):
                nested = getattr(current, attr_name, None)
                if nested is not None and nested is not current:
                    to_visit.append(nested)

            partial_args = getattr(current, "args", None)
            if isinstance(partial_args, tuple):
                to_visit.extend(item for item in partial_args if item is not current)

            partial_keywords = getattr(current, "keywords", None)
            if isinstance(partial_keywords, dict):
                to_visit.extend(
                    item for item in partial_keywords.values() if item is not current
                )

            closure = getattr(current, "__closure__", None)
            if isinstance(closure, tuple):
                for cell in closure:
                    try:
                        value = cell.cell_contents
                    except ValueError:
                        continue
                    if value is current:
                        continue
                    if hasattr(value, pending_attr):
                        return value
                    if callable(value):
                        to_visit.append(value)

        return fallback_owner

    def _local_owner_for_settle(
        self,
        callback: object,
        *,
        pending_attr: str,
        owner_hint: object | None,
        callback_label: str,
    ) -> object | None:
        owner = self._resolve_callback_owner(
            callback,
            pending_attr=pending_attr,
            fallback_owner=owner_hint,
        )
        if owner is None and callable(callback):
            logger.warning(
                "Failed to resolve local %s callback owner for session %s; "
                "mobile settlement cannot complete local pending state",
                callback_label,
                self.session_id,
            )
        return owner

    async def _notify_event_listeners(self, event: Event) -> None:
        for listener in list(self._event_listeners):
            try:
                result = listener(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Bridge event listener failed for session %s", self.session_id)

    def _notify_event_listeners_background(self, event: Event) -> None:
        if not self._event_listeners:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            for listener in list(self._event_listeners):
                try:
                    result = listener(event)
                    if inspect.isawaitable(result):
                        continue
                except Exception:
                    logger.exception(
                        "Bridge event listener failed outside running loop for session %s",
                        self.session_id,
                    )
            return

        task = loop.create_task(self._notify_event_listeners(event))
        self._track_task(task)

    async def _notify_raw_event_listeners(self, event: object) -> None:
        for listener in list(self._raw_event_listeners):
            try:
                result = listener(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Bridge raw event listener failed for session %s", self.session_id)

    async def _broadcast(self, event: Event) -> None:
        self.add_event(event)
        await self._notify_event_listeners(event)
        if self.connection_manager:
            await self.connection_manager.broadcast(self.session_id, event)

    def _track_task(self, task: asyncio.Task[object]) -> None:
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _broadcast_background(self, event: Event) -> None:
        self.add_event(event)
        self._notify_event_listeners_background(event)
        if not self.connection_manager:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self.connection_manager.broadcast(self.session_id, event))
        self._track_task(task)

    def add_event(self, event: Event) -> None:
        self.event_backlog.append(event)

    def backlog(self, limit: int = 50) -> list[Event]:
        return list(self.event_backlog)[-limit:]

    def _set_state(self, state: BridgeState) -> None:
        if self.state == state:
            return
        self.state = state
        self._broadcast_background(
            StateChangeEvent(
                state=state,
                attach_mode=self.attach_mode,
                controllable=self.controllable,
            )
        )

    async def request_approval(
        self,
        call_id: str,
        tool_name: str,
        args: dict,
        *,
        local_args: object | None = None,
    ) -> dict:
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending_approval[call_id] = future
        self.pending_approval_context[call_id] = {"tool_name": tool_name, "args": args}
        if self._local_approval_callback is not None:
            self._track_task(
                asyncio.create_task(
                    self._resolve_with_local_approval(
                        tool_name=tool_name,
                        args=local_args if local_args is not None else args,
                        tool_call_id=call_id,
                    )
                )
            )
        self._set_state("waiting_approval")
        await self._broadcast(ApprovalRequestEvent(call_id=call_id, tool_name=tool_name, args=args))
        result = await future
        return result

    def resolve_approval(self, call_id: str, approved: bool, edited_args: dict | None = None) -> bool:
        future = self.pending_approval.pop(call_id, None)
        self.pending_approval_context.pop(call_id, None)
        if future is None:
            return False
        if not future.done():
            future.set_result({"approved": approved, "edited_args": edited_args})
        self._settle_local_approval_state(approved=approved, edited_args=edited_args)
        self._set_state("running")
        self._broadcast_background(
            ApprovalResolutionEvent(call_id=call_id, approved=approved, edited_args=edited_args)
        )
        return True

    async def request_input(
        self,
        request_id: str,
        question: str,
        options: list[str] | None = None,
        *,
        local_args: object | None = None,
    ) -> str:
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending_input[request_id] = future
        self.pending_input_context[request_id] = {
            "question": question,
            "options": list(options or []),
        }
        if self._local_input_callback is not None:
            self._track_task(
                asyncio.create_task(
                    self._resolve_with_local_input(
                        local_args if local_args is not None else dict(self.pending_input_context[request_id]),
                        request_id,
                    )
                )
            )
        self._set_state("waiting_input")
        await self._broadcast(
            InputRequestEvent(request_id=request_id, question=question, options=options or [])
        )
        result = await future
        return result

    def resolve_input(self, request_id: str, response: str) -> bool:
        future = self.pending_input.pop(request_id, None)
        self.pending_input_context.pop(request_id, None)
        if future is None:
            return False
        if not future.done():
            future.set_result(response)
        self._settle_local_input_state(response=response)
        self._set_state("running")
        self._broadcast_background(InputResolutionEvent(request_id=request_id, response=response))
        return True

    def _message_to_dict(self, value: object) -> dict:
        if hasattr(value, "model_dump"):
            return dict(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return dict(value)
        return {"value": str(value)}

    def _extract_input_question(self, args: object) -> tuple[str, list[str], list[str]]:
        default_question = "Input requested"
        options: list[str] = []
        all_questions: list[str] = []

        questions = getattr(args, "questions", None)
        if not isinstance(questions, list) or not questions:
            return default_question, options, all_questions

        first = questions[0]
        if isinstance(getattr(first, "question", None), str):
            default_question = first.question

        for item in questions:
            text = getattr(item, "question", None)
            if isinstance(text, str) and text:
                all_questions.append(text)

        raw_options = getattr(first, "options", None)
        if isinstance(raw_options, list):
            for option in raw_options:
                label = getattr(option, "label", None)
                options.append(str(label) if label is not None else str(option))

        return default_question, options, all_questions

    def _build_input_result(self, answer_text: str, question_texts: list[str]) -> object:
        runtime = self._vibe_runtime
        if runtime is None or runtime.ask_result_cls is None or runtime.answer_cls is None:
            return {"response": answer_text}

        prompts = question_texts or ["Input requested"]
        answers = [
            runtime.answer_cls(question=prompt, answer=answer_text, is_other=False)
            for prompt in prompts
        ]
        return runtime.ask_result_cls(answers=answers, cancelled=False)

    def _apply_edited_args(self, args: object, edited_args: dict[str, object]) -> bool:
        if not edited_args:
            return True

        # Prefer full schema re-validation for Pydantic argument models.
        validator = getattr(args.__class__, "model_validate", None)
        dump = getattr(args, "model_dump", None)
        if callable(validator) and callable(dump):
            try:
                current = dump(mode="python")
                if isinstance(current, dict):
                    merged = {**current, **edited_args}
                    validated = validator(merged)
                    updated = validated.model_dump(mode="python")
                    if isinstance(updated, dict):
                        for key, value in updated.items():
                            if hasattr(args, key):
                                setattr(args, key, value)
                        return True
            except Exception:
                return False
            return False

        # Best effort for plain python argument holders used in tests/mocks.
        existing: dict[str, object] = {}
        for key in edited_args:
            if not hasattr(args, key):
                continue
            existing[key] = getattr(args, key)

        try:
            for key, value in edited_args.items():
                if key in existing:
                    setattr(args, key, value)
        except Exception:
            for key, value in existing.items():
                try:
                    setattr(args, key, value)
                except Exception:
                    pass
            return False

        return bool(existing)

    async def _approval_callback(
        self, tool_name: str, args: object, tool_call_id: str
    ) -> tuple[object, str | None]:
        approval = await self.request_approval(
            call_id=tool_call_id,
            tool_name=tool_name,
            args=self._message_to_dict(args),
            local_args=args,
        )

        runtime = self._vibe_runtime
        yes = runtime.approval_yes if runtime else "y"
        no = runtime.approval_no if runtime else "n"

        edited_args = approval.get("edited_args")
        if approval.get("approved") and isinstance(edited_args, dict):
            if not self._apply_edited_args(args, edited_args):
                return (no, "edited_args failed validation")

        feedback = None
        if edited_args is not None:
            feedback = json.dumps(edited_args, ensure_ascii=True)
        return (yes if approval.get("approved") else no, feedback)

    async def _user_input_callback(self, args: object) -> object:
        question, options, prompts = self._extract_input_question(args)
        request_id = f"req-{uuid4().hex[:8]}"

        response = await self.request_input(
            request_id=request_id,
            question=question,
            options=options,
            local_args=args,
        )

        return self._build_input_result(response, prompts)

    async def _resolve_with_local_approval(
        self,
        tool_name: str,
        args: object,
        tool_call_id: str,
    ) -> None:
        if tool_call_id not in self.pending_approval:
            return

        callback = self._local_approval_callback
        if callback is None:
            return

        try:
            result = callback(tool_name, args, tool_call_id)
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, tuple) or not result:
                return
            verdict = result[0]

            runtime = self._vibe_runtime
            yes = runtime.approval_yes if runtime else "y"
            approved = verdict == yes
            self.resolve_approval(tool_call_id, approved=approved)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Local approval callback failed for session %s", self.session_id)

    async def _resolve_with_local_input(self, args: object, request_id: str) -> None:
        if request_id not in self.pending_input:
            return

        callback = self._local_input_callback
        if callback is None:
            return

        try:
            result = callback(args)
            if inspect.isawaitable(result):
                result = await result
            response = self._extract_local_input_response(result)
            self.resolve_input(request_id=request_id, response=response)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Local input callback failed for session %s", self.session_id)

    def _extract_local_input_response(self, result: object) -> str:
        if isinstance(result, str):
            return result

        answers = getattr(result, "answers", None)
        if isinstance(answers, list) and answers:
            answer_text = getattr(answers[0], "answer", None)
            if isinstance(answer_text, str):
                return answer_text

        return ""

    def _call_switch_to_input_app(self, owner: object) -> None:
        switch_to_input = getattr(owner, "_switch_to_input_app", None)
        if not callable(switch_to_input):
            return

        try:
            maybe_awaitable = switch_to_input()
        except Exception:
            logger.exception(
                "Failed to switch local UI back to input app for session %s",
                self.session_id,
            )
            return

        if not inspect.isawaitable(maybe_awaitable):
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            close = getattr(maybe_awaitable, "close", None)
            if callable(close):
                close()
            return

        task = loop.create_task(maybe_awaitable)
        self._track_task(task)

    def _reset_local_owner_ui(self, owner: object) -> None:
        self._call_switch_to_input_app(owner)

        async def follow_up_reset() -> None:
            await asyncio.sleep(0)
            self._call_switch_to_input_app(owner)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        task = loop.create_task(follow_up_reset())
        self._track_task(task)

    def _settle_local_approval_state(self, approved: bool, edited_args: dict | None = None) -> None:
        callback = self._local_approval_callback
        owner = self._local_owner_for_settle(
            callback,
            pending_attr="_pending_approval",
            owner_hint=self._local_approval_owner,
            callback_label="approval",
        )
        if owner is not None:
            self._local_approval_owner = owner
        pending = getattr(owner, "_pending_approval", None)
        if not isinstance(pending, asyncio.Future) or pending.done():
            return

        runtime = self._vibe_runtime
        yes = runtime.approval_yes if runtime else "y"
        no = runtime.approval_no if runtime else "n"
        feedback: str | None = None
        if edited_args is not None:
            feedback = json.dumps(edited_args, ensure_ascii=True)
        pending.set_result((yes if approved else no, feedback))
        self._reset_local_owner_ui(owner)

    def _settle_local_input_state(self, response: str) -> None:
        callback = self._local_input_callback
        owner = self._local_owner_for_settle(
            callback,
            pending_attr="_pending_question",
            owner_hint=self._local_input_owner,
            callback_label="input",
        )
        if owner is not None:
            self._local_input_owner = owner
        pending = getattr(owner, "_pending_question", None)
        if not isinstance(pending, asyncio.Future) or pending.done():
            return

        pending.set_result(self._build_input_result(response, question_texts=[]))
        self._reset_local_owner_ui(owner)

    def _on_message_observed(self, message: object) -> None:
        message_id = getattr(message, "message_id", None)
        if isinstance(message_id, str):
            if message_id in self._observed_message_ids:
                return
            self._observed_message_ids.add(message_id)

        role = getattr(message, "role", None)
        role_value = getattr(role, "value", role)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content:
            return

        if role_value == "assistant":
            self._broadcast_background(AssistantEvent(content=content))
        elif role_value == "user":
            if self._consume_local_user_message_echo(content):
                return
            self._broadcast_background(UserMessageEvent(content=content))

    def _convert_vibe_event(self, raw_event: object) -> Event | None:
        kind = raw_event.__class__.__name__

        if kind.endswith("UserMessageEvent"):
            if self._message_observer_hooked:
                return None
            message_id = getattr(raw_event, "message_id", None)
            if isinstance(message_id, str):
                if message_id in self._observed_message_ids:
                    return None
                self._observed_message_ids.add(message_id)
            content = getattr(raw_event, "content", "")
            if self._consume_local_user_message_echo(str(content)):
                return None
            return UserMessageEvent(content=str(content))

        if kind.endswith("AssistantEvent"):
            stopped_by_middleware = bool(getattr(raw_event, "stopped_by_middleware", False))
            if self._message_observer_hooked and not stopped_by_middleware:
                return None
            message_id = getattr(raw_event, "message_id", None)
            if isinstance(message_id, str):
                if message_id in self._observed_message_ids:
                    return None
                self._observed_message_ids.add(message_id)
            content = getattr(raw_event, "content", "")
            return AssistantEvent(content=str(content))

        if kind.endswith("ToolCallEvent"):
            return ToolCallEvent(
                tool_name=str(getattr(raw_event, "tool_name", "tool")),
                args=self._message_to_dict(getattr(raw_event, "args", {})),
                call_id=str(getattr(raw_event, "tool_call_id", "")),
            )

        if kind.endswith("ToolResultEvent"):
            call_id = str(getattr(raw_event, "tool_call_id", ""))
            error = getattr(raw_event, "error", None)
            if isinstance(error, str) and error:
                return ToolResultEvent(call_id=call_id, output=error, is_error=True)

            result = getattr(raw_event, "result", None)
            if hasattr(result, "model_dump"):
                output = json.dumps(result.model_dump(mode="json"), ensure_ascii=True)
            elif result is None:
                output = ""
            else:
                output = str(result)
            return ToolResultEvent(call_id=call_id, output=output, is_error=False)

        return None

    def _wire_callbacks(self, agent_loop: object) -> None:
        if hasattr(agent_loop, "set_approval_callback"):
            agent_loop.set_approval_callback(self._approval_callback)
        if hasattr(agent_loop, "set_user_input_callback"):
            agent_loop.set_user_input_callback(self._user_input_callback)

    @staticmethod
    def _callbacks_match(candidate: object, target: object) -> bool:
        if candidate is target:
            return True
        candidate_func = getattr(candidate, "__func__", None)
        target_func = getattr(target, "__func__", None)
        candidate_self = getattr(candidate, "__self__", None)
        target_self = getattr(target, "__self__", None)
        return (
            candidate_func is not None
            and target_func is not None
            and candidate_func is target_func
            and candidate_self is target_self
        )

    def _wire_message_observer(self, agent_loop: object) -> None:
        if self._message_observer_hooked:
            return

        existing = getattr(agent_loop, "message_observer", None)
        existing_message_list_observer = None
        message_list = getattr(agent_loop, "messages", None)
        if message_list is not None:
            existing_message_list_observer = getattr(message_list, "_observer", None)

        def chained(message: object) -> None:
            self._on_message_observed(message)
            if callable(existing) and not self._callbacks_match(existing, self._on_message_observed):
                existing(message)
            if (
                callable(existing_message_list_observer)
                and not self._callbacks_match(existing_message_list_observer, self._on_message_observed)
                and not self._callbacks_match(existing_message_list_observer, existing)
            ):
                existing_message_list_observer(message)

        try:
            setattr(agent_loop, "message_observer", chained)
            if message_list is not None and hasattr(message_list, "_observer"):
                setattr(message_list, "_observer", chained)
            self._message_observer_hooked = True
        except Exception:
            self._message_observer_hooked = False

    def attach_to_loop(
        self,
        agent_loop: object,
        vibe_runtime: VibeRuntime | None = None,
        *,
        approval_callback: Callable[[str, object, str], object] | None = None,
        input_callback: Callable[[object], object] | None = None,
    ) -> None:
        self._agent_loop = agent_loop
        self._message_observer_hooked = False
        if vibe_runtime is not None:
            self._vibe_runtime = vibe_runtime
        self.configure_local_callbacks(
            approval_callback=approval_callback,
            input_callback=input_callback,
        )
        self.attach_mode = "live"
        self._wire_callbacks(agent_loop)
        self._wire_message_observer(agent_loop)

    def _ensure_agent_loop(self) -> None:
        if self._agent_loop is not None:
            return

        runtime = load_vibe_runtime()
        config = runtime.vibe_config_cls.load()
        try:
            agent_loop = runtime.agent_loop_cls(
                config,
                message_observer=self._on_message_observed,
                enable_streaming=False,
            )
        except TypeError:
            agent_loop = runtime.agent_loop_cls(
                config,
                message_observer=self._on_message_observed,
            )

        self.attach_mode = "managed"
        self.configure_local_callbacks(approval_callback=None, input_callback=None)
        self._message_observer_hooked = False
        self._wire_callbacks(agent_loop)
        self._wire_message_observer(agent_loop)
        self._agent_loop = agent_loop
        self._vibe_runtime = runtime

    async def _run_agent_turn(self, content: str) -> None:
        if self._agent_loop is None:
            return

        self._set_state("running")
        async with self._run_lock:
            cleaned = content.strip()
            self._active_injected_message = cleaned if cleaned else None
            try:
                async for raw_event in self._agent_loop.act(content):
                    await self._notify_raw_event_listeners(raw_event)
                    event = self._convert_vibe_event(raw_event)
                    if event is not None:
                        await self._broadcast(event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - integration behavior
                await self._broadcast(
                    AssistantEvent(content=f"Bridge failed to process agent event: {exc}")
                )
            finally:
                self._active_injected_message = None

    async def _message_worker(self) -> None:
        while True:
            content = await self._message_queue.get()
            try:
                await self._run_agent_turn(content)
            finally:
                self._message_queue.task_done()
                if (
                    self.state == "running"
                    and not self.pending_approval
                    and not self.pending_input
                    and self._message_queue.empty()
                ):
                    self._set_state("idle")

    def _ensure_message_worker(self) -> None:
        if self._message_worker_task is not None and not self._message_worker_task.done():
            return
        loop = asyncio.get_running_loop()
        task: asyncio.Task[None] = loop.create_task(self._message_worker())
        self._message_worker_task = task
        self._track_task(task)

    def prime_message_worker(self) -> None:
        """Start the message worker in the current task context if possible."""
        try:
            self._ensure_message_worker()
        except RuntimeError:
            # Safe no-op when called without an active event loop.
            return

    async def start_session(self, message: str, working_dir: Path | None = None) -> None:
        _ = working_dir
        self._ensure_agent_loop()
        self._message_queue.put_nowait(message)
        self._ensure_message_worker()
        await self._message_queue.join()

    def _broadcast_local_user_message(self, content: str) -> None:
        cleaned = content.strip()
        if not cleaned:
            return
        self._local_user_message_echoes.append((cleaned, time.monotonic()))
        self._broadcast_background(UserMessageEvent(content=cleaned))

    def _consume_local_user_message_echo(self, content: str, *, window_s: float = 10.0) -> bool:
        cleaned = content.strip()
        if not cleaned:
            return False

        active = self._active_injected_message
        if not active or cleaned != active:
            return False

        now = time.monotonic()
        while self._local_user_message_echoes and now - self._local_user_message_echoes[0][1] > window_s:
            self._local_user_message_echoes.popleft()

        for entry in list(self._local_user_message_echoes):
            if entry[0] != cleaned:
                continue
            try:
                self._local_user_message_echoes.remove(entry)
            except ValueError:
                pass
            return True

        return False

    def inject_message(self, content: str) -> bool:
        self.messages_to_inject.append(content)
        if not self.controllable:
            self._set_state("idle")
            return False

        if self._agent_loop is None:
            try:
                self._ensure_agent_loop()
            except RuntimeError:
                self._broadcast_local_user_message(content)
                self._set_state("idle")
                return False

        self._set_state("running")
        self._broadcast_local_user_message(content)
        self._message_queue.put_nowait(content)
        try:
            self._ensure_message_worker()
        except RuntimeError:
            # If no running loop is available, keep the message queued for the next
            # async context and still reflect the message in UI immediately.
            self._set_state("idle")
            return False
        return True

    def stop(self) -> None:
        if self._message_worker_task and not self._message_worker_task.done():
            self._message_worker_task.cancel()
        self._message_worker_task = None

        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()

        self.pending_approval.clear()
        self.pending_input.clear()
        self.pending_approval_context.clear()
        self.pending_input_context.clear()
        self._set_state("disconnected")

    def state_payload(self) -> dict:
        payload: dict[str, object] = {
            "state": self.state,
            "attach_mode": self.attach_mode,
            "controllable": self.controllable,
        }
        if self.pending_approval:
            call_id = next(iter(self.pending_approval.keys()))
            context = self.pending_approval_context.get(call_id, {})
            pending = {"call_id": call_id}
            if "tool_name" in context:
                pending["tool_name"] = context["tool_name"]
            if "args" in context:
                pending["args"] = context["args"]
            payload["pending_approval"] = pending
        if self.pending_input:
            request_id = next(iter(self.pending_input.keys()))
            context = self.pending_input_context.get(request_id, {})
            pending = {"request_id": request_id}
            if "question" in context:
                pending["question"] = context["question"]
            if "options" in context:
                pending["options"] = context["options"]
            payload["pending_input"] = pending
        return payload


class SessionManager:
    def __init__(self, logs_root: Path | None = None, connection_manager=None) -> None:
        self.logs_root = logs_root or (Path.home() / ".vibe" / "logs" / "session")
        self.connection_manager = connection_manager
        self.sessions: dict[str, SessionBridge] = {}
        self._bridge_hooks: set[Callable[[SessionBridge], None]] = set()

    def add_bridge_hook(self, hook: Callable[[SessionBridge], None]) -> None:
        self._bridge_hooks.add(hook)
        for bridge in self.sessions.values():
            try:
                hook(bridge)
            except Exception:
                logger.exception("Bridge hook failed for session %s", bridge.session_id)

    def set_connection_manager(self, connection_manager) -> None:
        self.connection_manager = connection_manager
        for bridge in self.sessions.values():
            bridge.connection_manager = connection_manager

    def discover(self) -> list[dict]:
        discovered: list[dict] = []
        if not self.logs_root.exists():
            return discovered

        for session_dir in sorted(self.logs_root.iterdir()):
            if not session_dir.is_dir():
                continue
            meta_file = session_dir / "meta.json"
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            session_id = meta.get("session_id") or session_dir.name
            discovered.append(
                {
                    "id": session_id,
                    "started_at": meta.get("start_time"),
                    "last_activity": meta.get("end_time") or meta.get("start_time"),
                    "message_count": self._message_count(session_dir),
                    "status": self.sessions.get(session_id).state if session_id in self.sessions else "disconnected",
                    "attach_mode": (
                        self.sessions[session_id].attach_mode
                        if session_id in self.sessions
                        else "observe_only"
                    ),
                    "controllable": (
                        self.sessions[session_id].controllable
                        if session_id in self.sessions
                        else False
                    ),
                }
            )
        return discovered

    def _message_count(self, session_dir: Path) -> int:
        messages_file = session_dir / "messages.jsonl"
        if not messages_file.exists():
            return 0
        return sum(1 for _ in messages_file.open("r", encoding="utf-8"))

    def attach(
        self,
        session_id: str,
        attach_mode: AttachMode | None = None,
    ) -> SessionBridge:
        if session_id in self.sessions:
            bridge = self.sessions[session_id]
            if attach_mode is not None:
                bridge.attach_mode = attach_mode
            return bridge

        mode = attach_mode
        if mode is None:
            mode = "observe_only" if any(item["id"] == session_id for item in self.discover()) else "managed"

        bridge = SessionBridge(
            session_id=session_id,
            connection_manager=self.connection_manager,
            attach_mode=mode,
        )
        for hook in list(self._bridge_hooks):
            try:
                hook(bridge)
            except Exception:
                logger.exception("Bridge hook failed for session %s", session_id)
        self.sessions[session_id] = bridge
        return bridge

    def detach(self, session_id: str) -> None:
        bridge = self.sessions.pop(session_id, None)
        if bridge is not None:
            bridge.stop()

    async def start_session(
        self,
        session_id: str,
        message: str,
        working_dir: Path | None = None,
    ) -> SessionBridge:
        bridge = self.attach(session_id, attach_mode="managed")
        await bridge.start_session(message=message, working_dir=working_dir)
        return bridge

    def get(self, session_id: str) -> SessionBridge:
        bridge = self.sessions.get(session_id)
        if bridge is None:
            raise KeyError(session_id)
        return bridge

    def has_known_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            return True
        return any(item["id"] == session_id for item in self.discover())

    def list(self) -> list[dict]:
        discovered = {item["id"]: item for item in self.discover()}
        for session_id, bridge in self.sessions.items():
            if session_id not in discovered:
                discovered[session_id] = {
                    "id": session_id,
                    "started_at": None,
                    "last_activity": None,
                    "message_count": len(bridge.event_backlog),
                    "status": bridge.state,
                    "attach_mode": bridge.attach_mode,
                    "controllable": bridge.controllable,
                }
            else:
                discovered[session_id]["status"] = bridge.state
                discovered[session_id]["attach_mode"] = bridge.attach_mode
                discovered[session_id]["controllable"] = bridge.controllable
        return list(discovered.values())

    def fleet_status(self) -> dict[str, int]:
        listed = self.list()
        running = 0
        waiting = 0
        idle = 0
        for item in listed:
            status = item["status"]
            if status == "running":
                running += 1
            elif status in {"waiting_approval", "waiting_input"}:
                waiting += 1
            elif status == "idle":
                idle += 1
        return {"total": len(listed), "running": running, "waiting": waiting, "idle": idle}

    def session_detail(self, session_id: str) -> dict:
        bridge = self.sessions.get(session_id)
        if bridge is not None:
            return {
                "id": bridge.session_id,
                "state": bridge.state,
                "attach_mode": bridge.attach_mode,
                "controllable": bridge.controllable,
                "pending_approval": list(bridge.pending_approval.keys()),
                "pending_input": list(bridge.pending_input.keys()),
                "backlog": [event.model_dump(mode="json") for event in bridge.backlog()],
            }

        discovered = next((item for item in self.discover() if item["id"] == session_id), None)
        if discovered is None:
            raise KeyError(session_id)

        return {
            "id": session_id,
            "state": "disconnected",
            "attach_mode": "observe_only",
            "controllable": False,
            "pending_approval": [],
            "pending_input": [],
            "backlog": [],
            "started_at": discovered["started_at"],
            "last_activity": discovered["last_activity"],
            "message_count": discovered["message_count"],
        }


session_manager = SessionManager()
