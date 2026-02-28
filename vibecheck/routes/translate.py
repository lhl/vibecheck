from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from pydantic import BaseModel, Field, field_validator

router = APIRouter()

TRANSLATE_MODEL = "mistral-large-latest"
MAX_TRANSLATE_CHARS = 4000
TRANSLATE_TIMEOUT_SECONDS = 15
LANG_CODE_PATTERN = r"^[A-Za-z]{2,8}(-[A-Za-z0-9]{2,8})?$"

SYSTEM_PROMPT = """You are a translation engine.

Translate the user's text while strictly preserving Markdown formatting.

Rules:
- Preserve fenced code blocks and inline code exactly (do not translate inside code blocks).
- Preserve file paths, CLI commands, identifiers, and technical terms untranslated.
- Keep links/URLs unchanged.
- Output ONLY the translated text, with no extra commentary.
"""


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TRANSLATE_CHARS)
    target_lang: str = Field(
        min_length=2,
        max_length=16,
        pattern=LANG_CODE_PATTERN,
    )
    source_lang: str | None = Field(
        default=None,
        min_length=2,
        max_length=16,
        pattern=LANG_CODE_PATTERN,
    )

    @field_validator("target_lang", mode="before")
    @classmethod
    def _strip_target_lang(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("text")
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value

    @field_validator("source_lang", mode="before")
    @classmethod
    def _strip_source_lang(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class TranslateResponse(BaseModel):
    translated_text: str
    source_lang: str
    target_lang: str


def get_mistral_client() -> Mistral:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY is not set")
    return Mistral(api_key=api_key)


def _extract_assistant_text(value: Any) -> str:
    choices = getattr(value, "choices", None)
    if not isinstance(choices, list) or not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            text = getattr(chunk, "text", None)
            if isinstance(text, str) and text:
                parts.append(text)
        return "".join(parts).strip()
    return ""


def _map_mistral_error(error: SDKError) -> HTTPException:
    status_code = getattr(getattr(error, "raw_response", None), "status_code", 502)
    if status_code in {401, 403}:
        return HTTPException(status_code=502, detail="Translation authentication with Mistral failed")
    if status_code == 429:
        return HTTPException(status_code=429, detail="Translation rate limited")
    if status_code >= 500:
        return HTTPException(status_code=502, detail="Translation upstream unavailable")
    return HTTPException(status_code=400, detail="Translation request failed")


@router.post("/api/translate")
async def translate(body: TranslateRequest) -> TranslateResponse:
    target_lang = body.target_lang.strip()
    source_lang = body.source_lang.strip() if isinstance(body.source_lang, str) else ""

    instruction = f"Translate to {target_lang}."
    if source_lang:
        instruction = f"Translate from {source_lang} to {target_lang}."

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{instruction}\n\n{body.text}"},
    ]

    client = get_mistral_client()
    try:
        result = await asyncio.wait_for(
            client.chat.complete_async(
                model=TRANSLATE_MODEL,
                messages=messages,
                temperature=0.1,
            ),
            timeout=TRANSLATE_TIMEOUT_SECONDS,
        )
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail="Translation upstream timed out") from error
    except SDKError as error:
        raise _map_mistral_error(error) from error

    translated = _extract_assistant_text(result)
    if not translated:
        raise HTTPException(status_code=502, detail="Translation upstream returned empty output")

    return TranslateResponse(
        translated_text=translated,
        source_lang=source_lang or "auto",
        target_lang=target_lang,
    )
