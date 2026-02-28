from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from mistralai import Mistral
from mistralai.models.sdkerror import SDKError
from pydantic import BaseModel, Field

router = APIRouter()

TRANSLATE_MODEL = "mistral-large-latest"

SYSTEM_PROMPT = """You are a translation engine.

Translate the user's text while strictly preserving Markdown formatting.

Rules:
- Preserve fenced code blocks and inline code exactly (do not translate inside code blocks).
- Preserve file paths, CLI commands, identifiers, and technical terms untranslated.
- Keep links/URLs unchanged.
- Output ONLY the translated text, with no extra commentary.
"""


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    target_lang: str = Field(min_length=2)
    source_lang: str | None = None


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
        result = await client.chat.complete_async(
            model=TRANSLATE_MODEL,
            messages=messages,
            temperature=0.1,
        )
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

