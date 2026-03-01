# Planned Future Work (Post-Hackathon)

This document captures legitimate follow-ups identified during Phase 7 session work (WU-23/WU-24: session picker + resume/diffs). These items are intentionally **out of scope for the hackathon deliverable**, but worth tracking for a production-hardening pass.

## P1 — Turn cancellation semantics + UX (deferred)

- **Decision:** Defer the Send/Cancel toggle and `/api/sessions/{id}/cancel` endpoint until we need stronger interruption guarantees or true token-stream UX.
- **Why defer now:**
  - We already stream events to the PWA over WebSocket, but managed turns are started with `enable_streaming=False`, so we are not exposing token-by-token assistant streaming to the client.
  - The bridge suppresses chunk-style assistant events when message observer wiring is active, so there is no visible partial-token stream for the user to stop mid-output.
  - A naive cancel implementation looks simple but has lifecycle edge cases (pending approval/input futures, local callback tasks, queue drain, and state consistency).
- **Current implication:** Cancel is not a critical UX requirement for "stop visible stream" right now, but remains a valid future control for long or hung turns.

### When we pick this up

- **Backend scope:**
  - Add `SessionBridge.cancel_turn()` with explicit, tested behavior:
    - cancel active turn worker task,
    - settle/cancel pending approval and input paths safely,
    - drain queued messages for the current turn policy,
    - transition bridge state to `idle` and broadcast state change.
  - Add `POST /api/sessions/{session_id}/cancel` (PSK-protected).
- **Frontend scope:**
  - InputBar Send/Cancel toggle based on agent state (`running` => Cancel).
  - Ensure keyboard and voice-submit paths are cancel-aware (not just button label swap).
  - Handle pending approval/input UI cleanup semantics on cancel.
- **Test scope:**
  - API coverage for cancel endpoint: idle no-op, running cancel, unknown session, PSK enforcement.
  - Bridge-level cancellation tests: worker cancellation, pending cleanup, queue behavior, and state event correctness.
  - Frontend tests for render toggle and cancel request behavior.

### Design constraints to decide first

- **Soft vs hard cancel contract:** `asyncio` cancellation is cooperative; it does not guarantee immediate termination of blocking tool operations or external subprocesses.
- **"Anywhere/anytime full cancel" requires runtime support:** true hard-interrupt semantics likely need deeper Vibe/tool-runner integration beyond bridge task cancellation.
- **Queue policy:** define whether cancel drops only the active turn or also clears queued turns.

## P1 — Session resume “atomic switch” semantics (failure paths)

- **Problem:** If `/api/sessions/{id}/resume` succeeds but the subsequent `/api/sessions` refresh fails (or remains stale), the frontend can remain connected to the prior session’s WebSocket while `sessionId` changes. Any resume backlog then risks being merged into the wrong timeline.
- **Desired behavior:** Treat resume as an atomic switch:
  - disconnect the old socket immediately,
  - only connect/merge backlog after confirming the resumed session is connectable,
  - surface a clear error state if refresh/reconnect fails (and do not merge backlog).
- **Possible approaches:**
  - Make `refreshSessions()` return success/failure and gate the rest of `resumeSession()` on success.
  - Add a `connectSocket({ force: true })`/bypass for a just-resumed session (using resume response payload as the source of truth).
  - Add explicit “resuming…” UI state that blocks timeline mutations until the switch completes.

## P2 — Session discovery + polling performance

- **Problem:** Session discovery currently relies on scanning session directories (reading `meta.json`) frequently (e.g., via session existence checks). As historical sessions grow, this becomes a bottleneck.
- **Problem:** Session list polling (frontend) can trigger backend work that reads entire `messages.jsonl` files to compute message counts/recency; this scales poorly.
- **Possible approaches:**
  - Cache discovery results with a short TTL (e.g., ~5s) and/or invalidate on write.
  - Cache computed session stats (message count, last activity) in memory with TTL.
  - Persist lightweight summary fields into `meta.json` as messages append (counts, last_activity_ts), avoiding full-file reads.
  - When reading text logs, use context managers and defensive decoding (e.g., `errors="replace"`).

## P2 — Diffs endpoint payload size / leakage controls

- **Problem:** `/api/sessions/{id}/diffs` currently includes full `before`/`after` contents even when the UI primarily renders unified diffs.
- **Risks:** Large payloads, slower mobile render, and unintentional content exposure.
- **Possible approaches:**
  - Add size caps and truncation indicators.
  - Add query params for output shape (e.g., `?format=unified` or `?include_contents=false`).
  - Paginate diffs and/or allow fetching a single diff by id.

## P3 — Frontend diffs fetch N+1 (ToolCall cards)

- **Problem:** Each `ToolCallCard` independently fetches the full diffs list, which can produce an N+1 request pattern when many cards render.
- **Possible approaches:**
  - Shared cache/store for diffs per session (fetch once, reuse).
  - Fetch diffs only on-demand (when a card expands) with a shared request de-dupe.

## P3 — Async file I/O + minor leak cleanups (backend bridge)

- **Problem:** Blocking filesystem reads (`Path.read_text()`) occur in async paths, which can add latency under load.
- **Problem:** Pending tool-call file-read state can linger if a tool call never completes (minor memory leak).
- **Problem:** Minor hygiene items (e.g., stdlib imports inside hot methods).
- **Possible approaches:**
  - Wrap blocking reads in `asyncio.to_thread()` or precompute diffs out-of-band.
  - Add cleanup on session end / disconnect / timeouts for pending reads.
  - Move imports (e.g., `difflib`) to module top-level.

## P3 — Origin-aware user bubble rendering (Gap 2 hardening)

- **Context:** WU-35 mounts a `UserMessage` widget in the Textual TUI on raw Vibe `UserMessageEvent` so phone-originated prompts are visible, with a FIFO *content-based* one-shot dedupe queue to avoid double-mounting locally-typed prompts.
- **Problem:** Content-only dedupe can suppress the wrong user bubble if a phone-originated prompt has the same rendered content as the next locally-marked prompt and the phone turn’s raw `UserMessageEvent` is processed first (rare, but possible during queue interleaving).
- **Possible approaches:**
  - Track turn origin at enqueue time (e.g., extend `SessionBridge.inject_message(..., origin=Literal["tui","remote"])` or use a task-local `contextvar`), and store queued turns as structured payloads instead of raw strings.
  - Expose current-turn origin to the TUI bridge (e.g., `TuiBridge(..., origin_getter=Callable[[], str | None])` or pass metadata alongside raw events).
  - Gate mounting on origin, not content: `origin=="tui"` → skip mount (Vibe already mounted), `origin=="remote"` → mount bubble.
- **Tests to add:**
  - Two queued turns with identical content (`"X"`) where the first is `remote` and second is `tui`: TUI mounts the first bubble and skips the second without relying on content matching.
  - Phone prompts still mount even when identical to the most recent local prompt.

## P4 — Misc cleanup / robustness

- Remove duplicated light-theme CSS blocks in the frontend if still present.
- Refactor tests that rely on `chdir` + relative paths to use `tmp_path` absolute paths (more robust in parallel runs).
