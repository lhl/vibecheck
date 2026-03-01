from __future__ import annotations

import hmac
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

EXACT_EXEMPT_PATHS = {
    "/",
    "/api/health",
    "/api/telemetry/notification-click",
    "/manifest.json",
    "/sw.js",
    "/favicon.ico",
}
PREFIX_EXEMPT_PATHS = ("/static/", "/assets/", "/icons/")


def load_psk() -> str:
    psk = os.environ.get("VIBECHECK_PSK")
    if not psk:
        raise RuntimeError("VIBECHECK_PSK must be set before starting vibecheck")
    return psk


def is_exempt_path(path: str) -> bool:
    if path in EXACT_EXEMPT_PATHS:
        return True
    return path.startswith(PREFIX_EXEMPT_PATHS)


def is_psk_valid(psk: str | None, expected_psk: str) -> bool:
    if not psk:
        return False
    return hmac.compare_digest(psk, expected_psk)


class PSKAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._expected_psk = load_psk()

    async def dispatch(self, request: Request, call_next) -> Response:
        if is_exempt_path(request.url.path):
            return await call_next(request)

        provided_psk = request.headers.get("X-PSK") or request.query_params.get("psk")
        if not is_psk_valid(provided_psk, self._expected_psk):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
