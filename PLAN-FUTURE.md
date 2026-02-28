# vibecheck — Future Work

This file tracks non-blocking improvements that were intentionally *not* implemented in the initial hackathon pass.

## Origin-aware user bubble rendering (Gap 2 hardening)

**Context:** WU-35 fixed “phone prompts visible in TUI” by mounting a `UserMessage` widget on raw Vibe `UserMessageEvent` and using a FIFO *content-based* one-shot dedupe queue to avoid double-mounting locally-typed prompts.

**Remaining edge case:** content-only dedupe can suppress the wrong user bubble if a phone-originated prompt has the same rendered content as the next locally-marked prompt and the phone turn’s raw `UserMessageEvent` is processed first (rare, but possible during queue interleaving).

### Proposed change

Replace content-based dedupe with **origin-aware gating**:

1. Track turn origin at enqueue time:
   - Extend `SessionBridge.inject_message(..., origin=Literal["tui","remote"])`.
   - TUI path (`VibeCheckApp._handle_agent_loop_turn`) uses `origin="tui"`.
   - REST path (`POST /api/sessions/{session_id}/message`) uses `origin="remote"`.
2. Store queued turns as a structured payload (e.g. `QueuedTurn(content, origin)`), not raw strings.
3. Expose current-turn origin to the TUI bridge:
   - Option A: `TuiBridge(..., origin_getter=Callable[[], str | None])`.
   - Option B: call raw listeners with metadata (`listener(raw_event, origin=...)`) and update the type/uses accordingly.
4. In `TuiBridge.on_bridge_raw_event`:
   - If `origin == "tui"` and raw event is `UserMessageEvent`: **skip mount** (Vibe already mounted it).
   - If `origin == "remote"` and raw event is `UserMessageEvent`: **mount bubble**.

This removes ambiguity when identical prompt strings occur across surfaces.

### Tests to add

- Two queued turns with identical content (`"X"`) where the first is `remote` and second is `tui`:
  - TUI should mount the first bubble (remote) and skip the second (tui) without relying on content matching.
- Ensure local-typed prompts still mount exactly once (no duplicate).
- Ensure phone prompts still mount even when identical to the most recent local prompt.

