from __future__ import annotations

import json
import math
from dataclasses import dataclass
from types import TracebackType
from typing import Any
from urllib.parse import urlsplit

import anyio
from starlette.types import ASGIApp, Message, Scope
from starlette.websockets import WebSocketDisconnect


@dataclass(slots=True)
class ASGIWebSocketSession:
    app: ASGIApp
    scope: Scope

    _to_app: anyio.abc.ObjectSendStream[Message] | None = None
    _from_app: anyio.abc.ObjectReceiveStream[Message] | None = None
    _tg: anyio.abc.TaskGroup | None = None

    async def __aenter__(self) -> "ASGIWebSocketSession":
        to_app_tx, to_app_rx = anyio.create_memory_object_stream[Message](math.inf)
        from_app_tx, from_app_rx = anyio.create_memory_object_stream[Message](math.inf)
        self._to_app = to_app_tx
        self._from_app = from_app_rx

        tg = anyio.create_task_group()
        await tg.__aenter__()
        self._tg = tg

        async def run_app() -> None:
            async with to_app_rx, from_app_tx:
                await self.app(self.scope, to_app_rx.receive, from_app_tx.send)

        tg.start_soon(run_app)

        await to_app_tx.send({"type": "websocket.connect"})
        message = await self.receive()
        if message["type"] == "websocket.close":
            raise WebSocketDisconnect(code=message.get("code", 1000), reason=message.get("reason", ""))
        if message["type"] == "websocket.accept":
            return self
        if message["type"] == "websocket.http.response.start":
            # Denial response; coerce into WebSocketDisconnect with best-effort code.
            status = message.get("status", 403)
            raise WebSocketDisconnect(code=status, reason="denied")
        raise AssertionError(f"unexpected websocket handshake message: {message!r}")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        _ = exc_type, exc, tb
        if self._to_app is not None:
            try:
                await self._to_app.send({"type": "websocket.disconnect", "code": 1000})
            except Exception:
                pass
            try:
                await self._to_app.aclose()
            except Exception:
                pass

        if self._tg is not None:
            await self._tg.__aexit__(None, None, None)

        if self._from_app is not None:
            try:
                await self._from_app.aclose()
            except Exception:
                pass

        self._to_app = None
        self._from_app = None
        self._tg = None

    async def send(self, message: Message) -> None:
        if self._to_app is None:
            raise RuntimeError("WebSocket session is not open")
        await self._to_app.send(message)

    async def receive(self) -> Message:
        if self._from_app is None:
            raise RuntimeError("WebSocket session is not open")
        return await self._from_app.receive()

    async def receive_json(self) -> Any:
        message = await self.receive()
        if message["type"] == "websocket.close":
            raise WebSocketDisconnect(code=message.get("code", 1000), reason=message.get("reason", ""))
        if message["type"] != "websocket.send":
            raise AssertionError(f"unexpected websocket message: {message!r}")

        if "text" in message:
            payload = message["text"]
        else:
            payload = message.get("bytes", b"").decode("utf-8")
        return json.loads(payload)


def websocket_session(app: ASGIApp, url: str) -> ASGIWebSocketSession:
    parts = urlsplit(url)
    path = parts.path
    query_string = parts.query.encode("ascii")

    scope: Scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "path": path,
        "raw_path": path.encode("ascii"),
        "root_path": "",
        "scheme": "ws",
        "query_string": query_string,
        "headers": [(b"host", b"testserver")],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "subprotocols": [],
        "state": {},
        "extensions": {"websocket.http.response": {}},
    }
    return ASGIWebSocketSession(app=app, scope=scope)

