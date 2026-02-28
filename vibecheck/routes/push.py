from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscription(BaseModel):
    endpoint: str = Field(min_length=1)
    keys: SubscriptionKeys
    expirationTime: float | None = None


class UnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1)


def _push_manager_from_request(request: Request):
    manager = getattr(request.app.state, "push_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="Push manager unavailable")
    return manager


@router.get("/api/push/vapid-key")
async def vapid_key(request: Request) -> dict[str, str]:
    manager = _push_manager_from_request(request)
    return {"public_key": manager.public_key()}


@router.post("/api/push/subscribe")
async def subscribe(request: Request, body: PushSubscription) -> dict[str, str]:
    manager = _push_manager_from_request(request)
    manager.subscribe(body.model_dump(mode="json"))
    return {"status": "ok"}


@router.post("/api/push/unsubscribe")
async def unsubscribe(request: Request, body: UnsubscribeRequest) -> dict[str, object]:
    manager = _push_manager_from_request(request)
    removed = manager.unsubscribe(body.endpoint)
    return {"status": "ok", "removed": removed}

