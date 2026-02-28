from __future__ import annotations

from collections import deque
import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TuiBridge:
    """Adapts SessionBridge events to a Textual-style event handler."""

    def __init__(
        self,
        event_handler: Any,
        *,
        loading_state_getter: Callable[[], bool] | None = None,
        loading_widget_getter: Callable[[], Any] | None = None,
        mount_user_message: Callable[[str], object] | None = None,
    ) -> None:
        self._event_handler = event_handler
        self._loading_state_getter = loading_state_getter or (lambda: False)
        self._loading_widget_getter = loading_widget_getter or (lambda: None)
        self._mount_user_message = mount_user_message
        self._local_user_message_marks: deque[str] = deque(maxlen=32)

    def mark_local_user_message(self, content: str) -> None:
        if not content.strip():
            return

        if (
            self._local_user_message_marks.maxlen is not None
            and len(self._local_user_message_marks) >= self._local_user_message_marks.maxlen
        ):
            # `deque(maxlen=...)` auto-drops the oldest entry on overflow; we log for observability.
            logger.debug("Local user message mark queue overflow; dropping oldest entry")

        self._local_user_message_marks.append(content)

    def _raw_user_message_content(self, event: object) -> str | None:
        if not type(event).__name__.endswith("UserMessageEvent"):
            return None
        if not hasattr(event, "message_id"):
            return None
        content = getattr(event, "content", None)
        return content if isinstance(content, str) else None

    async def _dispatch(self, event: object) -> None:
        handle_event = getattr(self._event_handler, "handle_event", None)
        if not callable(handle_event):
            raise TypeError("event_handler must define a callable handle_event(event, **kwargs)")

        maybe_awaitable = handle_event(
            event,
            loading_active=self._loading_state_getter(),
            loading_widget=self._loading_widget_getter(),
        )
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    async def on_bridge_event(self, event: object) -> None:
        await self._dispatch(event)

    async def on_bridge_raw_event(self, event: object) -> None:
        await self._dispatch(event)
        content = self._raw_user_message_content(event)
        if content is None or self._mount_user_message is None:
            return

        if self._local_user_message_marks and self._local_user_message_marks[0] == content:
            self._local_user_message_marks.popleft()
            return

        try:
            maybe_awaitable = self._mount_user_message(content)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        except Exception:
            logger.exception("Failed to mount user message bubble in TUI")
