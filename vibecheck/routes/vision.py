from __future__ import annotations

import base64
import os

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()

MISTRAL_CHAT_COMPLETIONS_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_VISION_MODEL = "mistral-large-latest"
DEFAULT_VISION_PROMPT = "Describe this image"
DEFAULT_VISION_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
VISION_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
UPLOAD_READ_CHUNK_SIZE = 1024 * 256


class UpstreamVisionError(Exception):
    def __init__(self, *, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _map_vision_error(error: UpstreamVisionError) -> HTTPException:
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


async def _read_upload_with_limit(
    upload: UploadFile,
    max_upload_bytes: int,
    *,
    too_large_detail: str = "Image file is too large",
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
                    {
                        "type": "image_url",
                        "image_url": f"data:{mime_type};base64,{encoded_image}",
                    },
                    {"type": "text", "text": DEFAULT_VISION_PROMPT},
                ],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(MISTRAL_CHAT_COMPLETIONS_URL, headers=headers, json=payload)
    except httpx.HTTPError as error:
        raise UpstreamVisionError(status_code=502, detail=f"Vision upstream transport error: {error}") from error

    if response.status_code >= 400:
        detail = response.text.strip() or "unknown vision upstream error"
        raise UpstreamVisionError(status_code=response.status_code, detail=detail)

    try:
        response_payload = response.json()
    except ValueError as error:
        raise UpstreamVisionError(status_code=502, detail=f"Vision upstream returned invalid JSON: {error}") from error

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise UpstreamVisionError(status_code=502, detail="Vision upstream returned no choices")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise UpstreamVisionError(status_code=502, detail="Vision upstream returned malformed choices")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise UpstreamVisionError(status_code=502, detail="Vision upstream returned malformed message payload")

    text = _normalize_vision_content(message.get("content"))
    if not text:
        raise UpstreamVisionError(status_code=502, detail="Vision upstream returned empty content")
    return text


@router.post("/api/vision")
async def vision(image: UploadFile | None = File(None)) -> dict[str, str]:
    if image is None:
        raise HTTPException(status_code=400, detail="Image file is required")

    content_type = (image.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if content_type not in VISION_ALLOWED_MIME_TYPES:
        allowed = ", ".join(sorted(VISION_ALLOWED_MIME_TYPES))
        raise HTTPException(status_code=415, detail=f"Unsupported image MIME type. Allowed types: {allowed}")

    max_upload_bytes = _parse_positive_int_env("VISION_MAX_UPLOAD_BYTES", DEFAULT_VISION_MAX_UPLOAD_BYTES)
    image_bytes = await _read_upload_with_limit(image, max_upload_bytes)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image file is empty")

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY is not set")

    try:
        text = await describe_image(api_key=api_key, image_bytes=image_bytes, mime_type=content_type)
    except UpstreamVisionError as error:
        raise _map_vision_error(error) from error

    return {"text": text, "prompt": DEFAULT_VISION_PROMPT, "model": DEFAULT_VISION_MODEL}
