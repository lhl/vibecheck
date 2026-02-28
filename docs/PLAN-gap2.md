# Gap 2 Fix: Phone-Injected Prompts Visible in TUI

> **Status:** Nice-to-have. Not required for Phase 3.1 acceptance.
> **Current state:** Documented known limitation. Phone user sees everything; terminal omits phone-originated user bubbles.

## Problem

Vibe's `EventHandler.handle_event()` no-ops on `UserMessageEvent` because the TUI mounts the widget before `act()`. Phone-injected messages via `bridge.inject_message()` skip that mount, so the terminal shows agent output but not the originating prompt — "ghost conversations."

## Proposed Fix

1. **Add explicit remote user-message rendering in `tui_bridge.py`.**
   - On raw `UserMessageEvent`: run normal `_dispatch(event)` first (preserves Vibe's `finalize_streaming()` behavior ordering), then mount the synthetic user bubble via callback.

2. **Wire a mount callback from `launcher.py`.**
   - `VibeCheckApp` provides `mount_user_message(content: str)` to `TuiBridge` at construction (in `on_mount`).
   - Uses Vibe's `UserMessage` widget + `_mount_and_scroll()` (or public equivalent).
   - TuiBridge holds only the callable, not an app reference.

3. **Local-prompt dedupe guard (FIFO one-shot queue, not set-based).**
   - `_handle_agent_loop_turn()` calls `inject_message()` first, then marks the **rendered** prompt (after `_render_path_prompt`) by appending to a FIFO queue on TuiBridge **only if inject succeeds**. No mark on failure = no rollback path needed.
   - `TuiBridge` on raw `UserMessageEvent`: peeks the front of the queue — if content matches, pop and skip mount; otherwise mount the bubble (phone-originated).
   - FIFO one-shot avoids mis-skipping repeated identical prompts (set-based matching would swallow duplicates).
   - Safe because `inject_message()` is synchronous (queues only); the raw `UserMessageEvent` won't arrive until `act()` runs asynchronously, so there's no race between inject and mark.

4. **Keep current raw-event tee path intact.** No upstream Vibe patching needed.

5. **Update docs after ship.**
   - Remove Gap 2 known limitation from `README.md`.
   - Update `scripts/manual-test/manual-test.howto.md` S6 expectations.

## Key Design Constraints (from review)

1. **FIFO one-shot, not set-based.** Repeated identical prompts are a real scenario (e.g., user retries). A set would mis-skip the second one. A queue pops on first match only.
2. **Mark the rendered prompt.** The mark must be placed after `_render_path_prompt()` (launcher.py:224), not on raw input, because the raw `UserMessageEvent` from `act()` contains the rendered content.
3. **Mark only on inject success.** Only append to the FIFO queue if `inject_message()` returns `True`. No mark on failure = no stale dedupe state, no rollback path. (Supersedes earlier "rollback on failure" design — same invariant, simpler code.)
4. **Bound the FIFO queue** (`maxlen=32`) and emit a `logger.debug` on queue overflow, so stale-mark issues are diagnosable in production logs.
5. **Dispatch-then-mount ordering.** `_dispatch(event)` runs first on every raw event (including `UserMessageEvent`) to preserve Vibe's `finalize_streaming()` cleanup. The synthetic user bubble mount happens after dispatch returns.

## Pre-implementation Checklist

Before coding, verify these against the Vibe source:

- [x] Exact user message widget class name and import path — **confirmed:** `UserMessage` widget, mount via `await app._mount_and_scroll(UserMessage(content))` (per Vibe source review)
- [x] `_mount_and_scroll()` existence, owner (app vs container), and signature — **confirmed:** method on VibeApp, accepts a widget instance. Local UI path uses it in `VibeApp._handle_user_message()`
- [ ] `act()` preserves verbatim submitted content in yielded `UserMessageEvent` (content-based dedupe depends on this)
- [ ] Async safety: confirm `on_bridge_raw_event` runs on the Textual event loop (same asyncio loop), not a worker thread — determines whether mount callback needs `call_from_thread()`

## Tests

1. TuiBridge mounts a user bubble for raw `UserMessageEvent` when not locally marked.
2. TuiBridge skips mount when prompt was locally marked (no duplicate).
3. `VibeCheckApp._handle_agent_loop_turn()` marks local prompt before `inject_message()`.
4. TuiBridge handles `UserMessageEvent` gracefully when mount callback is `None`.
5. No mark on inject failure — if `inject_message()` returns `False`, no mark is added and the next remote `UserMessageEvent` is not swallowed.
6. Repeated identical local prompts each render exactly once (proves FIFO one-shot, not set-based dedup).

## Acceptance Criteria

1. Phone-injected prompt appears as user bubble in TUI within the same turn.
2. Local typed prompt still shows exactly one user bubble.
3. Scenario 6 in manual run becomes strict pass (no "known limitation" fallback).
