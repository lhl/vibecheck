from __future__ import annotations

from datetime import datetime, timedelta

from vibecheck.notifications.manager import IntensityManager


def test_intensity_manager_filters_events_and_respects_snooze() -> None:
    now = [datetime(2026, 2, 28, 7, 30, 0)]
    manager = IntensityManager(now_fn=lambda: now[0])

    assert manager.level == 2
    assert manager.should_notify("approval") is True
    assert manager.should_notify("user_input") is True
    assert manager.should_notify("error") is True
    assert manager.should_notify("progress") is False

    manager.level = 4
    assert manager.should_notify("progress") is True

    manager.snooze("30m")
    assert manager.should_notify("progress") is False
    assert manager.should_notify("approval") is True

    now[0] += timedelta(minutes=31)
    assert manager.should_notify("progress") is True


def test_intensity_manager_escalates_idle_messages_by_level() -> None:
    now = [datetime(2026, 2, 28, 12, 0, 0)]
    manager = IntensityManager(level=4, now_fn=lambda: now[0])
    manager.mark_idle()

    now[0] += timedelta(minutes=5)
    assert manager.get_idle_message() == ("💤 Vibe Check", "Agent idle for 5min")
    assert manager.get_idle_message() is None

    now[0] += timedelta(minutes=5)
    assert manager.get_idle_message() == ("😐 Vibe Check", "Still waiting on you...")

    now[0] += timedelta(minutes=5)
    assert manager.get_idle_message() == ("🫠 Vibe Check", "Your agent is getting lonely")

    now[0] += timedelta(minutes=15)
    assert manager.get_idle_message() is None

    manager.level = 5
    title, body = manager.get_idle_message() or ("", "")
    assert title.startswith("💀")
    assert "30" in body


def test_intensity_manager_snooze_until_morning_rolls_forward() -> None:
    now = [datetime(2026, 2, 28, 9, 0, 0)]
    manager = IntensityManager(level=4, now_fn=lambda: now[0])

    manager.snooze("morning")
    assert manager.snooze_until == datetime(2026, 3, 1, 8, 0, 0)
    assert manager.should_notify("idle") is False

    now[0] = datetime(2026, 3, 1, 8, 0, 1)
    assert manager.should_notify("idle") is True

