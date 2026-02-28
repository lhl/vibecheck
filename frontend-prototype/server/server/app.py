from __future__ import annotations

import base64
import os
from collections.abc import AsyncIterator
import logging

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="frontend-prototype-server")
# Prototype/dev mode: allow the local frontend dev server; tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MISTRAL_STT_URL = "https://api.mistral.ai/v1/audio/transcriptions"
ELEVENLABS_TTS_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_STT_MODEL = "voxtral-mini-latest"
MISTRAL_CHAT_COMPLETIONS_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_VISION_MODEL = "mistral-large-latest"
DEFAULT_VISION_PROMPT = "Describe this image"
DEFAULT_VISION_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
VISION_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
UPLOAD_READ_CHUNK_SIZE = 1024 * 256
logger = logging.getLogger(__name__)

DEFAULT_VOICES = [
    {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "language": "EN"},
    {"voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella", "language": "EN"},
    {"voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "language": "EN"},
    {"voice_id": "B8gJV1IhpuegLxdpXFOE", "name": "Kuon", "language": "JP"},
    {"voice_id": "j210dv0vWm7fCknyQpbA", "name": "Hinata", "language": "JP"},
    {"voice_id": "3JDquces8E8bkmvbh6Bc", "name": "Otani", "language": "JP"},
]


class UpstreamAPIError(Exception):
    def __init__(self, *, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    voice_id: str | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("text must not be empty")
        return cleaned


def _map_stt_error(error: UpstreamAPIError) -> HTTPException:
    if error.status_code in {401, 403}:
        return HTTPException(status_code=502, detail="STT authentication with Mistral failed")
    if error.status_code == 429:
        return HTTPException(status_code=429, detail="STT rate limited")
    if error.status_code >= 500:
        return HTTPException(status_code=502, detail="STT upstream unavailable")
    return HTTPException(status_code=400, detail=f"STT request failed: {error.detail}")


def _map_tts_error(error: UpstreamAPIError) -> HTTPException:
    if error.status_code in {401, 402, 403}:
        return HTTPException(status_code=502, detail="TTS authentication or quota failure")
    if error.status_code == 429:
        return HTTPException(status_code=429, detail="TTS rate limited")
    if error.status_code >= 500:
        return HTTPException(status_code=502, detail="TTS upstream unavailable")
    return HTTPException(status_code=400, detail=f"TTS request failed: {error.detail}")


def _map_vision_error(error: UpstreamAPIError) -> HTTPException:
    if error.status_code == 429:
        return HTTPException(status_code=429, detail="Vision rate limited")
    if error.status_code in {401, 403}:
        return HTTPException(status_code=502, detail="Vision authentication with Mistral failed")
    if error.status_code >= 500:
        return HTTPException(status_code=502, detail="Vision upstream unavailable")
    return HTTPException(status_code=502, detail="Vision upstream request failed")


def _parse_positive_int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise HTTPException(status_code=500, detail=f"{name} must be an integer") from error
    if value <= 0:
        raise HTTPException(status_code=500, detail=f"{name} must be greater than 0")
    return value


async def transcribe_audio(
    *,
    api_key: str,
    audio_bytes: bytes,
    filename: str,
    content_type: str | None,
    language: str,
) -> str:
    files = {"file": (filename, audio_bytes, content_type or "application/octet-stream")}
    data = {"model": DEFAULT_STT_MODEL, "language": language}
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(MISTRAL_STT_URL, headers=headers, data=data, files=files)
    except httpx.HTTPError as error:
        raise UpstreamAPIError(status_code=502, detail=f"STT upstream transport error: {error}") from error

    if response.status_code >= 400:
        detail = response.text.strip() or "unknown STT upstream error"
        raise UpstreamAPIError(status_code=response.status_code, detail=detail)

    try:
        payload = response.json()
    except ValueError as error:
        raise UpstreamAPIError(status_code=502, detail=f"STT upstream returned invalid JSON: {error}") from error
    text = str(payload.get("text", "")).strip()
    if not text:
        raise UpstreamAPIError(status_code=502, detail="STT upstream returned an empty transcript")
    return text


async def read_upload_with_limit(
    upload: UploadFile,
    max_upload_bytes: int,
    *,
    too_large_detail: str = "Audio file is too large",
) -> bytes:
    upload_bytes = bytearray()
    while True:
        chunk = await upload.read(UPLOAD_READ_CHUNK_SIZE)
        if not chunk:
            break
        if len(upload_bytes) + len(chunk) > max_upload_bytes:
            raise HTTPException(status_code=413, detail=too_large_detail)
        upload_bytes.extend(chunk)
    return bytes(upload_bytes)


def _normalize_vision_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                value = block.strip()
                if value:
                    parts.append(value)
                continue
            if not isinstance(block, dict):
                continue
            for key in ("text", "content", "value"):
                raw = block.get(key)
                if isinstance(raw, str):
                    value = raw.strip()
                    if value:
                        parts.append(value)
                    break
        return " ".join(parts).strip()

    return ""


async def describe_image(*, api_key: str, image_bytes: bytes, mime_type: str) -> str:
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": DEFAULT_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    # Mistral OpenAPI currently accepts image_url as either a string data URI
                    # or an object with {"url": ...}; we intentionally use the string form.
                    {"type": "image_url", "image_url": f"data:{mime_type};base64,{encoded_image}"},
                    {"type": "text", "text": DEFAULT_VISION_PROMPT},
                ],
            }
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(MISTRAL_CHAT_COMPLETIONS_URL, headers=headers, json=payload)
    except httpx.HTTPError as error:
        raise UpstreamAPIError(status_code=502, detail=f"Vision upstream transport error: {error}") from error

    if response.status_code >= 400:
        detail = response.text.strip() or "unknown vision upstream error"
        raise UpstreamAPIError(status_code=response.status_code, detail=detail)

    try:
        response_payload = response.json()
    except ValueError as error:
        raise UpstreamAPIError(status_code=502, detail=f"Vision upstream returned invalid JSON: {error}") from error

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise UpstreamAPIError(status_code=502, detail="Vision upstream returned no choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise UpstreamAPIError(status_code=502, detail="Vision upstream returned malformed choices")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise UpstreamAPIError(status_code=502, detail="Vision upstream returned malformed message payload")

    text = _normalize_vision_content(message.get("content"))
    if not text:
        raise UpstreamAPIError(status_code=502, detail="Vision upstream returned empty content")
    return text


async def open_tts_stream(*, api_key: str, text: str, voice_id: str) -> tuple[httpx.AsyncClient, httpx.Response]:
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

    client = httpx.AsyncClient(timeout=60.0)
    try:
        request = client.build_request("POST", url, headers=headers, json=payload)
        response = await client.send(request, stream=True)
    except httpx.HTTPError as error:
        await client.aclose()
        raise UpstreamAPIError(status_code=502, detail=f"TTS upstream transport error: {error}") from error

    if response.status_code >= 400:
        body = (await response.aread()).decode("utf-8", errors="ignore").strip()
        await response.aclose()
        await client.aclose()
        raise UpstreamAPIError(
            status_code=response.status_code,
            detail=body or "unknown TTS upstream error",
        )

    return client, response


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get("/api/voices")
def list_voices() -> dict[str, list[dict[str, str]]]:
    return {"voices": DEFAULT_VOICES}


@app.post("/api/stt")
async def stt(audio: UploadFile = File(...), language: str = Form("en")) -> dict[str, str]:
    max_upload_bytes = int(os.environ.get("STT_MAX_UPLOAD_BYTES", "10485760"))
    min_audio_bytes = int(os.environ.get("STT_MIN_AUDIO_BYTES", "2048"))

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY is not set")

    audio_bytes = await read_upload_with_limit(audio, max_upload_bytes)
    size = len(audio_bytes)
    if size < min_audio_bytes:
        raise HTTPException(status_code=400, detail="Recording is too short. Please try again.")

    try:
        transcript = await transcribe_audio(
            api_key=api_key,
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.webm",
            content_type=audio.content_type,
            language=language,
        )
    except UpstreamAPIError as error:
        raise _map_stt_error(error) from error

    return {"text": transcript, "language": language}


@app.post("/api/tts")
async def tts(request: TTSRequest) -> StreamingResponse:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY is not set")

    voice_id = request.voice_id or os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", DEFAULT_VOICE_ID)
    try:
        client, upstream_response = await open_tts_stream(api_key=api_key, text=request.text, voice_id=voice_id)
    except UpstreamAPIError as error:
        raise _map_tts_error(error) from error

    upstream_stream = upstream_response.aiter_bytes()
    first_chunk = b""
    try:
        async for chunk in upstream_stream:
            if chunk:
                first_chunk = chunk
                break
    except (httpx.HTTPError, httpx.StreamError) as error:
        await upstream_response.aclose()
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"TTS upstream read failed: {error}") from error

    if not first_chunk:
        await upstream_response.aclose()
        await client.aclose()
        raise HTTPException(status_code=502, detail="TTS upstream returned empty audio")

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            yield first_chunk
            async for chunk in upstream_stream:
                if chunk:
                    yield chunk
        except (httpx.HTTPError, httpx.StreamError) as error:
            # Response headers are already sent; re-raise so the connection aborts
            # and clients observe a stream failure rather than a silent truncation.
            logger.exception("TTS stream interrupted mid-response")
            raise RuntimeError("TTS stream interrupted mid-response") from error
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(stream_body(), media_type="audio/mpeg")


@app.post("/api/vision")
async def vision(image: UploadFile | None = File(None)) -> dict[str, str]:
    if image is None:
        raise HTTPException(status_code=400, detail="Image file is required")

    content_type = (image.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if content_type not in VISION_ALLOWED_MIME_TYPES:
        allowed = ", ".join(sorted(VISION_ALLOWED_MIME_TYPES))
        raise HTTPException(status_code=415, detail=f"Unsupported image MIME type. Allowed types: {allowed}")

    max_upload_bytes = _parse_positive_int_env("VISION_MAX_UPLOAD_BYTES", DEFAULT_VISION_MAX_UPLOAD_BYTES)

    image_bytes = await read_upload_with_limit(image, max_upload_bytes, too_large_detail="Image file is too large")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image file is empty")

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY is not set")

    try:
        text = await describe_image(api_key=api_key, image_bytes=image_bytes, mime_type=content_type)
    except UpstreamAPIError as error:
        raise _map_vision_error(error) from error

    return {"text": text, "prompt": DEFAULT_VISION_PROMPT, "model": DEFAULT_VISION_MODEL}
