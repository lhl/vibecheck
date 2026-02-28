from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Literal

from mistralai import Mistral
from mistralai.models.sdkerror import SDKError

Urgency = Literal["low", "normal", "high"]

MINISTRAL_MODEL = "ministral-8b-latest"

_DEFAULT_TIMEOUT_S = 2.0


def get_mistral_client() -> Mistral | None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        return None
    return Mistral(api_key=api_key)


def _extract_text(value: Any) -> str:
    choices = getattr(value, "choices", None)
    if not isinstance(choices, list) or not choices:
        return ""

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            text = getattr(chunk, "text", None)
            if isinstance(text, str) and text:
                parts.append(text)
        return "".join(parts).strip()

    return ""


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    value = text.strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


async def _complete(
    *,
    messages: list[dict[str, str]],
    temperature: float,
    timeout_s: float | None = None,
) -> str:
    client = get_mistral_client()
    if client is None:
        return ""

    timeout = timeout_s if isinstance(timeout_s, (int, float)) and timeout_s > 0 else _DEFAULT_TIMEOUT_S

    try:
        result = await asyncio.wait_for(
            client.chat.complete_async(
                model=MINISTRAL_MODEL,
                messages=messages,
                temperature=temperature,
            ),
            timeout=timeout,
        )
    except (asyncio.TimeoutError, SDKError, OSError):
        return ""
    except Exception:
        return ""

    return _extract_text(result)


def _basic_tool_summary(tool_name: str, args: dict[str, Any]) -> str:
    tool = tool_name.strip() or "tool"
    if tool == "bash":
        command = str(args.get("command") or args.get("cmd") or "").strip()
        if command:
            return f"bash: {command}"
    if tool in {"write_file", "read_file"}:
        path = str(args.get("path") or args.get("file") or "").strip()
        if path:
            return f"{tool}: {path}"
    return tool


async def generate_notification_copy(tool_name: str, args: dict[str, Any]) -> str:
    """Generate short, user-friendly push copy for an approval request (<=80 chars)."""
    tool_summary = _basic_tool_summary(tool_name, args)
    system = (
        "You write short push notification bodies for a mobile app called vibecheck.\n"
        "Keep it calm and slightly playful. Never use ALL CAPS.\n"
        "Max 80 characters. Output ONLY the body text."
    )
    user = (
        "Write a notification body for a tool approval request.\n"
        f"Tool: {tool_name}\n"
        f"Args: {json.dumps(args, ensure_ascii=False)}\n"
        f"Fallback summary: {tool_summary}"
    )
    content = await _complete(messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], temperature=0.7)
    if not content:
        return _truncate(tool_summary, 80)
    return _truncate(content, 80)


async def summarize_tool_call(tool_name: str, args: dict[str, Any]) -> str:
    """Summarize a tool call as a 1-line banner (<=60 chars)."""
    tool_summary = _basic_tool_summary(tool_name, args)
    system = (
        "Summarize a coding agent tool call in one short sentence for a mobile banner.\n"
        "Be specific about the action. Max 60 characters. Output ONLY the summary string."
    )
    user = (
        f"Tool: {tool_name}\n"
        f"Args: {json.dumps(args, ensure_ascii=False)}\n"
        f"Fallback summary: {tool_summary}"
    )
    content = await _complete(messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], temperature=0.3)
    if not content:
        return _truncate(tool_summary, 60)
    return _truncate(content, 60)


def _normalize_urgency(value: str) -> Urgency | None:
    normalized = value.strip().lower()
    if normalized in {"low", "l"}:
        return "low"
    if normalized in {"normal", "medium", "med", "m"}:
        return "normal"
    if normalized in {"high", "critical", "crit", "h"}:
        return "high"
    return None


def _tool_urgency_fallback(tool_name: str, args: dict[str, Any]) -> Urgency:
    tool = tool_name.strip().lower()
    if tool in {"read_file", "list_dir", "search"}:
        return "low"

    text = json.dumps(args, ensure_ascii=False).lower()
    if tool == "bash" and any(token in text for token in ("rm -rf", " --force", "git push --force", "sudo ")):
        return "high"

    if tool in {"write_file", "search_replace", "bash"}:
        return "normal"

    return "normal"


async def classify_urgency(event: object) -> Urgency:
    """Classify urgency for a notification as low|normal|high."""
    tool_name = getattr(event, "tool_name", None)
    args = getattr(event, "args", None)
    if not isinstance(tool_name, str) or not isinstance(args, dict):
        event_type = str(getattr(event, "type", "")).strip().lower()
        if event_type in {"approval_request", "input_request"}:
            return "high"
        if event_type == "tool_result" and bool(getattr(event, "is_error", False)):
            return "normal"
        return "low"

    system = (
        "You classify coding agent tool calls for push notification urgency.\n"
        "Respond with one word ONLY: low, normal, or high."
    )
    user = f"Tool: {tool_name}\nArgs: {json.dumps(args, ensure_ascii=False)}"
    content = await _complete(messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], temperature=0.2)
    if content:
        normalized = _normalize_urgency(content)
        if normalized is not None:
            return normalized
        return "normal"

    return _tool_urgency_fallback(tool_name, args)

