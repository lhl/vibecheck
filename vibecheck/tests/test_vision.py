from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_vision_success_returns_contract(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.vision as vision_module

    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    async def _fake_describe_image(*, api_key: str, image_bytes: bytes, mime_type: str) -> str:
        assert api_key == "test-key"
        assert image_bytes == b"image-bytes"
        assert mime_type == "image/jpeg"
        return "A whiteboard with architecture notes."

    monkeypatch.setattr(vision_module, "describe_image", _fake_describe_image)

    response = await client.post(
        "/api/vision",
        headers={"X-PSK": psk},
        files={"image": ("photo.jpg", b"image-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "A whiteboard with architecture notes.",
        "prompt": "Describe this image",
        "model": "mistral-large-latest",
    }


@pytest.mark.asyncio
async def test_vision_missing_image_returns_400(client, psk: str) -> None:
    response = await client.post("/api/vision", headers={"X-PSK": psk})
    assert response.status_code == 400
    assert "required" in response.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_vision_rejects_unsupported_mime_before_api_key_check(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    response = await client.post(
        "/api/vision",
        headers={"X-PSK": psk},
        files={"image": ("photo.gif", b"GIF89a", "image/gif")},
    )

    assert response.status_code == 415
    assert "unsupported" in response.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_vision_maps_upstream_errors(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecheck.routes.vision as vision_module

    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")

    async def _failing_describe_image(**_kwargs: object) -> str:
        raise vision_module.UpstreamVisionError(status_code=502, detail="provider stack trace abc123")

    monkeypatch.setattr(vision_module, "describe_image", _failing_describe_image)

    response = await client.post(
        "/api/vision",
        headers={"X-PSK": psk},
        files={"image": ("photo.jpg", b"image-bytes", "image/jpeg")},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Vision upstream unavailable"}


@pytest.mark.asyncio
async def test_vision_missing_mistral_api_key_returns_500(
    client,
    psk: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    response = await client.post(
        "/api/vision",
        headers={"X-PSK": psk},
        files={"image": ("photo.jpg", b"image-bytes", "image/jpeg")},
    )

    assert response.status_code == 500
    assert "mistral_api_key" in response.json().get("detail", "").lower()
