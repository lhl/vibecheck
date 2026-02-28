from __future__ import annotations

import pytest


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
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def complete_async(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _DummyChatResponse("こんにちは")


class _DummyMistralClient:
    def __init__(self) -> None:
        self.chat = _DummyChat()


@pytest.mark.asyncio
async def test_translate_endpoint_builds_prompt_and_returns_translation(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.translate as translate_module

    dummy = _DummyMistralClient()
    monkeypatch.setattr(translate_module, "get_mistral_client", lambda: dummy)

    response = await client.post(
        "/api/translate",
        headers={"X-PSK": psk},
        json={"text": "Hello", "target_lang": "ja"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["translated_text"] == "こんにちは"
    assert payload["source_lang"] == "auto"
    assert payload["target_lang"] == "ja"

    assert dummy.chat.calls
    call = dummy.chat.calls[-1]
    assert call["model"] == "mistral-large-latest"
    assert call["temperature"] == 0.1
    messages = call["messages"]
    assert isinstance(messages, list) and messages
    system = messages[0]
    assert system["role"] == "system"
    assert "code block" in system["content"].lower()


@pytest.mark.asyncio
async def test_translate_rejects_oversized_text(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.translate as translate_module

    def _should_not_call():
        raise AssertionError("Mistral client should not be called for invalid payloads")

    monkeypatch.setattr(translate_module, "get_mistral_client", _should_not_call)

    response = await client.post(
        "/api/translate",
        headers={"X-PSK": psk},
        json={"text": "x" * 5000, "target_lang": "ja"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_translate_rejects_invalid_language_codes(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.translate as translate_module

    def _should_not_call():
        raise AssertionError("Mistral client should not be called for invalid payloads")

    monkeypatch.setattr(translate_module, "get_mistral_client", _should_not_call)

    response = await client.post(
        "/api/translate",
        headers={"X-PSK": psk},
        json={"text": "Hello", "target_lang": "ja;rm -rf /"},
    )
    assert response.status_code == 422
