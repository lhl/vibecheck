from __future__ import annotations

import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from vibecheck.auth import PSKAuthMiddleware, load_psk
from vibecheck.routes.api import router as api_router
from vibecheck.routes.push import router as push_router
from vibecheck.routes.translate import router as translate_router
from vibecheck.routes.voice import router as voice_router
from vibecheck.ws import bind_session_manager
from vibecheck.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.bridge = None
    yield
    app.state.bridge = None


def resolve_static_dir() -> Path:
    configured = os.environ.get("VIBECHECK_STATIC_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parent / "static"


def static_file(path: Path) -> Response:
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not Found")
    media_type, _encoding = mimetypes.guess_type(str(path))
    return Response(content=path.read_bytes(), media_type=media_type or "application/octet-stream")


def _safe_join(root: Path, fragment: str) -> Path:
    candidate = (root / fragment).resolve()
    if not candidate.is_relative_to(root):
        raise HTTPException(status_code=404, detail="Not Found")
    return candidate


def create_app() -> FastAPI:
    load_psk()
    bind_session_manager()
    app = FastAPI(title="vibecheck", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(PSKAuthMiddleware)

    app.include_router(api_router)
    app.include_router(push_router)
    app.include_router(translate_router)
    app.include_router(voice_router)
    app.include_router(ws_router)

    from vibecheck.push import PushManager, attach_bridge, set_push_manager

    push_manager = PushManager()
    set_push_manager(push_manager)
    app.state.push_manager = push_manager

    import vibecheck.bridge as bridge_module

    bridge_module.session_manager.add_bridge_hook(attach_bridge)

    static_dir = resolve_static_dir()
    assets_dir = static_dir / "assets"
    icons_dir = static_dir / "icons"

    @app.get("/assets/{asset_path:path}", include_in_schema=False)
    async def assets(asset_path: str):
        if not assets_dir.exists():
            raise HTTPException(status_code=404, detail="Not Found")
        return static_file(_safe_join(assets_dir, asset_path))

    @app.get("/icons/{icon_path:path}", include_in_schema=False)
    async def icons(icon_path: str):
        if not icons_dir.exists():
            raise HTTPException(status_code=404, detail="Not Found")
        return static_file(_safe_join(icons_dir, icon_path))

    @app.get("/static/{static_path:path}", include_in_schema=False)
    async def static_files(static_path: str):
        if not static_dir.exists():
            raise HTTPException(status_code=404, detail="Not Found")
        return static_file(_safe_join(static_dir, static_path))

    @app.get("/", include_in_schema=False)
    async def root():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return static_file(index_file)
        return JSONResponse({"name": "vibecheck", "status": "ok"})

    @app.get("/manifest.json", include_in_schema=False)
    async def manifest():
        return static_file(static_dir / "manifest.json")

    @app.get("/sw.js", include_in_schema=False)
    async def service_worker():
        return static_file(static_dir / "sw.js")

    return app
