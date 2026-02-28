from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Literal

IntensityLevelName = Literal["chill", "vibing", "dialed_in", "locked_in", "ralph"]


class IntensityManager:
    """Controls notification aggressiveness (Chill → Ralph)."""

    LEVELS: dict[int, IntensityLevelName] = {
        1: "chill",
        2: "vibing",
        3: "dialed_in",
        4: "locked_in",
        5: "ralph",
    }

    _ALWAYS_NOTIFY: frozenset[str] = frozenset({"approval", "user_input", "error"})

    def __init__(self, *, level: int = 2, now_fn: Callable[[], datetime] | None = None) -> None:
        self._now_fn = now_fn or datetime.now
        self.level = int(level)
        self.snooze_until: datetime | None = None
        self.idle_since: datetime | None = None
        self._idle_notified: set[int] = set()

    def _now(self) -> datetime:
        return self._now_fn()

    def should_notify(self, event_type: str) -> bool:
        """Return True if the event type should emit a push notification."""
        normalized = event_type.strip().lower()
        if not normalized:
            return False

        if normalized in self._ALWAYS_NOTIFY:
            return True

        now = self._now()
        if self.snooze_until is not None and now < self.snooze_until:
            return False

        level = int(self.level)
        match level:
            case 1 | 2:
                return False
            case 3:
                return normalized in {"task_complete", "idle"}
            case 4:
                return normalized in {"task_complete", "idle", "progress"}
            case 5:
                return True
            case _:
                return False

    def mark_idle(self) -> None:
        now = self._now()
        if self.idle_since is None:
            self.idle_since = now
        self._idle_notified.clear()

    def mark_active(self) -> None:
        self.idle_since = None
        self._idle_notified.clear()

    def get_idle_message(self) -> tuple[str, str] | None:
        """Return the next escalating idle message once per threshold."""
        if self.idle_since is None:
            return None

        now = self._now()
        if self.snooze_until is not None and now < self.snooze_until:
            return None

        minutes = int((now - self.idle_since).total_seconds() // 60)
        if minutes < 5:
            return None

        level = int(self.level)
        allowed_thresholds: tuple[int, ...]
        if level == 3:
            allowed_thresholds = (5,)
        elif level == 4:
            allowed_thresholds = (5, 10, 15)
        elif level >= 5:
            allowed_thresholds = (5, 10, 15, 30)
        else:
            return None

        for threshold in allowed_thresholds:
            if minutes < threshold:
                continue
            if threshold in self._idle_notified:
                continue
            self._idle_notified.add(threshold)
            return self._idle_copy(threshold, minutes)

        return None

    def _idle_copy(self, threshold: int, minutes: int) -> tuple[str, str]:
        match threshold:
            case 5:
                return ("💤 Vibe Check", "Agent idle for 5min")
            case 10:
                return ("😐 Vibe Check", "Still waiting on you...")
            case 15:
                return ("🫠 Vibe Check", "Your agent is getting lonely")
            case _:
                shown = max(threshold, minutes)
                return ("💀 Vibe Check", f"HELLO? Agent idle for {shown}min")

    def snooze(self, duration: str) -> datetime:
        """Snooze non-critical notifications."""
        now = self._now()
        value = duration.strip().lower()
        match value:
            case "30m":
                until = now + timedelta(minutes=30)
            case "1h":
                until = now + timedelta(hours=1)
            case "morning" | "until_morning" | "until-am" | "untilam":
                until = now.replace(hour=8, minute=0, second=0, microsecond=0)
                if until <= now:
                    until = until + timedelta(days=1)
            case _:
                raise ValueError(f"unknown snooze duration: {duration}")

        self.snooze_until = until
        return until

