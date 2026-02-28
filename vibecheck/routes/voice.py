from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from mistralai import Mistral
from mistralai.models.file import File
from mistralai.models.sdkerror import SDKError
from pydantic import BaseModel, Field

router = APIRouter()

VOXTRAL_MODEL = "voxtral-mini-latest"
DEFAULT_MAX_AUDIO_BYTES = 10 * 1024 * 1024


class VoiceTranscriptionResponse(BaseModel):
    text: str
    language: str
    duration_ms: int = Field(ge=0)


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
    language: Literal["ja", "en"] = Query("ja"),
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
        result = await client.audio.transcriptions.complete_async(
            model=VOXTRAL_MODEL,
            file=mistral_file,
            language=language,
            timestamp_granularities=["segment"],
        )
    except SDKError as error:
        raise _map_mistral_error(error) from error

    duration_ms = _segments_duration_ms(getattr(result, "segments", None))
    return VoiceTranscriptionResponse(
        text=str(getattr(result, "text", "")).strip(),
        language=language,
        duration_ms=duration_ms,
    )
