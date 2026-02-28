from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from py_vapid import Vapid02
from py_vapid.utils import b64urlencode
from pywebpush import WebPushException, webpush_async

from vibecheck.events import Event

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VapidKeypair:
    public_key: str
    private_key: str


def _default_storage_dir() -> Path:
    return Path.home() / ".vibecheck"


def _generate_vapid_keypair() -> VapidKeypair:
    vapid = Vapid02()
    vapid.generate_keys()

    private_der = vapid.private_key.private_bytes(
        encoding=Encoding.DER,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    public_raw = vapid.public_key.public_bytes(
        encoding=Encoding.X962,
        format=PublicFormat.UncompressedPoint,
    )

    return VapidKeypair(
        public_key=b64urlencode(public_raw),
        private_key=b64urlencode(private_der),
    )


class PushManager:
    def __init__(self, *, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir or _default_storage_dir()
        self._lock = threading.Lock()

    @property
    def storage_dir(self) -> Path:
        return self._storage_dir

    def _keys_path(self) -> Path:
        return self._storage_dir / "vapid_keys.json"

    def _subs_path(self) -> Path:
        return self._storage_dir / "push_subscriptions.json"

    def _ensure_storage_dir(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_vapid_keypair(self) -> VapidKeypair:
        with self._lock:
            path = self._keys_path()
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                public_key = str(payload.get("public_key", "")).strip()
                private_key = str(payload.get("private_key", "")).strip()
                if public_key and private_key:
                    return VapidKeypair(public_key=public_key, private_key=private_key)

            self._ensure_storage_dir()
            keypair = _generate_vapid_keypair()
            path.write_text(
                json.dumps(
                    {"public_key": keypair.public_key, "private_key": keypair.private_key},
                    ensure_ascii=True,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            return keypair

    def public_key(self) -> str:
        return self.get_or_create_vapid_keypair().public_key

    def _load_subscriptions(self) -> list[dict[str, Any]]:
        with self._lock:
            path = self._subs_path()
            if not path.exists():
                return []
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return []
            if not isinstance(payload, list):
                return []
            subscriptions: list[dict[str, Any]] = []
            for item in payload:
                if isinstance(item, dict) and isinstance(item.get("endpoint"), str):
                    subscriptions.append(dict(item))
            return subscriptions

    def _store_subscriptions(self, subscriptions: list[dict[str, Any]]) -> None:
        with self._lock:
            self._ensure_storage_dir()
            self._subs_path().write_text(
                json.dumps(subscriptions, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def subscribe(self, subscription: dict[str, Any]) -> None:
        endpoint = str(subscription.get("endpoint", "")).strip()
        if not endpoint:
            raise ValueError("subscription endpoint is required")

        subscriptions = self._load_subscriptions()
        filtered = [item for item in subscriptions if item.get("endpoint") != endpoint]
        filtered.append(dict(subscription))
        self._store_subscriptions(filtered)

    def unsubscribe(self, endpoint: str) -> bool:
        endpoint = endpoint.strip()
        if not endpoint:
            return False
        subscriptions = self._load_subscriptions()
        filtered = [item for item in subscriptions if item.get("endpoint") != endpoint]
        if len(filtered) == len(subscriptions):
            return False
        self._store_subscriptions(filtered)
        return True

    def _notification_payload(self, session_id: str, event: Event) -> dict[str, Any] | None:
        if event.type == "approval_request":
            return {
                "title": "Approval needed",
                "body": event.tool_name,
                "requireInteraction": True,
                "tag": f"approval:{event.call_id}",
                "url": f"/?sid={session_id}",
                "actions": [
                    {"action": "approve", "title": "Approve"},
                    {"action": "deny", "title": "Deny"},
                ],
            }

        if event.type == "input_request":
            return {
                "title": "Input requested",
                "body": event.question,
                "requireInteraction": True,
                "tag": f"input:{event.request_id}",
                "url": f"/?sid={session_id}",
            }

        if event.type == "tool_result" and event.is_error:
            return {
                "title": "Vibe error",
                "body": (event.output or "Tool failed")[:160],
                "requireInteraction": False,
                "tag": f"error:{event.call_id}",
                "url": f"/?sid={session_id}",
            }

        return None

    async def _send_notification(self, *, subscription: dict[str, Any], payload: dict[str, Any], urgency: str) -> None:
        keypair = self.get_or_create_vapid_keypair()
        data = json.dumps(payload, ensure_ascii=False)
        await webpush_async(
            subscription_info=subscription,
            data=data,
            vapid_private_key=keypair.private_key,
            vapid_claims={"sub": "mailto:vibecheck@localhost"},
            headers={"Urgency": urgency},
            ttl=3600 if payload.get("requireInteraction") else 300,
        )

    async def send_for_event(self, session_id: str, event: Event) -> None:
        payload = self._notification_payload(session_id, event)
        if payload is None:
            return

        urgency = "normal"
        if payload.get("requireInteraction"):
            urgency = "high"

        subscriptions = self._load_subscriptions()
        if not subscriptions:
            return

        for subscription in subscriptions:
            try:
                await self._send_notification(subscription=subscription, payload=payload, urgency=urgency)
            except WebPushException:
                logger.exception("push send failed for session %s", session_id)
            except Exception:
                logger.exception("push notification crashed for session %s", session_id)

    def notify_for_event(self, session_id: str, event: Event) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.send_for_event(session_id=session_id, event=event))


_current_push_manager: PushManager | None = None
_BRIDGE_LISTENER_ATTR = "_vibecheck_push_listener"


def set_push_manager(manager: PushManager | None) -> None:
    global _current_push_manager
    _current_push_manager = manager


def attach_bridge(bridge: object) -> None:
    if getattr(bridge, _BRIDGE_LISTENER_ATTR, None) is not None:
        return

    session_id = getattr(bridge, "session_id", None)
    if not isinstance(session_id, str) or not session_id:
        return

    def listener(event: Event) -> None:
        manager = _current_push_manager
        if manager is None:
            return
        manager.notify_for_event(session_id, event)

    setattr(bridge, _BRIDGE_LISTENER_ATTR, listener)
    add_event_listener = getattr(bridge, "add_event_listener", None)
    if callable(add_event_listener):
        add_event_listener(listener)
