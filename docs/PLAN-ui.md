# vibecheck — UI/UX Plan

> **Status:** Design spec for Phase 7 FE polish. Guides WU-23 implementation.
> **Last updated:** 2026-02-28

---

## Layout Structure

Fixed viewport PWA layout with three zones. No page-level scroll — each zone manages its own overflow.

```
┌─────────────────────────────────┐
│  HEADER (sticky top)            │
│  logo + connection + session    │
├─────────────────────────────────┤  ← header bottom edge
│                                 │
│  MESSAGE LOG (scrollable)       │
│  fills remaining vertical space │
│  overflow-y: auto               │
│  overflow-x: hidden / wrap      │
│                                 │
├─────────────────────────────────┤
│  MESSAGE INPUT (sticky bottom)  │
│  textarea + send button         │
├─────────────────────────────────┤
│  STATUS LINE (footer)           │
│  YOLO toggle / intensity / cost │
└─────────────────────────────────┘
```

Full height = `100dvh` (dynamic viewport height for mobile browser chrome). Layout via flexbox column, message log gets `flex: 1` with `min-height: 0` to shrink properly.

---

## Header

**Default (collapsed):**
- vibecheck pixel-art logo (left)
- Active session label: title or first 8 chars of UUID (e.g. `b8b6aa96…`) (center/left)
- Connection status indicator (right): dot + label (green=connected, red=disconnected, yellow=reconnecting)
- Tap anywhere on header to expand

**Expanded (session picker):**
- Slides open below header bar
- Lists active sessions (controllable=true), sorted reverse-chron by `started_at`
- Each row: title (or "New session"), session ID prefix (`b8b6aa96…`), relative age, status badge
- Attention icon on `waiting_approval` / `waiting_input` sessions
- "Browse older sessions" collapsible section for non-active sessions
- Tap a session to switch; picker collapses
- Tap header bar again to collapse without switching

---

## Message Log

**Layout:**
- `flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden`
- Content wraps within the viewport width — no horizontal scroll
- Wide content (code blocks, tool output) gets `overflow-x: auto` on the individual card, not the whole log
- `word-break: break-word` on message text to prevent blowout

**Auto-scroll behavior** (existing):
- Auto-scroll to bottom on new messages when user is near bottom
- "New messages ↓" button when scrolled up (already implemented)

**Content types rendered:**
- Assistant messages (markdown)
- User messages
- Tool call cards (collapsible)
- Tool result cards
- Approval request cards
- Input request cards

---

## Message Input (Footer Top)

**Layout:**
- Pinned to bottom of message log area
- Mic icon (left side, hold-to-record — no timer display, just icon state change while recording)
- Textarea (center, auto-grow to ~3 lines max, then scroll internally)
- Send / Cancel button (right side, context-dependent)
- Auto-translate toggle (inline, existing)

**Behavior:**
- Enter to send (shift+enter for newline)
- **Voice auto-submit:** after mic release → transcribe → auto-send the transcribed text (no manual send step)
- **Send/Cancel toggle:** button shows "Send" when idle. When agent is running (`state=running`), button becomes "Cancel" (red) — cancels the active agent turn via `asyncio.CancelledError` on the run task. Needs `POST /api/sessions/{id}/cancel` endpoint (cancels `_run_agent_turn` task on the bridge).
- Disabled state when not connected or no session selected
- Clear after send

---

## Status Line (Footer Bottom)

The bottom-most bar of the app. Compact single-line strip.

**Default content:**
- Left: agent state (e.g. "idle", "running", "waiting approval") — this is session/agent state, NOT connection state (connection lives in header top-right)
- Right: token/cost counter (e.g. "$0.42 | 12K tokens") — always visible, updates in real time

**Interactive elements:**
- Tap to expand status panel (or long-press for YOLO toggle)
- YOLO mode toggle: hidden by default, revealed via status line interaction. When active, pulsing visual indicator + "YOLO" badge
- Future: intensity level, snooze controls (deferred)

---

## Notification / Alert Overlay

For approval requests and input questions that need immediate attention.

**Layout:**
- Full-width modal overlay
- Top edge starts below header bar (doesn't cover header)
- Full remaining height
- Semi-transparent backdrop: `rgba(0,0,0,0.7)` — blocks interaction with message log and input
- Alert card(s) stack from the top of the overlay area

**Behavior:**
- Triggered when session enters `waiting_approval` or `waiting_input`
- Cannot type or send messages while overlay is active (input is behind the shim)
- Approve/Deny buttons (for approval) or response input (for questions) are in the overlay card
- Overlay dismisses when approval/input is resolved
- Multiple pending alerts stack vertically (rare but possible)

**Alert card content:**
- Tool name + args summary (for approvals)
- Question text + options (for input requests)
- Approve / Deny buttons (large, touch-friendly)
- Haptic feedback on appearance: `navigator.vibrate(200)`

---

## Talker Mode (L7 Stretch)

Full voice conversation loop: speak to your agent, hear it respond. Activated from the input bar mic icon. Requires ElevenLabs TTS backend (WU-29/30).

**Activation:**
- **Tap mic** = toggle talker mode on/off
- **Hold mic** = one-shot voice input (existing behavior: record → transcribe → auto-send)
- Mic icon changes appearance when talker mode is active (e.g. filled/pulsing vs outline)

**Talker mode ON — input bar transforms:**

```
┌─────────────────────────────────────────┐
│  🎙  LISTENING...  (pulsing)        [✕] │
└─────────────────────────────────────────┘
```

- Replaces textarea + send button with voice state indicator
- X button exits talker mode, restores normal input bar
- Message log stays visible and updates as conversation flows

**State cycle:**
```
listening → transcribing → agent running → speaking (TTS) → listening → ...
```

- **Listening**: mic active, pulsing indicator, capturing audio
- **Transcribing**: mic off, spinner, Voxtral STT processing
- **Agent running**: transcribed text auto-sent, waiting for response (message log updates in real time)
- **Speaking**: ElevenLabs TTS plays agent response aloud, speaker icon animates
- **→ Listening**: auto-cycles back after TTS finishes, ready for next turn

**Interrupts:**
- Tap voice area during speaking → stop TTS playback, return to listening
- Approval/input request → notification overlay takes over as normal, talker mode pauses
- After approval resolved → talker mode resumes
- Cancel button (if agent running) → same as text mode cancel

**What stays the same:**
- Message log keeps updating — user sees transcribed bubbles + agent text responses
- Header, status line, notification overlay all work normally
- Cost ticker updates in real time

**What changes:**
- Input bar replaced by voice state UI
- Agent responses auto-play as TTS audio (ElevenLabs)
- No manual typing while in talker mode (exit to type)

---

## Dark / Light Theme

- CSS custom properties for all colors
- Default: follow `prefers-color-scheme`
- Manual toggle in header or status line
- Key tokens: `--bg`, `--bg-card`, `--text`, `--text-muted`, `--accent`, `--border`, `--danger`, `--success`
- Mistral brand colors preserved for accent/highlights regardless of theme

---

## Known Issues to Fix

- [ ] Wide content (long code lines, URLs) breaks horizontal layout — needs `overflow-x: auto` on cards, `word-break` on text
- [ ] Message input not locked to bottom on iOS Safari (keyboard push behavior)
- [ ] No visual distinction between active/stale sessions in picker
- [ ] Raw UUID shown as session label — needs title + ID prefix

---

## Mobile Considerations

- Touch targets: minimum 44x44px for all interactive elements
- Safe area insets: `env(safe-area-inset-*)` for notch/home indicator
- `100dvh` not `100vh` to handle mobile browser chrome
- Keyboard: `visualViewport` API to handle virtual keyboard resize
- Pull-to-refresh: disabled (`overscroll-behavior: none` on body)
