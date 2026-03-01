from __future__ import annotations

import asyncio
from collections.abc import Iterable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from vibecheck.auth import is_psk_valid, load_psk
from vibecheck.bridge import session_manager
from vibecheck.events import ConnectedEvent, Event, HeartbeatEvent, StateChangeEvent


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = {}
        self.socket_to_session: dict[WebSocket, str] = {}
        self._expected_psk: str | None = None

    def _get_expected_psk(self) -> str:
        if self._expected_psk is None:
            self._expected_psk = load_psk()
        return self._expected_psk

    async def connect(self, websocket: WebSocket, session_id: str, psk: str | None) -> bool:
        if not is_psk_valid(psk, self._get_expected_psk()):
            await websocket.close(code=4401)
            return False
        await websocket.accept()
        connections = self.rooms.setdefault(session_id, set())
        connections.add(websocket)
        self.socket_to_session[websocket] = session_id
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        session_id = self.socket_to_session.pop(websocket, None)
        if session_id is None:
            return
        connections = self.rooms.get(session_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self.rooms.pop(session_id, None)

    @property
    def total_clients(self) -> int:
        return len(self.socket_to_session)

    def session_clients(self, session_id: str) -> int:
        return len(self.rooms.get(session_id, set()))

    @staticmethod
    def _serialize_event(event: Event | dict) -> dict:
        if hasattr(event, "model_dump"):
            return event.model_dump(mode="json")
        return dict(event)

    async def send_personal(self, websocket: WebSocket, event: Event | dict) -> None:
        payload = self._serialize_event(event)
        try:
            await websocket.send_json(payload)
        except Exception:
            await self.disconnect(websocket)

    async def _send_many(self, sockets: Iterable[WebSocket], event: Event | dict) -> None:
        payload = self._serialize_event(event)
        stale: list[WebSocket] = []
        for websocket in list(sockets):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            await self.disconnect(websocket)

    async def broadcast(self, session_id: str, event: Event | dict) -> None:
        await self._send_many(self.rooms.get(session_id, set()), event)

    async def broadcast_all(self, event: Event | dict) -> None:
        await self._send_many(self.socket_to_session.keys(), event)


async def _send_heartbeats(websocket: WebSocket) -> None:
    while True:
        await asyncio.sleep(30)
        await websocket.send_json(HeartbeatEvent().model_dump(mode="json"))


router = APIRouter()
manager = ConnectionManager()


def bind_session_manager() -> None:
    session_manager.set_connection_manager(manager)


@router.websocket("/ws/events/{session_id}")
async def events(websocket: WebSocket, session_id: str) -> None:
    provided_psk = websocket.query_params.get("psk")
    connected = await manager.connect(websocket=websocket, session_id=session_id, psk=provided_psk)
    if not connected:
        return

    if not session_manager.has_known_session(session_id):
        await websocket.close(code=4404)
        await manager.disconnect(websocket)
        return

    bridge = session_manager.attach(session_id)
    await manager.send_personal(websocket, ConnectedEvent(session_id=session_id))
    await manager.send_personal(
        websocket,
        StateChangeEvent(
            state=bridge.state,
            attach_mode=bridge.attach_mode,
            controllable=bridge.controllable,
        ),
    )
    for event in bridge.backlog():
        await manager.send_personal(websocket, event)
    stats_event = bridge._build_stats_event()
    if stats_event is not None:
        await manager.send_personal(websocket, stats_event)

    heartbeat_task = asyncio.create_task(_send_heartbeats(websocket))

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):
            pass
        await manager.disconnect(websocket)
