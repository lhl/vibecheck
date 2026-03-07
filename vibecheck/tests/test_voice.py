from __future__ import annotations

import asyncio

import pytest


class _DummySegment:
    def __init__(self, end: float) -> None:
        self.start = 0.0
        self.end = end
        self.text = "hi"


class _DummyTranscriptionResponse:
    def __init__(self, *, text: str, language: str) -> None:
        self.text = text
        self.language = language
        self.segments = [_DummySegment(1.23)]


class _DummyTranscriptions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def complete_async(self, **kwargs):
        self.calls.append(dict(kwargs))
        return _DummyTranscriptionResponse(text="konnichiwa", language=str(kwargs.get("language") or "ja"))


class _DummyAudio:
    def __init__(self) -> None:
        self.transcriptions = _DummyTranscriptions()


class _DummyMistralClient:
    def __init__(self) -> None:
        self.audio = _DummyAudio()


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["en", "fr"])
async def test_voice_transcribe_accepts_raw_audio_and_forwards_language(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
    language: str,
) -> None:
    import vibecheck.routes.voice as voice_module

    dummy = _DummyMistralClient()
    monkeypatch.setattr(voice_module, "get_mistral_client", lambda: dummy)

    response = await client.post(
        f"/api/voice/transcribe?language={language}",
        headers={"X-PSK": psk, "Content-Type": "audio/webm;codecs=opus"},
        content=b"fake-audio",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "konnichiwa"
    assert payload["language"] == language
    assert payload["duration_ms"] == 1230

    assert dummy.audio.transcriptions.calls
    assert dummy.audio.transcriptions.calls[-1]["model"] == "voxtral-mini-latest"
    assert dummy.audio.transcriptions.calls[-1]["language"] == language


@pytest.mark.asyncio
async def test_voice_transcribe_rejects_missing_audio(client, psk: str) -> None:
    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk, "Content-Type": "audio/webm;codecs=opus"},
        content=b"",
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_voice_transcribe_accepts_multipart_upload(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    dummy = _DummyMistralClient()
    monkeypatch.setattr(voice_module, "get_mistral_client", lambda: dummy)

    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk},
        files={"audio": ("recording.webm", b"fake-audio", "audio/webm")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "konnichiwa"


@pytest.mark.asyncio
async def test_voice_transcribe_rejects_unsupported_language(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    def _should_not_call():
        raise AssertionError("Mistral client should not be called for invalid query params")

    monkeypatch.setattr(voice_module, "get_mistral_client", _should_not_call)

    response = await client.post(
        "/api/voice/transcribe?language=xx",
        headers={"X-PSK": psk, "Content-Type": "audio/webm"},
        content=b"fake-audio",
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_voice_transcribe_rejects_non_audio_content_type_raw(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    def _should_not_call():
        raise AssertionError("Mistral client should not be called for invalid payloads")

    monkeypatch.setattr(voice_module, "get_mistral_client", _should_not_call)

    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk, "Content-Type": "text/plain"},
        content=b"not-audio",
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_voice_transcribe_rejects_non_audio_multipart_upload(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    def _should_not_call():
        raise AssertionError("Mistral client should not be called for invalid payloads")

    monkeypatch.setattr(voice_module, "get_mistral_client", _should_not_call)

    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk},
        files={"audio": ("recording.txt", b"not-audio", "text/plain")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_voice_transcribe_rejects_oversized_raw_audio(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    dummy = _DummyMistralClient()
    monkeypatch.setattr(voice_module, "get_mistral_client", lambda: dummy)
    monkeypatch.setenv("VIBECHECK_MAX_AUDIO_BYTES", "4")

    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk, "Content-Type": "audio/webm"},
        content=b"12345",
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_voice_transcribe_rejects_oversized_multipart_upload(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    dummy = _DummyMistralClient()
    monkeypatch.setattr(voice_module, "get_mistral_client", lambda: dummy)
    monkeypatch.setenv("VIBECHECK_MAX_AUDIO_BYTES", "4")

    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk},
        files={"audio": ("recording.webm", b"12345", "audio/webm")},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_voice_transcribe_returns_500_when_mistral_key_missing(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk, "Content-Type": "audio/webm"},
        content=b"fake-audio",
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
async def test_voice_transcribe_maps_mistral_sdk_errors(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
    upstream_status: int,
    expected_status: int,
    expected_detail: str,
) -> None:
    import httpx
    from mistralai.models.sdkerror import SDKError

    import vibecheck.routes.voice as voice_module

    class _DummyTranscriptions:
        async def complete_async(self, **_kwargs):
            request = httpx.Request("POST", "https://api.mistral.ai/v1/audio/transcriptions")
            response = httpx.Response(upstream_status, request=request)
            raise SDKError("boom", raw_response=response)

    class _DummyAudio:
        def __init__(self) -> None:
            self.transcriptions = _DummyTranscriptions()

    class _DummyClient:
        def __init__(self) -> None:
            self.audio = _DummyAudio()

    monkeypatch.setattr(voice_module, "get_mistral_client", lambda: _DummyClient())

    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk, "Content-Type": "audio/webm"},
        content=b"fake-audio",
    )
    assert response.status_code == expected_status
    payload = response.json()
    assert expected_detail in payload.get("detail", "").lower()


def test_segments_duration_ms_handles_edge_cases() -> None:
    import vibecheck.routes.voice as voice_module

    assert voice_module._segments_duration_ms([]) == 0
    assert voice_module._segments_duration_ms([object()]) == 0

    class _BadEnd:
        end = "nope"

    assert voice_module._segments_duration_ms([_BadEnd()]) == 0

    class _NegativeEnd:
        end = -1.0

    assert voice_module._segments_duration_ms([_NegativeEnd()]) == 0

    class _OkEnd:
        end = 0.42

    assert voice_module._segments_duration_ms([_OkEnd()]) == 420


# ---------------------------------------------------------------------------
# TTS / Voices tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_voices_returns_list(client, psk: str) -> None:
    response = await client.get("/api/voice/voices", headers={"X-PSK": psk})
    assert response.status_code == 200
    payload = response.json()
    assert "voices" in payload
    assert len(payload["voices"]) > 0
    assert all("voice_id" in v and "name" in v for v in payload["voices"])


@pytest.mark.asyncio
async def test_synthesize_returns_500_when_elevenlabs_key_missing(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    response = await client.post(
        "/api/voice/synthesize",
        headers={"X-PSK": psk, "Content-Type": "application/json"},
        json={"text": "hello world"},
    )
    assert response.status_code == 500
    assert "ELEVENLABS_API_KEY" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_synthesize_rejects_empty_text(client, psk: str) -> None:
    response = await client.post(
        "/api/voice/synthesize",
        headers={"X-PSK": psk, "Content-Type": "application/json"},
        json={"text": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_synthesize_rejects_whitespace_only_text(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    response = await client.post(
        "/api/voice/synthesize",
        headers={"X-PSK": psk, "Content-Type": "application/json"},
        json={"text": "   "},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_synthesize_streams_audio(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    fake_audio = b"\xff\xfb\x90\x00" * 100  # fake mp3 bytes

    async def mock_open_tts_stream(*, api_key, text, voice_id):
        class FakeResponse:
            status_code = 200

            def aiter_bytes(self):
                return _async_iter_chunks([fake_audio])

            async def aclose(self):
                pass

        class FakeClient:
            async def aclose(self):
                pass

        return FakeClient(), FakeResponse()

    async def _async_iter_chunks(chunks):
        for chunk in chunks:
            yield chunk

    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(voice_module, "open_tts_stream", mock_open_tts_stream)

    response = await client.post(
        "/api/voice/synthesize",
        headers={"X-PSK": psk, "Content-Type": "application/json"},
        json={"text": "hello world"},
    )
    assert response.status_code == 200
    assert response.headers.get("content-type") == "audio/mpeg"
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_synthesize_uses_custom_voice_id(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    captured = {}

    async def mock_open_tts_stream(*, api_key, text, voice_id):
        captured["voice_id"] = voice_id
        captured["text"] = text

        class FakeResponse:
            status_code = 200

            def aiter_bytes(self):
                return _async_iter_chunks([b"\xff\xfb"])

            async def aclose(self):
                pass

        class FakeClient:
            async def aclose(self):
                pass

        return FakeClient(), FakeResponse()

    async def _async_iter_chunks(chunks):
        for chunk in chunks:
            yield chunk

    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(voice_module, "open_tts_stream", mock_open_tts_stream)

    response = await client.post(
        "/api/voice/synthesize",
        headers={"X-PSK": psk, "Content-Type": "application/json"},
        json={"text": "konnichiwa", "voice_id": "custom-voice-123"},
    )
    assert response.status_code == 200
    assert captured["voice_id"] == "custom-voice-123"
    assert captured["text"] == "konnichiwa"


@pytest.mark.asyncio
async def test_synthesize_maps_upstream_auth_error(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    async def mock_open_tts_stream(*, api_key, text, voice_id):
        raise voice_module._map_tts_error(401, "Unauthorized")

    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(voice_module, "open_tts_stream", mock_open_tts_stream)

    response = await client.post(
        "/api/voice/synthesize",
        headers={"X-PSK": psk, "Content-Type": "application/json"},
        json={"text": "hello"},
    )
    assert response.status_code == 502
    assert "authentication" in response.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_synthesize_maps_upstream_rate_limit(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    async def mock_open_tts_stream(*, api_key, text, voice_id):
        raise voice_module._map_tts_error(429, "Too many requests")

    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(voice_module, "open_tts_stream", mock_open_tts_stream)

    response = await client.post(
        "/api/voice/synthesize",
        headers={"X-PSK": psk, "Content-Type": "application/json"},
        json={"text": "hello"},
    )
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_voice_transcribe_returns_504_on_upstream_timeout(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    class _HangingTranscriptions:
        async def complete_async(self, **kwargs):
            await asyncio.sleep(999)

    class _HangingAudio:
        transcriptions = _HangingTranscriptions()

    class _HangingClient:
        audio = _HangingAudio()

    monkeypatch.setattr(voice_module, "get_mistral_client", lambda: _HangingClient())
    monkeypatch.setattr(voice_module, "STT_TIMEOUT_SECONDS", 0.01)

    response = await client.post(
        "/api/voice/transcribe",
        headers={"X-PSK": psk, "Content-Type": "audio/webm"},
        content=b"fake-audio",
    )
    assert response.status_code == 504
    assert "timed out" in response.json().get("detail", "").lower()
