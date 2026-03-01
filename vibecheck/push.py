from __future__ import annotations

import asyncio
import json
import logging
import os
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
from vibecheck.notifications.manager import IntensityManager
from vibecheck.notifications.ministral import classify_urgency, generate_notification_copy

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
        self.intensity = IntensityManager()
        self._idle_sessions: set[str] = set()
        self._idle_task: asyncio.Task[None] | None = None

    def _cancel_idle_task(self) -> None:
        task = self._idle_task
        if task is None:
            return
        if not task.done():
            task.cancel()
        self._idle_task = None

    def _ensure_idle_task(self) -> None:
        task = self._idle_task
        if task is not None and not task.done():
            return

        loop = asyncio.get_running_loop()
        task = loop.create_task(self._idle_worker())

        def _swallow(task: asyncio.Task[None]) -> None:
            if task.cancelled():
                return
            try:
                task.exception()
            except Exception:
                return

        task.add_done_callback(_swallow)
        self._idle_task = task

    async def _idle_worker(self) -> None:
        while True:
            await asyncio.sleep(60)
            await self._send_idle_escalation_if_needed()

    def _handle_bridge_state(self, session_id: str, state: str) -> None:
        normalized = state.strip().lower()
        if not normalized:
            return

        if normalized in {"waiting_approval", "waiting_input"}:
            self._idle_sessions.add(session_id)
            self.intensity.mark_idle()
            self._ensure_idle_task()
            return

        self._idle_sessions.discard(session_id)
        if not self._idle_sessions:
            self.intensity.mark_active()
            self._cancel_idle_task()

    @property
    def storage_dir(self) -> Path:
        return self._storage_dir

    def _keys_path(self) -> Path:
        return self._storage_dir / "vapid_keys.json"

    def _subs_path(self) -> Path:
        return self._storage_dir / "push_subscriptions.json"

    def _ensure_storage_dir(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _vapid_sub_claim(self) -> str:
        configured = os.environ.get("VIBECHECK_VAPID_SUB")
        if isinstance(configured, str):
            cleaned = configured.strip()
            if cleaned:
                return cleaned
        return "mailto:vibecheck@localhost"

    def _restrict_secret_file(self, path: Path) -> None:
        try:
            os.chmod(path, 0o600)
        except OSError:
            return

    def get_or_create_vapid_keypair(self) -> VapidKeypair:
        with self._lock:
            path = self._keys_path()
            if path.exists():
                payload: object
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    payload = {}

                public_key = ""
                private_key = ""
                if isinstance(payload, dict):
                    public_key = str(payload.get("public_key", "")).strip()
                    private_key = str(payload.get("private_key", "")).strip()
                if public_key and private_key:
                    self._restrict_secret_file(path)
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
            self._restrict_secret_file(path)
            return keypair

    def public_key(self) -> str:
        return self.get_or_create_vapid_keypair().public_key

    def _load_subscriptions(self) -> list[dict[str, Any]]:
        with self._lock:
            path = self._subs_path()
            if not path.exists():
                return []
            self._restrict_secret_file(path)
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
            path = self._subs_path()
            path.write_text(
                json.dumps(subscriptions, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._restrict_secret_file(path)

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

    async def _notification_payload(self, session_id: str, event: Event) -> dict[str, Any] | None:
        if event.type == "approval_request":
            body = await generate_notification_copy(event.tool_name, event.args)
            return {
                "title": "Approval needed",
                "body": body or event.tool_name,
                "requireInteraction": True,
                "tag": f"approval:{event.call_id}",
                "url": f"/?sid={session_id}",
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
            vapid_claims={"sub": self._vapid_sub_claim()},
            headers={"Urgency": urgency},
            ttl=3600 if payload.get("requireInteraction") else 300,
        )

    async def _send_idle_escalation_if_needed(self) -> None:
        if not self._idle_sessions:
            return

        message = self.intensity.get_idle_message()
        if message is None:
            return

        title, body = message
        subscriptions = self._load_subscriptions()
        if not subscriptions:
            return

        for session_id in list(self._idle_sessions):
            payload = {
                "title": title,
                "body": body,
                "requireInteraction": False,
                "tag": f"idle:{session_id}",
                "url": f"/?sid={session_id}",
            }

            for subscription in subscriptions:
                try:
                    await self._send_notification(subscription=subscription, payload=payload, urgency="low")
                except WebPushException as error:
                    self._maybe_prune_subscription_on_error(subscription, error)
                    logger.exception("idle push send failed for session %s", session_id)
                except Exception:
                    logger.exception("idle push crashed for session %s", session_id)

    def _maybe_prune_subscription_on_error(self, subscription: dict[str, Any], error: WebPushException) -> None:
        response = getattr(error, "response", None)
        status = getattr(response, "status", None)
        if status is None:
            status = getattr(response, "status_code", None)
        if not isinstance(status, int):
            return
        if status not in {404, 410}:
            return

        endpoint = str(subscription.get("endpoint", "")).strip()
        if endpoint:
            self.unsubscribe(endpoint)

    async def send_for_event(self, session_id: str, event: Event) -> None:
        if event.type == "state":
            state = getattr(event, "state", None)
            if isinstance(state, str):
                self._handle_bridge_state(session_id, state)
            return

        intensity_key: str | None = None
        if event.type == "approval_request":
            intensity_key = "approval"
        elif event.type == "input_request":
            intensity_key = "user_input"
        elif event.type == "tool_result" and event.is_error:
            intensity_key = "error"

        if intensity_key and not self.intensity.should_notify(intensity_key):
            return

        payload = await self._notification_payload(session_id, event)
        if payload is None:
            return

        urgency = "normal"
        if payload.get("requireInteraction"):
            urgency = "high"
        else:
            urgency = await classify_urgency(event)

        subscriptions = self._load_subscriptions()
        if not subscriptions:
            return

        for subscription in subscriptions:
            try:
                await self._send_notification(subscription=subscription, payload=payload, urgency=urgency)
            except WebPushException as error:
                self._maybe_prune_subscription_on_error(subscription, error)
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
