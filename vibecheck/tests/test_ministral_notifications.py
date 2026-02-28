from __future__ import annotations

from typing import Any

import pytest

from vibecheck.events import ApprovalRequestEvent


class _DummyAssistantMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _DummyChoice:
    def __init__(self, content: str) -> None:
        self.message = _DummyAssistantMessage(content)


class _DummyChatResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_DummyChoice(content)]


class _DummyChat:
    def __init__(self, content: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self._content = content

    async def complete_async(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _DummyChatResponse(self._content)


class _DummyMistralClient:
    def __init__(self, content: str) -> None:
        self.chat = _DummyChat(content)


@pytest.mark.asyncio
async def test_generate_notification_copy_uses_ministral_and_trims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.notifications.ministral as ministral_module

    dummy = _DummyMistralClient("x" * 200)
    monkeypatch.setattr(ministral_module, "get_mistral_client", lambda: dummy)

    text = await ministral_module.generate_notification_copy("bash", {"command": "npm test -- --coverage"})
    assert text
    assert len(text) <= 80

    call = dummy.chat.calls[-1]
    assert call["model"] == "ministral-8b-latest"
    messages = call["messages"]
    assert messages[0]["role"] == "system"
    assert "80" in messages[0]["content"]
    assert "bash" in messages[1]["content"].lower()


@pytest.mark.asyncio
async def test_classify_urgency_normalizes_ministral_output(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecheck.notifications.ministral as ministral_module

    dummy = _DummyMistralClient("HIGH")
    monkeypatch.setattr(ministral_module, "get_mistral_client", lambda: dummy)

    event = ApprovalRequestEvent(call_id="tc-1", tool_name="bash", args={"command": "rm -rf node_modules"})
    assert await ministral_module.classify_urgency(event) == "high"

    dummy_bad = _DummyMistralClient("banana")
    monkeypatch.setattr(ministral_module, "get_mistral_client", lambda: dummy_bad)
    assert await ministral_module.classify_urgency(event) == "normal"

