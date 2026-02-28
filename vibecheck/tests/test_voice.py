from __future__ import annotations

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
async def test_voice_transcribe_accepts_raw_audio_and_forwards_language(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.voice as voice_module

    dummy = _DummyMistralClient()
    monkeypatch.setattr(voice_module, "get_mistral_client", lambda: dummy)

    response = await client.post(
        "/api/voice/transcribe?language=en",
        headers={"X-PSK": psk, "Content-Type": "audio/webm;codecs=opus"},
        content=b"fake-audio",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "konnichiwa"
    assert payload["language"] == "en"
    assert payload["duration_ms"] == 1230

    assert dummy.audio.transcriptions.calls
    assert dummy.audio.transcriptions.calls[-1]["model"] == "voxtral-mini-latest"
    assert dummy.audio.transcriptions.calls[-1]["language"] == "en"


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
