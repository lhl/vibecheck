from __future__ import annotations

import asyncio

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


@pytest.mark.asyncio
async def test_translate_rejects_blank_language_codes_after_strip(
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
        json={"text": "Hello", "target_lang": "  "},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_translate_rejects_empty_text(client, psk: str, monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecheck.routes.translate as translate_module

    def _should_not_call():
        raise AssertionError("Mistral client should not be called for invalid payloads")

    monkeypatch.setattr(translate_module, "get_mistral_client", _should_not_call)

    response = await client.post(
        "/api/translate",
        headers={"X-PSK": psk},
        json={"text": "", "target_lang": "ja"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_translate_rejects_whitespace_only_text(
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
        json={"text": "   ", "target_lang": "ja"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_translate_returns_500_when_mistral_key_missing(client, psk: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    response = await client.post(
        "/api/translate",
        headers={"X-PSK": psk},
        json={"text": "Hello", "target_lang": "ja"},
    )
    assert response.status_code == 500
    payload = response.json()
    assert "MISTRAL_API_KEY" in payload.get("detail", "")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upstream_status", "expected_status", "expected_detail"),
    [
        (401, 502, "authentication"),
        (429, 429, "rate limited"),
        (500, 502, "upstream unavailable"),
    ],
)
async def test_translate_maps_mistral_sdk_errors(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
    upstream_status: int,
    expected_status: int,
    expected_detail: str,
) -> None:
    import httpx
    from mistralai.models.sdkerror import SDKError

    import vibecheck.routes.translate as translate_module

    class _DummyChat:
        async def complete_async(self, **_kwargs):
            request = httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions")
            response = httpx.Response(upstream_status, request=request)
            raise SDKError("boom", raw_response=response)

    class _DummyClient:
        def __init__(self) -> None:
            self.chat = _DummyChat()

    monkeypatch.setattr(translate_module, "get_mistral_client", lambda: _DummyClient())

    response = await client.post(
        "/api/translate",
        headers={"X-PSK": psk},
        json={"text": "Hello", "target_lang": "ja"},
    )
    assert response.status_code == expected_status
    payload = response.json()
    assert expected_detail in payload.get("detail", "").lower()


@pytest.mark.asyncio
async def test_translate_returns_502_when_upstream_empty_output(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.translate as translate_module

    class _DummyAssistantMessage:
        def __init__(self) -> None:
            self.content = ""

    class _DummyChoice:
        def __init__(self) -> None:
            self.message = _DummyAssistantMessage()

    class _DummyChatResponse:
        def __init__(self) -> None:
            self.choices = [_DummyChoice()]

    class _DummyChat:
        async def complete_async(self, **_kwargs):
            return _DummyChatResponse()

    class _DummyClient:
        def __init__(self) -> None:
            self.chat = _DummyChat()

    monkeypatch.setattr(translate_module, "get_mistral_client", lambda: _DummyClient())

    response = await client.post(
        "/api/translate",
        headers={"X-PSK": psk},
        json={"text": "Hello", "target_lang": "ja"},
    )
    assert response.status_code == 502
    payload = response.json()
    assert "empty" in payload.get("detail", "").lower()


@pytest.mark.asyncio
async def test_translate_returns_504_on_upstream_timeout(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.translate as translate_module

    class _HangingChat:
        async def complete_async(self, **_kwargs):
            await asyncio.sleep(999)

    class _HangingClient:
        def __init__(self) -> None:
            self.chat = _HangingChat()

    monkeypatch.setattr(translate_module, "get_mistral_client", lambda: _HangingClient())
    monkeypatch.setattr(translate_module, "TRANSLATE_TIMEOUT_SECONDS", 0.01)

    response = await client.post(
        "/api/translate",
        headers={"X-PSK": psk},
        json={"text": "Hello", "target_lang": "ja"},
    )
    assert response.status_code == 504
    assert "timed out" in response.json().get("detail", "").lower()
