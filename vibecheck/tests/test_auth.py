import pytest

from vibecheck.app import create_app


@pytest.mark.asyncio
async def test_health_no_auth(client) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_state_with_valid_psk_header(client, psk: str) -> None:
    response = await client.get("/api/state", headers={"X-PSK": psk})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"total", "running", "waiting", "idle"}
    assert all(isinstance(payload[key], int) and payload[key] >= 0 for key in payload)


@pytest.mark.asyncio
async def test_state_with_valid_psk_query_param(client, psk: str) -> None:
    response = await client.get(f"/api/state?psk={psk}")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"total", "running", "waiting", "idle"}
    assert all(isinstance(payload[key], int) and payload[key] >= 0 for key in payload)


@pytest.mark.asyncio
async def test_state_with_bad_psk_returns_401(client) -> None:
    response = await client.get("/api/state", headers={"X-PSK": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.asyncio
async def test_state_with_no_psk_returns_401(client) -> None:
    response = await client.get("/api/state")

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


@pytest.mark.asyncio
async def test_notification_click_telemetry_no_auth_required(client) -> None:
    response = await client.post(
        "/api/telemetry/notification-click",
        json={"stage": "start", "source": "sw_notificationclick"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_startup_fails_when_psk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIBECHECK_PSK", raising=False)

    with pytest.raises(RuntimeError, match="VIBECHECK_PSK"):
        create_app()
