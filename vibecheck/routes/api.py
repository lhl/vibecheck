from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from vibecheck.bridge import SessionBridge, session_manager

router = APIRouter()


class ApproveRequest(BaseModel):
    call_id: str
    approved: bool
    edited_args: dict | None = None


class InputResponseRequest(BaseModel):
    request_id: str
    response: str


class MessageRequest(BaseModel):
    content: str


def _session_or_404(session_id: str) -> SessionBridge:
    if session_manager.has_known_session(session_id):
        return session_manager.attach(session_id)
    raise HTTPException(status_code=404, detail=f"Unknown session: {session_id}")


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/state")
async def fleet_state() -> dict[str, int]:
    return session_manager.fleet_status()


@router.get("/api/sessions")
async def list_sessions() -> list[dict]:
    return session_manager.list()


@router.get("/api/sessions/{session_id}/state")
async def session_state(session_id: str) -> dict:
    bridge = _session_or_404(session_id)
    return bridge.state_payload()


@router.get("/api/sessions/{session_id}")
async def session_detail(session_id: str) -> dict:
    try:
        return session_manager.session_detail(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown session: {session_id}") from exc


@router.post("/api/sessions/{session_id}/approve")
async def approve(session_id: str, body: ApproveRequest) -> dict[str, str]:
    bridge = _session_or_404(session_id)
    if not bridge.resolve_approval(
        call_id=body.call_id,
        approved=body.approved,
        edited_args=body.edited_args,
    ):
        raise HTTPException(status_code=404, detail=f"No pending approval for call_id={body.call_id}")
    return {"status": "ok"}


@router.post("/api/sessions/{session_id}/input")
async def input_response(session_id: str, body: InputResponseRequest) -> dict[str, str]:
    bridge = _session_or_404(session_id)
    if not bridge.resolve_input(request_id=body.request_id, response=body.response):
        raise HTTPException(status_code=404, detail=f"No pending input for request_id={body.request_id}")
    return {"status": "ok"}


@router.post("/api/sessions/{session_id}/message")
async def message(session_id: str, body: MessageRequest) -> dict[str, str]:
    bridge = _session_or_404(session_id)
    if not bridge.inject_message(body.content):
        raise HTTPException(
            status_code=503,
            detail="Vibe runtime unavailable; message was not forwarded to AgentLoop",
        )
    return {"status": "queued"}


@router.post("/api/sessions/{session_id}/resume")
async def resume_session(session_id: str) -> dict:
    try:
        session_manager.resume(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown session: {session_id}") from exc
    return session_manager.session_detail(session_id)


@router.get("/api/sessions/{session_id}/diffs")
async def session_diffs(session_id: str) -> list[dict]:
    bridge = _session_or_404(session_id)
    return bridge.diffs_payload()
