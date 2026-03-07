from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from mistralai import Mistral
from mistralai.models.file import File
from mistralai.models.sdkerror import SDKError
from pydantic import BaseModel, Field, field_validator

router = APIRouter()
logger = logging.getLogger(__name__)

VOXTRAL_MODEL = "voxtral-mini-latest"
DEFAULT_MAX_AUDIO_BYTES = 10 * 1024 * 1024
STT_TIMEOUT_SECONDS = 30

ELEVENLABS_TTS_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
TTS_TIMEOUT_SECONDS = 60

DEFAULT_VOICES = [
    {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "language": "EN"},
    {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "language": "EN"},
    {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "language": "EN"},
    {"voice_id": "B8gJV1IhpuegLxdpXFOE", "name": "Kuon", "language": "JP"},
    {"voice_id": "j210dv0vWm7fCknyQpbA", "name": "Hinata", "language": "JP"},
    {"voice_id": "3JDquces8E8bkmvbh6Bc", "name": "Otani", "language": "JP"},
]


class VoiceTranscriptionResponse(BaseModel):
    text: str
    language: str
    duration_ms: int = Field(ge=0)


class TTSSynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice_id: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be empty")
        return cleaned


def get_mistral_client() -> Mistral:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY is not set")
    return Mistral(api_key=api_key)


def _max_audio_bytes() -> int:
    configured = os.environ.get("VIBECHECK_MAX_AUDIO_BYTES")
    if configured is None:
        return DEFAULT_MAX_AUDIO_BYTES
    try:
        value = int(configured)
    except ValueError:
        return DEFAULT_MAX_AUDIO_BYTES
    if value <= 0:
        return DEFAULT_MAX_AUDIO_BYTES
    return value


def _guard_audio_size(*, size: int, max_bytes: int) -> None:
    if size > max_bytes:
        raise HTTPException(status_code=413, detail="Audio payload too large")

def _normalize_content_type(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return value.split(";", 1)[0].strip().lower()


def _guard_audio_content_type(content_type: str | None) -> str | None:
    normalized = _normalize_content_type(content_type)
    if not normalized:
        return None
    if normalized.startswith("audio/") or normalized == "application/octet-stream":
        return normalized
    raise HTTPException(status_code=415, detail="Unsupported audio content type")


async def _read_request_body_limited(request: Request, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        size += len(chunk)
        _guard_audio_size(size=size, max_bytes=max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


async def _read_upload_limited(upload: object, max_bytes: int) -> bytes:
    if not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="Audio file is required")

    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await upload.read(1024 * 1024)  # type: ignore[reportUnknownMemberType]
        if not chunk:
            break
        size += len(chunk)
        _guard_audio_size(size=size, max_bytes=max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


def _segments_duration_ms(segments: Any) -> int:
    if not isinstance(segments, list) or not segments:
        return 0

    ends: list[float] = []
    for segment in segments:
        end = getattr(segment, "end", None)
        if isinstance(end, (float, int)):
            ends.append(float(end))

    if not ends:
        return 0
    return max(0, int(max(ends) * 1000))


def _map_mistral_error(error: SDKError) -> HTTPException:
    status_code = getattr(getattr(error, "raw_response", None), "status_code", 502)
    if status_code in {401, 403}:
        return HTTPException(status_code=502, detail="STT authentication with Mistral failed")
    if status_code == 429:
        return HTTPException(status_code=429, detail="STT rate limited")
    if status_code >= 500:
        return HTTPException(status_code=502, detail="STT upstream unavailable")
    return HTTPException(status_code=400, detail="STT request failed")


@router.post("/api/voice/transcribe")
async def transcribe(
    request: Request,
    language: Literal["ja", "en", "fr"] = Query("ja"),
) -> VoiceTranscriptionResponse:
    content_type = request.headers.get("content-type") or ""
    max_bytes = _max_audio_bytes()
    content_length = request.headers.get("content-length")
    if not content_type.startswith("multipart/form-data") and content_length:
        try:
            _guard_audio_size(size=int(content_length), max_bytes=max_bytes)
        except ValueError:
            pass
    audio_bytes: bytes
    filename = "recording.webm"
    file_content_type: str | None = None

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("audio") or form.get("file")
        if upload is None:
            raise HTTPException(status_code=400, detail="Audio file is required")
        filename = getattr(upload, "filename", None) or filename
        file_content_type = getattr(upload, "content_type", None)
        _guard_audio_content_type(file_content_type)
        audio_bytes = await _read_upload_limited(upload, max_bytes)
    else:
        file_content_type = content_type or None
        _guard_audio_content_type(file_content_type)
        audio_bytes = await _read_request_body_limited(request, max_bytes)

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio body is required")

    client = get_mistral_client()
    mistral_file = File(
        file_name=filename,
        content=audio_bytes,
        content_type=file_content_type,
    )
    try:
        result = await asyncio.wait_for(
            client.audio.transcriptions.complete_async(
                model=VOXTRAL_MODEL,
                file=mistral_file,
                language=language,
                timestamp_granularities=["segment"],
            ),
            timeout=STT_TIMEOUT_SECONDS,
        )
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail="STT upstream timed out") from error
    except SDKError as error:
        raise _map_mistral_error(error) from error

    duration_ms = _segments_duration_ms(getattr(result, "segments", None))
    return VoiceTranscriptionResponse(
        text=str(getattr(result, "text", "")).strip(),
        language=language,
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# TTS (ElevenLabs proxy)
# ---------------------------------------------------------------------------


def _get_elevenlabs_api_key() -> str:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY is not set")
    return api_key


def _map_tts_error(status_code: int, detail: str) -> HTTPException:
    if status_code in {401, 402, 403}:
        return HTTPException(status_code=502, detail="TTS authentication or quota failure")
    if status_code == 429:
        return HTTPException(status_code=429, detail="TTS rate limited")
    if status_code >= 500:
        return HTTPException(status_code=502, detail="TTS upstream unavailable")
    return HTTPException(status_code=400, detail=f"TTS request failed: {detail}")


async def open_tts_stream(
    *, api_key: str, text: str, voice_id: str
) -> tuple[httpx.AsyncClient, httpx.Response]:
    url = ELEVENLABS_TTS_URL_TEMPLATE.format(voice_id=voice_id)
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": DEFAULT_TTS_MODEL,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
    }

    http_client = httpx.AsyncClient(timeout=TTS_TIMEOUT_SECONDS)
    try:
        request = http_client.build_request("POST", url, headers=headers, json=payload)
        response = await http_client.send(request, stream=True)
    except httpx.HTTPError as error:
        await http_client.aclose()
        raise _map_tts_error(502, f"TTS upstream transport error: {error}") from error

    if response.status_code >= 400:
        body = (await response.aread()).decode("utf-8", errors="ignore").strip()
        await response.aclose()
        await http_client.aclose()
        raise _map_tts_error(response.status_code, body or "unknown TTS upstream error")

    return http_client, response


@router.get("/api/voice/voices")
async def list_voices() -> dict[str, list[dict[str, str]]]:
    return {"voices": DEFAULT_VOICES}


@router.post("/api/voice/synthesize")
async def synthesize(body: TTSSynthesizeRequest) -> StreamingResponse:
    api_key = _get_elevenlabs_api_key()
    voice_id = body.voice_id or os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", DEFAULT_VOICE_ID)

    try:
        http_client, upstream_response = await open_tts_stream(
            api_key=api_key, text=body.text, voice_id=voice_id
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"TTS upstream error: {error}") from error

    upstream_stream = upstream_response.aiter_bytes()

    # Read first chunk to verify non-empty response before committing to streaming
    first_chunk = b""
    try:
        async for chunk in upstream_stream:
            if chunk:
                first_chunk = chunk
                break
    except (httpx.HTTPError, httpx.StreamError) as error:
        await upstream_response.aclose()
        await http_client.aclose()
        raise HTTPException(status_code=502, detail=f"TTS upstream read failed: {error}") from error

    if not first_chunk:
        await upstream_response.aclose()
        await http_client.aclose()
        raise HTTPException(status_code=502, detail="TTS upstream returned empty audio")

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            yield first_chunk
            async for chunk in upstream_stream:
                if chunk:
                    yield chunk
        except (httpx.HTTPError, httpx.StreamError) as error:
            logger.exception("TTS stream interrupted mid-response")
            raise RuntimeError("TTS stream interrupted mid-response") from error
        finally:
            await upstream_response.aclose()
            await http_client.aclose()

    return StreamingResponse(stream_body(), media_type="audio/mpeg")
