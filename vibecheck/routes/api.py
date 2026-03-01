from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi import Request
from pydantic import BaseModel

from vibecheck.bridge import SessionBridge, session_manager

router = APIRouter()
logger = logging.getLogger(__name__)


def _audit_notification_log(message: str, *args: object) -> None:
    logger.warning(message, *args)

    debug_value = os.getenv("VIBECHECK_DEBUG", "").strip().lower()
    debug_enabled = debug_value in {"1", "true", "yes", "on", "debug"}
    if not debug_enabled:
        return

    try:
        rendered = message % args if args else message
    except Exception:
        rendered = f"{message} {' '.join(str(arg) for arg in args)}"

    audit_path_value = os.getenv("VIBECHECK_NOTIFICATION_AUDIT_LOG", "/tmp/vibecheck-notification.log").strip()
    if not audit_path_value:
        return

    try:
        audit_path = Path(audit_path_value)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now(timezone.utc).isoformat()} {rendered}\n")
    except Exception:
        logger.exception("failed to write notification audit log")


class ApproveRequest(BaseModel):
    call_id: str
    approved: bool
    edited_args: dict | None = None


class InputResponseRequest(BaseModel):
    request_id: str
    response: str


class MessageRequest(BaseModel):
    content: str


class AutoApproveRequest(BaseModel):
    enabled: bool


class NotificationClickTelemetryRequest(BaseModel):
    stage: str
    source: str = ""
    session_id: str = ""
    detail: str = ""
    url: str = ""


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


@router.post("/api/telemetry/notification-click")
async def notification_click_telemetry(body: NotificationClickTelemetryRequest) -> dict[str, str]:
    _audit_notification_log(
        "notification click telemetry stage=%s source=%s session=%s detail=%s url=%s",
        body.stage.strip() or "unknown",
        body.source.strip(),
        body.session_id.strip(),
        body.detail.strip(),
        body.url.strip(),
    )
    return {"status": "ok"}


@router.post("/api/sessions/{session_id}/approve")
async def approve(session_id: str, body: ApproveRequest, request: Request) -> dict[str, str]:
    action = request.headers.get("X-Vibecheck-Notification-Action")
    source = request.headers.get("X-Vibecheck-Notification-Source")
    source_header = (request.headers.get("X-Vibecheck-Approval-Source") or "").strip()
    from_notification = bool(action or source)

    approval_source = "api"
    if source_header:
        approval_source = source_header
    if from_notification:
        approval_source = "notification"

    if from_notification:
        _audit_notification_log(
            "notification approval request session=%s call_id=%s approved=%s action=%s source=%s",
            session_id,
            body.call_id,
            body.approved,
            action or "",
            source or "",
        )

    bridge = _session_or_404(session_id)
    if not bridge.resolve_approval(
        call_id=body.call_id,
        approved=body.approved,
        edited_args=body.edited_args,
        source=approval_source,
    ):
        if from_notification:
            _audit_notification_log(
                "notification approval outcome session=%s call_id=%s status=missing",
                session_id,
                body.call_id,
            )
        raise HTTPException(status_code=404, detail=f"No pending approval for call_id={body.call_id}")
    if from_notification:
        _audit_notification_log(
            "notification approval outcome session=%s call_id=%s status=ok",
            session_id,
            body.call_id,
        )
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


@router.post("/api/sessions/{session_id}/auto-approve")
async def auto_approve(session_id: str, body: AutoApproveRequest) -> dict[str, object]:
    bridge = _session_or_404(session_id)
    bridge.set_auto_approve(body.enabled)
    return {"status": "ok", "auto_approve": bridge.auto_approve}


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
