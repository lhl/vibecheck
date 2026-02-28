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
