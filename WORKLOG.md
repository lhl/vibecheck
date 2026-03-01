# vibecheck — Worklog

## 2026-03-01

### Scope decision: defer cancellation feature to future work

- Deferred implementation of Send/Cancel toggle and `POST /api/sessions/{session_id}/cancel` from current hackathon scope.
- Added a dedicated deferred-work section in `docs/PLAN-FUTURE.md`:
  - documented current behavior (WebSocket event streaming exists, but managed runs are not token-streamed to client),
  - captured why cancellation is lower priority right now for UX,
  - outlined future backend/frontend/test scope for a robust cancel feature,
  - called out soft-cancel vs hard-cancel constraints and required runtime/tooling decisions.

### Push notification action tracing (Android Approve/Deny diagnostics)

- Added client-side notification action tracing in `vibecheck/frontend/src/App.svelte`:
  - stores bounded trace entries in localStorage key `vibecheck_notification_trace`,
  - records action flow stages (`received`, `resolved_session`, `approve_request`, `approve_ok`, error/skip reasons),
  - includes action/source/session/call-id metadata to diagnose misrouted Approve/Deny taps.
- Added global debug helper in browser runtime:
  - `window.__vibecheckNotificationTrace.dump()`
  - `window.__vibecheckNotificationTrace.clear()`
  - `window.__vibecheckNotificationTrace.enableConsole()` / `disableConsole()`
- Added notification metadata headers on approval REST calls:
  - `X-Vibecheck-Notification-Action`
  - `X-Vibecheck-Notification-Source`
- Added service-worker source tagging in `vibecheck/frontend/public/sw.js`:
  - posts `source: "sw_notificationclick"` with `notification_action` messages,
  - adds `notif_source=sw_notificationclick` when opening a new client window.
- Added backend correlation log in `vibecheck/routes/api.py` for `/approve` when debug headers are present.
- Added frontend tests in `vibecheck/frontend/src/App.test.js`:
  - explicit service-worker **approve** path asserts `approved: true` + debug headers + trace entry,
  - explicit service-worker **deny** path asserts `approved: false` + debug headers + trace entry.
- Verification:
  - `cd vibecheck/frontend && npm test -- src/App.test.js` -> pass.
  - `uv run pytest vibecheck/tests/test_api.py -v` -> pass.
  - `cd vibecheck/frontend && npm run build` -> pass.

### Approval logs visible in `vibecheck-vibe` mode

- Updated `/api/sessions/{session_id}/approve` logging in `vibecheck/routes/api.py` from `info` to `warning` for notification-originated actions so logs are visible when running `uv run vibecheck-vibe` (uvicorn `warning` log level).
- Added explicit warning outcome logs for notification approvals:
  - `status=ok` when pending approval resolves
  - `status=missing` when call id is not pending (404 path)
- Added backend tests in `vibecheck/tests/test_api.py`:
  - `test_approve_logs_notification_request_and_success_outcome`
  - `test_approve_logs_notification_missing_outcome`
- Verification:
  - `uv run pytest vibecheck/tests/test_api.py -v` -> pass.

### Notification approval audit file fallback

- Added `_audit_notification_log()` in `vibecheck/routes/api.py` for notification approval request/outcome lines.
- The helper still emits `logger.warning(...)`, and also appends plain-text audit lines to:
  - `/tmp/vibecheck-notification.log` by default, or
  - path from `VIBECHECK_NOTIFICATION_AUDIT_LOG` when set.
- This bypasses full-screen TUI logging visibility issues so notification taps can be diagnosed from a stable file.
- Added backend coverage in `vibecheck/tests/test_api.py`:
  - `test_approve_writes_notification_audit_file`.
- Verification:
  - `uv run pytest vibecheck/tests/test_api.py -v` -> pass.

### Notification action triage + approval source tagging

- Added approval resolution source tagging end-to-end:
  - `ApprovalResolutionEvent` now includes optional `source`,
  - `SessionBridge.resolve_approval(..., source=...)` forwards source into backlog/websocket events,
  - local/TUI callback path tags approvals as `tui_local`,
  - API path accepts `X-Vibecheck-Approval-Source` and tags event source (e.g., `pwa_ui`),
  - frontend in-app approval posts `X-Vibecheck-Approval-Source: pwa_ui`.
- Switched push approval notifications to **regular open-app notifications** (no inline Approve/Deny actions):
  - removed `actions` + `call_id` from approval push payload in `vibecheck/push.py`,
  - updated service worker click behavior in `vibecheck/frontend/public/sw.js`:
    - cache bump to `v4`,
    - focus/navigate existing app window or open app URL,
    - carry only `notif_source` deep-link context.
- Added launcher debug flags for runtime notification diagnostics:
  - `uv run vibecheck-vibe --debug [--log-file /path/to/log]`,
  - `--debug` enables audit file writing,
  - `--log-file` selects destination; default remains `/tmp/vibecheck-notification.log`.
- Updated tests:
  - backend: source tagging + debug/audit + payload shape assertions,
  - launcher: parse + env wiring for `--debug`/`--log-file`,
  - frontend: approval panel header source assertion.
- Verification:
  - `uv run pytest vibecheck/tests/test_api.py vibecheck/tests/test_push.py vibecheck/tests/test_bridge.py vibecheck/tests/test_launcher.py -q` -> pass.
  - `cd vibecheck/frontend && npm test -- src/App.test.js src/components/ApprovalPanel.test.js` -> pass.
  - `cd vibecheck/frontend && npm run build` -> pass.

### Frontend scroll fix: wide output horizontal pan

- Updated chat stream container to allow horizontal overflow (`.timeline { overflow-x: auto; }`) while keeping viewport lock (`html/body` + shell remain overflow-hidden) in `vibecheck/frontend/src/App.svelte`.
- Added regression coverage in `vibecheck/frontend/src/App.test.js` to assert the stream CSS keeps horizontal scrolling enabled for wide content.
- Tightened chat message test coverage in `vibecheck/frontend/src/components/ChatMessage.test.js` to ensure rendered code blocks sit inside `.message-body`.
- Verification:
  - `cd vibecheck/frontend && npm test -- src/App.test.js src/components/ChatMessage.test.js` -> pass.
  - `cd vibecheck/frontend && npm run build` -> pass.

## 2026-02-28

### Phase 7 planning + UI design spec

- Defined visual aesthetic: terminal-native dark theme (dark grey bg, hairline borders, JetBrains Mono everywhere, Mistral flame gradient accents, byobu-style segmented status bar, YOLO mode inverse yellow banner)
- Created `docs/PLAN-ui.md` — full PWA layout spec for Phase 7 polish:
  - Fixed viewport layout: header (sticky top), message log (flex scroll), input bar (sticky bottom), status line (footer)
  - Header: logo + session label + connection status (top-right), expands to session picker on tap
  - Session picker: active sessions (controllable=true) sorted reverse-chron, title + ID prefix + age + attention icon
  - Input bar: mic icon (left, hold=one-shot, tap=talker mode), textarea (center), send/cancel toggle (right)
  - Status line: agent state (bottom-left), token/cost ticker (bottom-right, tap while running → big overlay)
  - Notification overlay: 70% alpha shim below header, blocks input, stacks approval/question cards
  - Talker mode (L7 stretch): tap mic toggles voice loop, input bar transforms to voice UI, TTS auto-plays responses
  - Dark/light theme, mobile considerations (100dvh, safe areas, 44px touch targets)
- Updated `docs/PLAN.md`:
  - Session picker redesign spec (active=controllable, title from meta.json, attention badges)
  - YOLO mode + live cost ticker as active L9 scope
  - Camera/vision prototype cross-referenced in L8
  - Explicit Deferred section with full specs: settings panel (intensity/snooze), diff viewer, offline cache, rate limiting, replay mode, confetti, live demo mode, QR code, per-tool trust levels
- Updated `docs/IMPLEMENTATION.md`:
  - WU-23: session picker redesign, dark theme, error/loading states, haptics
  - WU-24: expose title from meta.json, resume + diff endpoints
  - L8: camera/vision prototype cross-reference
  - L9: YOLO mode + cost ticker specs, deferred items synced with PLAN.md
- Created pixel-art PWA icon: 10×10 grid SVG with 5 Mistral-colored stripes + white checkmark, rendered to 192×192 and 512×512 PNGs

### Phase 7 polish — sessions (WU-24/WU-23)

- Backend (WU-24):
  - `GET /api/sessions` now exposes `title` from `meta.json` (trimmed to 50 chars).
  - Added `POST /api/sessions/{session_id}/resume` to reattach a managed bridge to past sessions and return backlog.
  - Added `GET /api/sessions/{session_id}/diffs` to return before/after + unified diffs for `write_file`/`search_replace` tool calls observed by the bridge.
  - Added test coverage in `vibecheck/tests/test_sessions.py`.
- Frontend (WU-23):
  - Replaced raw UUID dropdown with structured active/older session lists (active = `controllable=true`, older sessions behind a `<details>` expando).
  - Added session resume button (calls `/resume`) and auto-selects the newest active session on launch.
  - Added theme preference persistence (`auto`/`dark`/`light`) + wired the UI to CSS variables; tightened component styling to use the shared tokens.
  - Added haptic feedback on approval request (`navigator.vibrate(200)`).
  - Updated frontend tests (`vibecheck/frontend/src/App.test.js`) to cover “New session” title fallback.
- Verification:
  - `uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test && npm run build` -> pass.

### Phase 6 follow-up review remediation
- Fixed **High**: push notification actions now call-bound — payload includes `call_id`, SW threads it through to App.svelte, which uses it directly instead of fetching `/state` for "whatever is currently pending". Stale notifications can no longer approve the wrong tool call.
- Fixed **Medium**: idle escalation now tracks all waiting sessions via `set[str]` instead of a single `_idle_session_id` slot. Concurrent sessions all receive escalation pushes.
- Fixed **Low**: MicButton `onDestroy` now calls `stopRecording()` to release mic/tracks if component unmounts during recording.
- Fixed **Low**: STT and translate routes wrap Mistral SDK calls in `asyncio.wait_for` (30s / 15s respectively) and return HTTP 504 on timeout.
- Fixed FE error UX: ChatMessage and ApprovalPanel now extract JSON `{detail}` from error responses (was showing raw `statusText`).
- Fixed push notification action handling for already-open clients: App now listens for Service Worker `message` events (`client.postMessage`) in addition to URL `?action=` params (`vibecheck/frontend/src/App.svelte`, `vibecheck/frontend/src/App.test.js`).
- **Decision**: PSK-in-query-param for REST routes intentionally kept for dev convenience; documented in `docs/PLAN.md` with production hardening note.
- Test suite: 116 backend (+3 new: call_id in push payload, multi-session idle, STT/translate timeout), 60 frontend, build OK.
- Updated `docs/REVIEW-phase6.md` fix status and remaining items.

### Docs: running instructions
- Updated `README.md` to add a **Running** section + refresh Quick Start (PSK requirement, `uv run vibecheck-vibe`, state-check curl commands).
- Tweaked server-only instructions to build the frontend in a subshell so the subsequent `uv run python -m vibecheck` runs from the repo root.
- Updated `docs/DEMO.md` to reference `vibecheck-vibe` (instead of `vibe`) and clarify the EC2 “server running” check.
- Updated `docs/PLAN.md` to mark Layer 1 + 1.5 bridge items as complete (`[x]`).

### Launcher defaults: port + model
- `vibecheck-vibe` now defaults to port `7870` (no need to pass `--ws-port` unless overriding).
- `vibecheck-vibe` now loads `~/.vibe/.env` (matching Vibe CLI) and prefers Vibe's `devstral-2` (Mistral API) when `MISTRAL_API_KEY` is present, unless `VIBE_ACTIVE_MODEL` is explicitly set.
- Updated `README.md`, `docs/DEMO.md`, and `scripts/manual-test/` docs to omit `--ws-port 7870` and document the model preference.
- Tests: `uv run pytest vibecheck/tests/ -v` → **119 passed**

### PWA chat: suppress streamed assistant chunk bubbles
- Fixed: PWA was showing a stray first-token assistant bubble ("Under" → "Understood...") because we were broadcasting streamed `AssistantEvent` chunks in addition to the final aggregated message.
- Bridge now suppresses raw `AssistantEvent`/`UserMessageEvent` yields when message observer is available, keeping middleware STOP messages intact (`vibecheck/bridge.py`).
- Fixed: message observer chaining now uses bound-method equivalence checks (instead of `is`) to avoid double-invoking the same observer in some setups (`vibecheck/bridge.py`).
- Tests: `uv run pytest vibecheck/tests/ -v` → **122 passed**

### TUI stability: mobile-first message context crash
- Fixed `LookupError: active_app` crash in Textual markdown rendering when the first prompt comes from mobile (REST) instead of TUI.
- Root cause: `SessionBridge` message worker task captured the context of whichever surface sent the first message; mobile-first created the worker outside Textual context, so raw event-driven UI mounts failed.
- Added `SessionBridge.prime_message_worker()` and now call it during `VibeCheckApp.on_mount()` so the worker is created in Textual context before mobile traffic (`vibecheck/bridge.py`, `vibecheck/launcher.py`).
- Added launcher regression test for worker priming (`vibecheck/tests/test_launcher.py`).
- Verification:
  - `uv run pytest vibecheck/tests/test_launcher.py vibecheck/tests/test_bridge.py vibecheck/tests/test_tui_bridge.py -v` -> pass.
  - `uv run pytest vibecheck/tests/ -v` -> **121 passed**.

### Repository setup
- Created `vibecheck` repo
- Created README.md (full product brief)
- Created docs/PLAN.md (L0-L9 layer architecture, parallel tracks, tech stack)
- Created docs/IMPLEMENTATION.md (WU-01 through WU-27, dependency graph, testing strategy, directory structure)
- Created docs/DEMO.md, docs/ANALYSIS-vibe.md, docs/USING-VIBE.md, docs/TODO.md
- Created docs/REMOTING-UI.md (mobile-to-TUI bridge research)
- Updated AGENTS.md/CLAUDE.md with correct `docs/` paths for all key files
- All cross-links verified (README ↔ docs/PLAN ↔ docs/IMPLEMENTATION)

### Reviewer 2 - Phase 0 audit (Vibe/Devstral)
- Reviewed WU-01/WU-02 scaffold output against `docs/IMPLEMENTATION.md` and `REVIEW-PROCESS.md`
- Executed verification checks (`npm run build`, pytest run, runtime API probe)
- Added findings and capability assessment to `docs/VIBE-REVIEW.md`
- Confirmed blockers: HTTP auth bypass, broken backend test fixture setup, and process non-compliance on commit/worklog hygiene

### Phase 0 punchlist reset (WU-01/WU-02)
- Updated `docs/IMPLEMENTATION.md` WU-01 to enforce strict PSK policy (`VIBECHECK_PSK` required, no default)
- Updated WU-01 route contract to `WS /ws/events/{session_id}` and session-id REST placeholders
- Updated WU-01 verification commands to explicit `export VIBECHECK_PSK=dev`, targeted auth tests, and full-suite gate
- Updated WU-02 mobile acceptance note to target 360px–428px phone widths and retained explicit frontend build gate

### Documentation consistency pass (README → PLAN → IMPLEMENTATION)
- Normalized session storage path references to `~/.vibe/logs/session/` across planning docs
- Standardized REST and WS route parameter naming to `{session_id}` across examples and WU specs
- Updated stale endpoint examples (`/api/approve`, `/api/input`, `/api/message`) to session-scoped paths
- Standardized status wording to `disconnected` (replacing mixed `detached` usage in API planning text)

### Phase 0 implementation (WU-01 + WU-02) redo
- Rebuilt Phase 0 from scratch in a clean tree using tests-first flow:
  - Added `vibecheck/tests/conftest.py` and `vibecheck/tests/test_auth.py` before implementation.
  - Confirmed red state first (`ModuleNotFoundError: No module named 'vibecheck'`) using `uv run --with ... pytest`.
- Implemented backend scaffold (`WU-01`) with root-level `pyproject.toml` and importable `vibecheck/` package:
  - Added FastAPI app factory (`vibecheck/app.py`) with CORS, lifespan hook, API/WS router mounting.
  - Added strict PSK middleware (`vibecheck/auth.py`) with fail-fast `VIBECHECK_PSK` requirement and timing-safe compare.
  - Added stub REST routes (`vibecheck/routes/api.py`) and WS scaffold (`vibecheck/ws.py`) with connect event + 30s heartbeat.
  - Added runtime entrypoint (`vibecheck/__main__.py`) for `uv run python -m vibecheck`.
- Implemented frontend scaffold (`WU-02`) via `npm create vite@latest vibecheck/frontend -- --template svelte`:
  - Configured `vite.config.js` proxy (`/api`, `/ws`) to `localhost:7870` and build output to `../static`.
  - Replaced default app with mobile shell layout in `src/App.svelte` (safe-area insets, 44px targets, dark theme vars).
  - Added PWA files (`public/manifest.json`, `public/sw.js`) and registered SW in `src/main.js`.
  - Generated placeholder icons: `public/icons/vibe-192.png` and `public/icons/vibe-512.png`.
- Updated ignore policy:
  - Added `vibecheck/frontend/node_modules/` and `vibecheck/static/` to root `.gitignore`.
- Verification results:
  - `uv run pytest vibecheck/tests/test_auth.py -v` -> 6 passed.
  - `uv run pytest vibecheck/tests/ -v` -> 6 passed.
  - Backend smoke: `uv run python -m vibecheck` + `curl` checks (`/api/health` 200, `/api/state` with PSK 200, without PSK 401).
  - Frontend: `cd vibecheck/frontend && npm install && npm run build` succeeded; output in `vibecheck/static/`.
  - Frontend dev probe: `npm run dev` served on `:5173` and responded to `curl`.

### Reviewer 2 - Phase 0 reimplementation audit
- Reviewed commit `baf0fa0` and re-ran claimed verification commands:
  - `uv run pytest vibecheck/tests/test_auth.py -v` -> 6 passed
  - `uv run pytest vibecheck/tests/ -v` -> 6 passed
  - `cd vibecheck/frontend && npm run build` -> success
- Ran additional integration checks against backend-hosted frontend assets/PWA files.
- Logged findings in `docs/VIBE-REVIEW.md`: quality is improved, but backend static mount currently breaks root asset and PWA paths (`/assets/*`, `/manifest.json`, `/sw.js`, `/icons/*` returning 404).

### Reviewer 2 - static/PWA routing fix verification
- Reviewed commit `9be9622` (`fix: serve frontend PWA assets from backend root`).
- Re-ran claimed validations:
  - `uv run pytest vibecheck/tests/test_static_frontend.py -v` -> passed
  - `uv run pytest vibecheck/tests/test_auth.py -v` -> 6 passed
  - `uv run pytest vibecheck/tests/ -v` -> 7 passed
- Reproduced runtime smoke with backend server:
  - `/`, `/assets/index-*.js`, `/manifest.json`, `/sw.js`, `/icons/vibe-192.png` all returned 200
  - `/api/state` with PSK returned 200; without PSK returned 401
- Appended acceptance follow-up notes to `docs/VIBE-REVIEW.md`.

### Phase 2 implementation (WU-09 to WU-12)
- Implemented typed event models in `vibecheck/events.py` and added round-trip/validation coverage in `vibecheck/tests/test_events.py`.
- Built out `SessionBridge`/`SessionManager` in `vibecheck/bridge.py` with:
  - per-session state, pending approval/input futures, backlog cap, and session discovery from `~/.vibe/logs/session/`
  - fleet aggregation and session detail helpers for API consumers
- Replaced stub API routes with real session-backed endpoints in `vibecheck/routes/api.py`:
  - `GET /api/state`, `GET /api/sessions`, `GET /api/sessions/{session_id}`, `GET /api/sessions/{session_id}/state`
  - `POST /api/sessions/{session_id}/approve|input|message`
- Reworked WebSocket manager in `vibecheck/ws.py`:
  - session rooms (`rooms`, `socket_to_session`) with `connect` auth, `disconnect`, `broadcast`, `broadcast_all`, `send_personal`
  - connect flow sends `connected` + `state` + backlog, plus 30s heartbeat task
  - teardown hardened so heartbeat-task failures/cancellation do not skip disconnect cleanup
- Expanded API/WS/bridge tests:
  - `vibecheck/tests/test_api.py`
  - `vibecheck/tests/test_ws.py`
  - `vibecheck/tests/test_bridge.py`
- Updated auth state assertions in `vibecheck/tests/test_auth.py` to match dynamic session discovery (`/api/state` values are non-negative ints, not hardcoded zeros).
- Verification:
  - `uv run pytest vibecheck/tests/test_events.py -v` -> passed
  - `uv run pytest vibecheck/tests/test_bridge.py -v` -> passed
  - `uv run pytest vibecheck/tests/test_api.py -v` -> passed
  - `uv run pytest vibecheck/tests/test_ws.py -v` -> passed
  - `uv run pytest vibecheck/tests/ -v` -> passed (34 tests)
  - backend smoke: `uv run python -m vibecheck` + `curl http://127.0.0.1:7870/api/health` returned `{"status":"ok"}`

### Live Vibe tap probe script (external process reality check)
- Added `scripts/probe_live_vibe_session.py` to probe a real session log under `~/.vibe/logs/session/` and print:
  - discovered target session metadata
  - parsed last-N events (`user_message`, `assistant`, `tool_call`, `tool_result`)
  - optional short tail window for new live log lines
  - explicit capability verdict that callback control cannot be attached from an external running `vibe` process
- Added reusable probe helpers in `vibecheck/live_probe.py` and test coverage in `vibecheck/tests/test_live_probe.py`.
- Verification:
  - `uv run pytest vibecheck/tests/test_live_probe.py -v` -> passed
  - `uv run pytest vibecheck/tests/ -v` -> passed (38 tests)
  - `uv run python scripts/probe_live_vibe_session.py --tail-seconds 3 --show-last 4` -> passed against live session logs

### Session attachment deep-dive analysis
- Added `docs/ANALYSIS-session-attachment.md` to clarify the distinction between:
  - discovery/observe-only attach
  - replay/resume attach (new loop from history)
  - true live attach to the same already-running terminal process
- Documented current constraints of in-process callback wiring (`set_approval_callback`, `set_user_input_callback`) and why unmanaged external `vibe` processes are not automatically controllable.
- Added recommended roadmap clarifications, attach-mode capability contract, incremental implementation plan, and validation criteria for the "coffee-walk control" promise.

### CRITICAL: Architecture gap identified — bridge creates new AgentLoop, cannot attach to running Vibe
- **Problem:** Phase 2's `SessionBridge` creates its own `AgentLoop` via `_ensure_agent_loop()`. It cannot control an already-running Vibe terminal process. Vibe has zero IPC — `set_approval_callback()` and `set_user_input_callback()` are in-process method calls, not network endpoints. The product promise ("run Vibe in terminal, control from phone") was impossible with the Phase 2 architecture.
- **Analysis:** Evaluated four architecture options:
  - **Option A: Managed startup** — vibecheck replaces vibe. Works but users lose Vibe's Textual TUI (rich tool approval dialogs, streaming output, syntax highlighting). This is what Phase 2 builds. Not acceptable because the UX promise requires terminal + mobile.
  - **Option B: Sidecar injection into Vibe's entry point** — `vibecheck-vibe` wraps Vibe's CLI. Same process runs Textual TUI + FastAPI/WebSocket server. One shared AgentLoop. **SELECTED.**
  - **Option C: tmux/PTY sidecar** — Terminal scraping. Fragile (heuristic parsing, keystroke simulation, state drift). Used by Happy and other Claude Code remoting apps — their UX shows the limitations. **Fallback only.**
  - **Option D: Upstream ACP** — Vibe's `resume_session()` is `NotImplemented`. Not viable for hackathon timeline.
- **Key architectural insight from Vibe source analysis:** In `vibe/cli/cli.py`, the flow is: create `AgentLoop` (line ~190) → pass to `run_textual_ui(agent_loop=agent_loop)` (line ~203). The TUI and AgentLoop are independent objects. Textual is built on asyncio. We can run uvicorn alongside it as a Textual worker in the same event loop.
- **Decision:** Option B primary, Option C fallback. User confirmed.

### Phase 3 (Live Attach) inserted into planning docs
- **`docs/ANALYSIS-session-attachment.md`** — Complete rewrite replacing colleague's initial draft. Now contains:
  - Problem statement (Vibe has no IPC)
  - Three attachment modes (observe-only, replay/resume, live attach)
  - Four architecture options with honest tradeoffs
  - Decision rationale (Option B primary, Option C fallback)
  - Detailed Option B architecture: single asyncio loop, bridge owns AgentLoop, event tee pattern, dual input, approval flow
  - Session API contract with `attach_mode` values
  - Acceptance test definition
  - Risk/mitigation table
- **`docs/PLAN.md`** — Updated:
  - Architecture diagram: now shows `vibecheck-vibe` with terminal + phone as parallel surfaces
  - Inserted Layer 1.5 (Live Attach) between L1 and L2
  - Updated dependency graph: L1.5 is prerequisite for all higher layers
  - Updated parallelism map: added L1.5 row (backend-only)
  - Updated Track A: added L1.5 entry
  - Fixed "In-process vs sidecar?" open question to reference Option B
- **`docs/IMPLEMENTATION.md`** — Major restructure:
  - Inserted new **Phase 3: Live Attach (L1.5)** with four work units:
    - WU-25: Bridge `attach_to_loop()` — wire callbacks on existing AgentLoop, add `attach_mode` field
    - WU-26: Event tee + TUI bridge rendering — `TuiBridge` adapter, event fan-out to TUI + WebSocket
    - WU-27: VibeCheckApp + launcher — Textual subclass, uvicorn as worker, `vibecheck-vibe` entry point
    - WU-28: Live attach integration test — mocked AgentLoop, real FastAPI, acceptance test
  - Renumbered all subsequent phases: Phase 3→4, 4→5, 5→6, 6→7, 7→8
  - Renumbered stretch WUs to avoid collision: WU-25→29, WU-26→30, WU-27→31
  - Updated: ToC, dependency graph, constraints table, WU table, parallelism map, directory structure
  - Added new files to directory structure: `tui_bridge.py`, `launcher.py`, `test_tui_bridge.py`, `test_launcher.py`, `test_live_attach.py`
- All 44 existing tests pass after changes (doc-only commit, no code changes).

### Reviewer 2 + Reviewer 3 findings on Phase 3 doc insertion
- Fixed 7 findings from Reviewer 2 and additional feedback from Reviewer 3:
  1. **Blocker fixed:** Normalized `act()` ownership — bridge is sole consumer in all modes (live + managed). Removed contradictory "TUI drives act() initially" language from IMPLEMENTATION.md.
  2. **High fixed:** Integration/deploy steps now reference `vibecheck-vibe` as primary startup path, with `python -m vibecheck` as standalone fallback.
  3. **High fixed:** Clarified discovered sessions are `observe_only` — live control requires sessions started via `vibecheck-vibe`. Added explicit notes in PLAN.md (L1 SessionManager, Open Questions) and IMPLEMENTATION.md (WU-12).
  4. **Medium fixed:** Gate labels corrected — Integration #1 says "after L1.5 + L2", stretch WUs reference Phase 5 gate.
  5. **Medium fixed:** Added `controllable` property alongside `attach_mode` in PLAN.md and IMPLEMENTATION.md — derived from mode, used by frontend to show/hide controls.
  6. **Medium fixed:** Normalized approval surface — both TUI keyboard and mobile REST can resolve pending approvals (first response wins). Per Reviewer 3: this is required for "go back and forth" UX, not stretch.
  7. **Low fixed:** Updated WU range from WU-27 to WU-31 in README.md and AGENTS.md.
- Added explicit Textual + uvicorn spike step in WU-27 (highest technical risk).
- Files changed: `docs/ANALYSIS-session-attachment.md`, `docs/PLAN.md`, `docs/IMPLEMENTATION.md`, `README.md`, `AGENTS.md`

### Phase 3 implementation (WU-25 to WU-28)
- Implemented live-attach bridge capabilities in `vibecheck/bridge.py`:
  - Added `attach_to_loop(agent_loop, vibe_runtime)` for wiring callbacks/message observer onto an existing AgentLoop.
  - Added `attach_mode` (`live|managed|observe_only|replay`) and derived `controllable` property on `SessionBridge`.
  - Added bridge event listeners (`add_event_listener` / `remove_event_listener`) and fan-out so bridge events can tee to multiple consumers.
  - Extended state/session payloads to include `attach_mode` and `controllable`.
  - Updated `SessionManager.attach()` mode selection: discovered sessions default to `observe_only`; unmanaged new sessions default to `managed`.
- Added `vibecheck/tui_bridge.py` with `TuiBridge` adapter (`on_bridge_event`) to forward bridge events to Textual-style `handle_event(...)`.
- Added `vibecheck/launcher.py` and `VibeCheckApp`:
  - Launcher parses `--ws-port`, builds AgentLoop from Vibe runtime, attaches bridge in `live` mode, and runs TUI app.
  - `VibeCheckApp` starts uvicorn server worker with `log_level=\"warning\"` and routes TUI turn handling through `bridge.inject_message()` so bridge remains sole `act()` consumer.
- Registered CLI entrypoint in `pyproject.toml`:
  - `[project.scripts] vibecheck-vibe = "vibecheck.launcher:launch"`.
- Added Phase 3 tests:
  - `vibecheck/tests/test_tui_bridge.py`
  - `vibecheck/tests/test_launcher.py`
  - `vibecheck/tests/test_live_attach.py`
  - Expanded `vibecheck/tests/test_bridge.py` for live attach behavior and attach-mode semantics.
- Added `scripts/test_live_attach.sh` smoke/integration script.
- Verification run:
  - `uv run pytest vibecheck/tests/test_bridge.py vibecheck/tests/test_tui_bridge.py vibecheck/tests/test_launcher.py vibecheck/tests/test_live_attach.py -v` -> passed.
  - `uv run pytest vibecheck/tests/ -v` -> 54 passed.
  - `scripts/test_live_attach.sh` -> passed.
  - `uv run python -m vibecheck` startup smoke + `curl /api/health` -> `{\"status\":\"ok\"}`.

### Phase 3 reviewer feedback fixes (callback ownership + raw event tee)
- Addressed Reviewer 1/2 blocker on callback ownership in `vibecheck/launcher.py`:
  - `VibeCheckApp.on_mount()` now rebinds bridge callbacks after `super().on_mount()`.
  - Added callback interceptors on `agent_loop.set_approval_callback` / `set_user_input_callback` so future rebinds (including agent switches) keep bridge ownership while preserving TUI callbacks as local fallback resolvers.
- Addressed event type mismatch for TUI tee:
  - Added raw event listener channel in `SessionBridge` (`add_raw_event_listener`, `_notify_raw_event_listeners`).
  - `_run_agent_turn()` now fans out raw AgentLoop events to raw listeners before conversion for WebSocket payloads.
  - `VibeCheckApp` now connects TUI bridge via raw channel, so Textual `EventHandler` receives upstream Vibe event objects.
- Hardened bridge callback orchestration:
  - Added optional local callback racing in `SessionBridge` so local TUI approval/input callbacks can resolve the same pending futures (first response wins behavior).
  - Extended message observer wiring to also patch `agent_loop.messages._observer` when present.
  - Replaced silent listener exception swallowing with logger-backed exceptions.
- Hardened launcher lifecycle:
  - Added uvicorn server handle tracking and graceful `should_exit` signaling on unmount.
  - `_handle_agent_loop_turn()` now surfaces failed bridge injection via TUI notification.
  - `_build_agent_loop()` now accepts a `message_observer` parameter; launcher bootstrap uses bridge observer at loop construction.
- Updated `scripts/test_live_attach.sh` to smoke the launcher entry point (`uv run vibecheck-vibe --help`) in addition to integration and backend startup checks.
- Added/expanded tests for fixes:
  - `test_bridge.py`: raw event listener path + local callback resolution path.
  - `test_tui_bridge.py`: raw event forwarding.
  - `test_launcher.py`: message observer forwarding and callback rebind/interceptor behavior.
- Verification run after fixes:
  - `uv run pytest vibecheck/tests/ -v` -> 59 passed.
  - `scripts/test_live_attach.sh` -> passed.

### Phase 3 reviewer follow-up fixes (mobile-first race + method matching)
- Fixed mobile-first resolution race in `vibecheck/bridge.py`:
  - Removed cancellation of local callback tasks after REST resolution.
  - Added local callback state settlement helpers to resolve Vibe TUI pending futures safely:
    - `_settle_local_approval_state(...)` sets `_pending_approval` result when mobile resolves first.
    - `_settle_local_input_state(...)` sets `_pending_question` result when mobile resolves first.
  - Wired settlement into `resolve_approval(...)` and `resolve_input(...)`.
- Fixed interceptor bound-method comparison in `vibecheck/launcher.py`:
  - Added `_callbacks_match(...)` helper using `__func__` + `__self__` semantics instead of identity-only `is`.
  - Prevents self-referential local fallback assignment when callback passed is bridge callback.
- Strengthened test coverage:
  - Added `test_mobile_resolution_does_not_leave_local_pending_state_stuck` in `vibecheck/tests/test_bridge.py`.
  - Extended launcher callback interception test in `vibecheck/tests/test_launcher.py` to assert bridge callback re-registration does not overwrite local fallback callbacks.
- Improved `scripts/test_live_attach.sh` smoke flow:
  - Added launcher wiring smoke test (`test_on_mount_rebinds_callbacks_and_intercepts_future_rebinds`) so the script now exercises callback interception behavior, not only `--help`.
- Verification run after follow-up:
  - `uv run pytest vibecheck/tests/test_bridge.py vibecheck/tests/test_launcher.py vibecheck/tests/test_tui_bridge.py -v` -> passed.
  - `scripts/test_live_attach.sh` -> passed.
  - `uv run pytest vibecheck/tests/ -v` -> 60 passed.

### Phase 3 race-window hardening (late local task start)
- Closed the remaining late-start window in `vibecheck/bridge.py`:
  - `_resolve_with_local_approval(...)` now returns immediately if `tool_call_id` is no longer pending.
  - `_resolve_with_local_input(...)` now returns immediately if `request_id` is no longer pending.
- Added regression tests in `vibecheck/tests/test_bridge.py`:
  - `test_late_local_approval_task_skips_after_mobile_resolution`
  - `test_late_local_input_task_skips_after_mobile_resolution`
  - Both tests delay local callback task start and verify no stuck local pending future after mobile-first resolution.
- Verification:
  - `uv run pytest vibecheck/tests/test_bridge.py vibecheck/tests/test_launcher.py vibecheck/tests/test_tui_bridge.py -v` -> passed.
  - `scripts/test_live_attach.sh` -> passed.
  - `uv run pytest vibecheck/tests/ -q` -> 62 passed.

### Phase 3.1 (TUI Integration Hardening) — planning inserted
- **Source:** External reviewer validated Option B approach and identified three TUI integration gaps that unit tests cannot catch (they require the real Vibe Textual app).
- **Gap 1 (High):** TUI stuck in approval/question widget after mobile resolves. Our `_settle_local_approval_state()` resolves the asyncio Future but doesn't trigger Vibe's Textual UI cleanup (`on_approval_app_*` handlers). The approval widget stays mounted, input area stays hidden.
- **Gap 2 (Medium):** Mobile-injected prompts invisible in TUI. Vibe's `EventHandler.handle_event()` intentionally no-ops on `UserMessageEvent` because the TUI mounts the widget before `act()`. Phone-injected messages skip that mount → "ghost conversations" in terminal.
- **Gap 3 (Medium):** `_handle_agent_loop_turn` override drops loading widget lifecycle, Ctrl+C interrupt behavior, and history refresh. Queue serialization replaces `_agent_running` guard (equivalent), but the other losses are visible.
- **Docs updated:**
  - `docs/ANALYSIS-session-attachment.md` — Added "Phase 3 Validation: Confirmed Gaps" section with full technical detail and Vibe source references
  - `docs/PLAN.md` — Added Phase 3.1 status note under L1.5 with summary of all three gaps
  - `docs/IMPLEMENTATION.md` — Inserted Phase 3.1 with WU-32 (approval UI cleanup, M), WU-33 (remote injection UX + lifecycle audit, S), WU-34 (manual validation with real Vibe, S). Updated ToC, dependency graph, WU table, key constraints, parallelism map, and Phase 5 gate dependencies.

### Phase 3.1 implementation (WU-32 + WU-33 documentation pass)
- Implemented explicit local TUI cleanup hook in `vibecheck/bridge.py`:
  - Added `_reset_local_owner_ui(owner)` to call owner `_switch_to_input_app()` when present.
  - Wired the cleanup into both `_settle_local_approval_state(...)` and `_settle_local_input_state(...)` after future settlement.
  - Behavior is async-safe: awaitables are scheduled on the active loop and tracked with bridge background task management.
- Strengthened regression coverage in `vibecheck/tests/test_bridge.py`:
  - Extended `test_mobile_resolution_does_not_leave_local_pending_state_stuck` to assert `_switch_to_input_app()` is invoked after mobile approval/input resolution.
  - Ensures the bridge now updates both asyncio state and local TUI mode state.
- Documented WU-33 lifecycle/UX tradeoffs:
  - `README.md` now includes a "Live Attach Known Limitations (Phase 3.1)" section covering:
    - user-prompt visibility limitation for phone-injected `UserMessageEvent` in terminal TUI
    - deliberate `_handle_agent_loop_turn` lifecycle tradeoffs (loading indicator, interrupt, history refresh)
  - Added inline parity-tradeoff comment in `vibecheck/launcher.py` next to `_handle_agent_loop_turn`.
- Verification:
  - `uv run pytest vibecheck/tests/test_bridge.py::test_mobile_resolution_does_not_leave_local_pending_state_stuck -v` -> passed
  - `uv run pytest vibecheck/tests/test_bridge.py vibecheck/tests/test_launcher.py vibecheck/tests/test_tui_bridge.py vibecheck/tests/test_live_attach.py -v` -> passed (27 tests)
  - `uv run pytest vibecheck/tests/ -q` -> passed (62 tests)
  - `scripts/test_live_attach.sh` -> passed

### WU-34 manual validation harness (operator error reduction)
- Added a structured manual-test toolkit under `scripts/manual-test/`:
  - `run.sh` — interactive scenario runner for Phase 3.1/WU-34 with hard acceptance checks and per-scenario pass/fail capture.
  - `api.sh` — session API helper (state inspection, wait-for-pending, resolve approval/input, send message).
  - `tui_prompts.sh` — canonical TUI prompts for each manual scenario (approve/reject/question/race/reconnect/running).
  - `capture.sh` — starts `vibecheck-vibe` with `script` transcript capture into timestamped artifacts.
  - `README.md` — runbook for multi-terminal execution (Terminal A/B + phone).
- Added ignore rules to keep manual artifacts/secrets out of git:
  - `artifacts/manual-test/`
  - `scripts/manual-test/.env.local`
- Harness output:
  - `artifacts/manual-test/wu34-<timestamp>/results.tsv`
  - `artifacts/manual-test/wu34-<timestamp>/report.md` (commit hash, Vibe version, scenario table, pasteback summary)
- Script verification:
  - `bash -n scripts/manual-test/api.sh scripts/manual-test/run.sh scripts/manual-test/capture.sh scripts/manual-test/tui_prompts.sh`
  - `scripts/manual-test/run.sh --help`
  - `scripts/manual-test/api.sh --help`
  - `scripts/manual-test/tui_prompts.sh list`
  - `scripts/manual-test/capture.sh --help`

### WU-34 runtime preflight hardening + environment sync
- Encountered real runtime failure during manual launch: `ModuleNotFoundError: tomli_w` when loading reference Vibe modules from `reference/mistral-vibe/`.
- Installed reference Vibe package/dependencies into the active uv environment:
  - `uv pip install -e reference/mistral-vibe`
  - Verified `load_vibe_runtime()` succeeds after install.
- Hardened `scripts/manual-test/capture.sh` with a preflight runtime check:
  - Runs `load_vibe_runtime()` before starting TUI.
  - Fails fast with explicit remediation command instead of full traceback.
- Updated `scripts/manual-test/README.md` with one-time preflight/install instruction.

### WU-34 live launcher fix: unlock Vibe config paths
- Encountered runtime error on live launch:
  - `RuntimeError: Config path is locked` from `vibe/core/paths/config_paths.py` during `VibeConfig.load()`.
- Root cause:
  - `vibecheck.launcher` parsed Vibe args but did not run Vibe entrypoint `main()`, so `unlock_config_paths()` was never called.
- Fix:
  - Added `_unlock_vibe_config_paths()` in `vibecheck/launcher.py`.
  - `_build_agent_loop(...)` now calls `_unlock_vibe_config_paths()` before `runtime.vibe_config_cls.load()`.
- Added isolated regression test (without touching in-progress launcher test edits by other agent):
  - `vibecheck/tests/test_launcher_config_unlock.py::test_build_agent_loop_unlocks_vibe_config_paths`
- Verification:
  - `uv run pytest vibecheck/tests/test_launcher_config_unlock.py -v` -> passed
  - `uv run pytest vibecheck/tests/test_launcher.py::test_build_agent_loop_passes_message_observer -v` -> passed
  - real-runtime probe:
    - `uv run python -c "... _build_agent_loop(...)"` -> `ok AgentLoop`

### WU-34 docs: dedicated operator HOWTO
- Added `scripts/manual-test/manual-test.howto.md` with a clean end-to-end runbook:
  - prerequisites, runtime/network assumptions
  - exact Terminal A/B/phone commands
  - scenario coverage mapping (S1-S7)
  - artifact expectations
  - troubleshooting for common failures:
    - missing runtime deps (`tomli_w` / `vibe`)
    - stylesheet path mismatch
    - `llamacpp` connection failures when `active_model=local`
- Updated `scripts/manual-test/README.md` to point to the new HOWTO as the canonical operator guide.

### Phase 3.1 reviewer remediation (pre-WU-34 manual pass)
- Hardened callback-owner discovery in `vibecheck/bridge.py` to avoid `__self__`-only fragility:
  - Added wrapper-aware owner resolution across bound methods, `__wrapped__`, `functools.partial` (`func` / `args` / `keywords`), and closure-captured owners.
  - Cached local approval/input owner hints on callback configuration and reused them during settle paths.
  - Added warning log when a callable local callback exists but owner resolution fails at settle time.
- Reduced mobile-first ordering flake risk in local TUI reset:
  - Split reset into `_call_switch_to_input_app(...)` and `_reset_local_owner_ui(...)`.
  - `_reset_local_owner_ui(...)` now performs immediate reset plus a follow-up `asyncio.sleep(0)` reset task to win late UI-switch races.
- Restored path-prompt parity in `vibecheck/launcher.py`:
  - Added `_render_path_prompt` import fallback (safe no-op when Vibe module unavailable).
  - `_handle_agent_loop_turn(...)` now injects the rendered prompt (`render_path_prompt(prompt, base_dir=Path.cwd())`) before bridge queueing.
- Added regression coverage:
  - `test_settle_local_state_resolves_wrapped_and_partial_callbacks`
  - `test_settle_local_state_schedules_follow_up_ui_reset`
  - `test_handle_agent_loop_turn_renders_prompt_before_bridge_injection`
  - Updated launcher on-mount tests to stub `_BaseVibeApp.__init__` / `run_worker` for environment-stable isolation when real Textual `VibeApp` is importable.
- Verification:
  - `uv run pytest vibecheck/tests/test_bridge.py::test_settle_local_state_resolves_wrapped_and_partial_callbacks -q` -> passed
  - `uv run pytest vibecheck/tests/test_bridge.py::test_settle_local_state_schedules_follow_up_ui_reset -q` -> passed
  - `uv run pytest vibecheck/tests/test_launcher.py::test_handle_agent_loop_turn_renders_prompt_before_bridge_injection -q` -> passed
  - `uv run pytest vibecheck/tests/ -v` -> 65 passed

### WU-34 manual runner UX: explicit pending-clear progress and abort
- Updated `scripts/manual-test/run.sh` to replace silent `api wait-clear-*` blocking waits with `wait_for_pending_clear()`:
  - prints progress every 5s with pending id and elapsed time
  - supports `q` + Enter abort while waiting and writes a partial report
  - now used in approve/reject/question/race/reconnect scenarios
- Verification:
  - `bash -n scripts/manual-test/run.sh` -> passed
  - `scripts/manual-test/run.sh --help` -> passed

### WU-34 manual runner robustness: fix scenario-7 completion crash
- Hardened `scripts/manual-test/run.sh` `build_report()` to avoid `||` inside command substitutions:
  - `commit_hash` now falls back via explicit post-check instead of inline `||`.
  - `vibe_version` now uses `uv run python -c` capture with explicit fallback handling.
- This addresses the late-run shell error observed after Scenario 7 (`command substitution ... unexpected token '||'`).
- Verification:
  - `bash -n scripts/manual-test/run.sh` -> passed
  - `scripts/manual-test/run.sh --help` -> passed

### WU-34 completion: packaged Phase 3.1 manual validation results
- Packaged the passing run from `artifacts/manual-test/wu34-20260228-080025/results.tsv` into:
  - local artifact report: `artifacts/manual-test/wu34-20260228-080025/report.md`
  - reviewer handoff doc: `docs/reports/WU34-2026-02-28.md`
- Recorded evidence pointers:
  - scenario checklist results (`results.tsv`)
  - TUI transcript capture (`artifacts/manual-test/wu34-20260228-080013/tui-transcript.log`)
  - capture metadata (`artifacts/manual-test/wu34-20260228-080013/meta.txt`)
- Validation summary:
  - S1-S7 all passed
  - Gap 2 remained a documented known limitation (`terminal_user_bubble=no_known_limitation`)
- Artifact policy:
  - Screenshots/recordings intentionally omitted for this run; transcript + checklist evidence used.

### Phase 4 frontend core implementation (WU-13, WU-14, WU-15)
- Reworked frontend from monolithic `App.svelte` into Phase 4 architecture:
  - Added WU-13 modules:
    - `vibecheck/frontend/src/lib/ws.js` with reconnect backoff (1s -> 30s), 45s heartbeat timeout handling, JSON event ingest, and event-store dispatch.
    - `vibecheck/frontend/src/stores/connection.js` with `connected|connecting|disconnected` state + reconnect attempt tracking.
    - `vibecheck/frontend/src/stores/events.js` with 500-event FIFO cap, dedupe-by-id merge behavior, and derived stores for `messages`, `pendingApproval`, `pendingInput`, `toolCalls`, and `toolResultsByCall`.
    - `vibecheck/frontend/src/lib/auth.js` for PSK load/store/clear and URL-hash bootstrap.
  - Added WU-14 components:
    - `ConnectionStatus.svelte`
    - `ChatMessage.svelte` (assistant/user rendering + basic markdown for code blocks/inline code/bold/links)
    - `ToolCallCard.svelte` (collapsed/expanded args + result/error state)
  - Added WU-15 components:
    - `ApprovalPanel.svelte` (approve/deny POST flow + in-flight disable)
    - `InputBar.svelte` (message vs input POST routing, Enter/Shift+Enter handling, disconnected disable)
  - Replaced `vibecheck/frontend/src/App.svelte` with a store-driven shell:
    - PSK gate screen when no key is configured
    - session controls + websocket lifecycle wiring
    - chat timeline rendering from stores (messages + tool cards)
    - auto-scroll logic with user-scroll lockout and `New messages ↓` button
    - bottom composer wiring for approval/input surfaces
- Added frontend test harness and suite:
  - Updated `vibecheck/frontend/package.json` scripts/deps for `vitest`, `jsdom`, and Svelte testing library.
  - Updated `vibecheck/frontend/vite.config.js` with test environment config.
  - Added `vibecheck/frontend/src/test-setup.js`.
  - Added tests:
    - `src/lib/auth.test.js`
    - `src/lib/ws.test.js`
    - `src/stores/events.test.js`
    - `src/components/ConnectionStatus.test.js`
    - `src/components/ChatMessage.test.js`
    - `src/components/ToolCallCard.test.js`
    - `src/components/ApprovalPanel.test.js`
    - `src/components/InputBar.test.js`
    - `src/App.test.js`
- Verification:
  - `cd vibecheck/frontend && npm test` -> 9 files passed, 26 tests passed.
  - `cd vibecheck/frontend && npm run build` -> success (`vibecheck/static/` artifacts emitted).

### Phase 4 reviewer remediation (P1 + integration blockers)
- Addressed reviewer-reported Phase 4 follow-up issues in frontend core:
  - `vibecheck/frontend/src/lib/ws.js`
    - Reset `reconnectAttempts` to `0` on successful `onopen` so reconnect cycles restart at 1s backoff.
    - Added backlog-array handling in `onmessage` via `mergeEvents(...)` for reconnect payloads.
    - Filtered `heartbeat` events so they are not persisted into the 500-event FIFO store.
  - `vibecheck/frontend/src/components/InputBar.svelte`
    - Added fetch error handling (`catch`) to prevent unhandled rejections.
    - Added inline error rendering and retained draft text on failure.
  - `vibecheck/frontend/src/lib/auth.js`
    - Added session-id safe-storage helpers (`load/store/clear`) to avoid direct unsafe `localStorage` calls in app shell.
    - Added URL hash cleanup after PSK extraction (`history.replaceState`) to remove `#psk=...` from address bar/history.
  - `vibecheck/frontend/src/App.svelte`
    - Replaced direct session `localStorage` usage with auth safe wrappers.
    - Removed optimistic local `user_message` append to prevent duplicate user bubbles once WS echo arrives.
    - Reset timeline only when switching to a different session (prevents cross-session mixing without wiping same-session reconnects).
    - Stopped refresh interval on key clear and centralized refresh timer lifecycle helpers.
- Test coverage additions/updates:
  - `vibecheck/frontend/src/lib/ws.test.js`
    - reconnect reset behavior
    - heartbeat filtering
    - reconnect backlog array merge
  - `vibecheck/frontend/src/components/InputBar.test.js`
    - error path preserves draft and surfaces status
  - `vibecheck/frontend/src/App.test.js`
    - no optimistic user bubble before WS echo
    - timeline clears on session switch
  - `vibecheck/frontend/src/lib/auth.test.js`
    - hash cleanup assertion
    - session storage helper coverage
- Verification:
  - `cd vibecheck/frontend && npm test` -> 9 files passed, 33 tests passed.
  - `cd vibecheck/frontend && npm run build` -> success (`vibecheck/static/` updated).

### Phase 4 reviewer pass 2 (remaining gaps)
- Addressed remaining post-review deltas that were still valid after `cddc7de`:
  - `vibecheck/frontend/src/lib/ws.js`
    - Added terminal close-code handling for WebSocket auth/session terminal failures (`4401`, `4404`).
    - Client now stops auto-reconnect and transitions to `disconnected` immediately for terminal codes; reconnect resumes only on explicit `connect()`.
  - `vibecheck/frontend/src/components/ConnectionStatus.svelte`
    - Updated connecting label logic: `Connecting` before first retry, `Reconnecting (n)` once retries begin.
- Added regression coverage:
  - `vibecheck/frontend/src/lib/ws.test.js`
    - close-code terminal behavior coverage for `4401` and `4404`.
  - `vibecheck/frontend/src/components/ConnectionStatus.test.js`
    - first-connect `Connecting` label coverage.
- Verification:
  - `cd vibecheck/frontend && npm test` -> 9 files passed, 36 tests passed.
  - `cd vibecheck/frontend && npm run build` -> success.

### Phase 6 infra hardening (test + static serving)
- Observed upstream transport hangs when exercising streaming responses + websocket tests in-process:
  - `fastapi.testclient.TestClient` requests never completed under current dependency set (even for trivial apps).
  - `httpx.ASGITransport` similarly hung on `FileResponse` / static file streaming reads.
- Implemented stable in-process test + static behavior:
  - `vibecheck/app.py` now serves `/`, `/manifest.json`, `/sw.js`, `/assets/*`, `/icons/*` via non-streaming byte `Response` reads (plus safe path join).
  - Added `vibecheck/tests/asgi_ws.py` in-memory ASGI websocket harness.
  - Migrated `vibecheck/tests/test_ws.py` + `vibecheck/tests/test_live_attach.py` off `TestClient` to async + in-memory websocket session.
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.

### Phase 6A Voice input (WU-17 + WU-18)
- Backend (WU-17):
  - Added `POST /api/voice/transcribe` (`vibecheck/routes/voice.py`) Voxtral proxy via Mistral SDK (`audio.transcriptions.complete_async`).
  - Supports raw audio body or multipart upload; forwards `language` query param; returns `{text, language, duration_ms}`.
  - Added tests in `vibecheck/tests/test_voice.py` with mocked Mistral client.
- Frontend (WU-18):
  - Added `MicButton.svelte` hold-to-record UI + duration counter; posts blob to `/api/voice/transcribe`.
  - Added `lib/recorder.js` MediaRecorder helper and `lib/settings.js` for persisted voice language (JA/EN) selection.
  - Wired `MicButton` into `InputBar.svelte` to insert transcription into the editable draft before send.
  - Added/updated frontend tests (`MicButton.test.js`, `settings.test.js`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test` -> pass.
  - `cd vibecheck/frontend && npm run build` -> success.

### Phase 6B Push notifications (WU-19 + WU-20)
- Backend (WU-19):
  - Added VAPID key generation + persistence (`~/.vibecheck/vapid_keys.json`) and subscription persistence (`~/.vibecheck/push_subscriptions.json`).
  - Added push API routes:
    - `GET /api/push/vapid-key`
    - `POST /api/push/subscribe`
    - `POST /api/push/unsubscribe`
  - Wired bridge-level push triggers for `approval_request`, `input_request`, and error `tool_result` events.
  - Added coverage in `vibecheck/tests/test_push.py` (subscribe/unsubscribe + approval_request push trigger, mocking `pywebpush.webpush_async`).
- Frontend (WU-20):
  - Added `lib/push.js` helper for subscribe/unsubscribe (VAPID key fetch + PushManager.subscribe payload forward).
  - Updated `public/sw.js` push handler to `showNotification` with actions + `notificationclick` open/focus behavior.
  - Added notifications toggle in `App.svelte` settings and persisted enable state in `lib/settings.js`.
  - Added `lib/push.test.js` + extended `lib/settings.test.js`.
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test` -> pass.
  - `cd vibecheck/frontend && npm run build` -> success.

### Phase 6D Japanese auto-translation (WU-21)
- Backend:
  - Added `POST /api/translate` (`vibecheck/routes/translate.py`) proxying `mistral-large-latest` with a markdown/code-preserving system prompt.
  - Added `vibecheck/tests/test_translate.py` mocking Mistral and asserting prompt construction.
- Frontend:
  - Added per-message `🌐` toggle in `ChatMessage.svelte` that swaps between original and translated text.
  - Added in-memory translation cache keyed by event id (`src/lib/translate.js`) and CJK ratio skip (>30%).
  - Added persisted global auto-translate toggle in `App.svelte` + `src/lib/settings.js`.
  - Added/updated tests (`ChatMessage.test.js`, `App.test.js`, `translate.test.js`, `settings.test.js`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test` -> pass.
  - `cd vibecheck/frontend && npm run build` -> success.

### Phase 6C Smart notifications — Ministral (WU-22)
- Added `vibecheck/notifications/manager.py` (`IntensityManager`) with level filtering, snooze, and escalating idle copy logic.
- Added `vibecheck/notifications/ministral.py` helpers:
  - `generate_notification_copy()` (<=80 chars)
  - `summarize_tool_call()` (1-line)
  - `classify_urgency()` (low/normal/high)
- Wired push payload generation to use `IntensityManager` filtering and smarter approval bodies/urgency (`vibecheck/push.py`).
- Added tests:
  - `vibecheck/tests/test_intensity_manager.py`
  - `vibecheck/tests/test_ministral_notifications.py`
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.

### Phase 5 integration watch item: prompt `user_message` echo
- `SessionBridge.inject_message()` now immediately emits a `user_message` event so mobile UI can render the user's message without optimistic bubbles.
- Added lightweight content+time dedupe so a later Vibe echo (raw event or message observer) doesn't double-render the same message.
- Added test coverage in `vibecheck/tests/test_bridge.py`.
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/test_bridge.py -v` -> pass.

### Phase 6 review fixes (MicButton + dedupe)
- Fixed MicButton press/release race: releasing before `startRecording()` resolves now still triggers a stop/upload once recording starts (`vibecheck/frontend/src/components/MicButton.svelte`).
- Tightened local `user_message` dedupe:
  - Narrowed the window and scoped suppression to active turns so same-content messages from other sources are not dropped (`vibecheck/bridge.py`).
  - Added coverage for both “echo absent” and “late same-content message” cases (`vibecheck/tests/test_bridge.py`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test && npm run build` -> pass.

### Phase 6 docs reconciliation
- Updated Phase 6 review tracker with post-fix status + commit map (`docs/REVIEW-phase6.md`).
- Synced push reference doc with current SW/app action handling (no PSK in SW; action forwarded to app) and updated the “what we push” table (`docs/REFERENCE-push-notifications.md`).
- Refreshed project TODO list for current Phase 6 follow-ups (`docs/TODO.md`).

### Phase 6 review fixes (Reviewer 3 follow-ups)
- Voice:
  - Added max payload guard (`VIBECHECK_MAX_AUDIO_BYTES`, default 10MB) for both raw and multipart uploads (`vibecheck/routes/voice.py`).
  - Added oversized-payload coverage (`vibecheck/tests/test_voice.py`).
- MicButton:
  - Added `touchcancel` handling to avoid stuck recordings on interrupted touches (`vibecheck/frontend/src/components/MicButton.svelte`).
  - Added regression coverage (`vibecheck/frontend/src/components/MicButton.test.js`).
- Push:
  - App now handles push approve/deny action buttons by fetching pending approval state then POSTing `/approve` (`vibecheck/frontend/src/App.svelte` + `vibecheck/frontend/src/App.test.js`).
  - Hardened VAPID key handling: corrupt `vapid_keys.json` regenerates keys, file permissions restricted to `0600`, and VAPID `sub` claim configurable via `VIBECHECK_VAPID_SUB` (`vibecheck/push.py`, `vibecheck/tests/test_push.py`).
- Translation:
  - Added request caps + language-code validation (`MAX_TRANSLATE_CHARS`, `LANG_CODE_PATTERN`) with rejection tests (`vibecheck/routes/translate.py`, `vibecheck/tests/test_translate.py`).
- Coverage:
  - Added `/api/push/*`, `/api/translate`, `/api/voice/transcribe` to the PSK-required regression matrix (`vibecheck/tests/test_api.py`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test && npm run build` -> pass.

### Phase 6A review fixes (Recorder + voice coverage)
- Fixed `MediaRecorder.onerror` state leak so new recordings can start after an error (`vibecheck/frontend/src/lib/recorder.js`).
- Added unit coverage for recorder error recovery (`vibecheck/frontend/src/lib/recorder.test.js`).
- Added backend voice coverage for missing `MISTRAL_API_KEY`, SDKError mapping, and `_segments_duration_ms` edge cases (`vibecheck/tests/test_voice.py`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test && npm run build` -> pass.

### Phase 6C review fixes (Smart notifications)
- IntensityManager:
  - `mark_idle()` no longer clears the per-threshold dedupe set (prevents repeated idle alerts on idle heartbeats).
  - Clamp intensity level to 1–5 (covers init + runtime assignment) and route idle escalation through `should_notify("idle")`.
- Ministral helpers:
  - Truncate/compact `args` before embedding into prompts (caps prompt growth / cost).
  - Truncate long fallback tool summaries (bounds intermediate strings).
- Push:
  - Added an integration assertion that approval push bodies use `generate_notification_copy()` (`vibecheck/tests/test_push.py`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.

### Phase 6D review fixes (Translation hardening)
- Frontend:
  - Abort in-flight auto-translate requests on component destroy to avoid state updates after unmount (`vibecheck/frontend/src/components/ChatMessage.svelte`).
  - Cap translation cache to 200 entries with eviction (`vibecheck/frontend/src/lib/translate.js`).
  - Added regression coverage (`ChatMessage.test.js`, `translate.test.js`).
- Backend:
  - Expanded translate endpoint test coverage for validation, missing `MISTRAL_API_KEY`, SDKError mapping, and empty upstream output (`vibecheck/tests/test_translate.py`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test && npm run build` -> pass.

### Phase 6B review fixes (Push unsubscribe ordering)
- Fixed push unsubscribe ordering so backend unsubscribe happens before local `subscription.unsubscribe()` (prevents server/client drift on backend failure) (`vibecheck/frontend/src/lib/push.js`).
- Added regression coverage for ordering + backend failure behavior (`vibecheck/frontend/src/lib/push.test.js`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test && npm run build` -> pass.

### Phase 6 re-review fixes (Push subscribe + idle escalation + translate validation)
- Push (frontend):
  - Reuse an existing `PushManager.getSubscription()` result instead of calling `subscribe()` again (avoids `InvalidStateError` when already subscribed) (`vibecheck/frontend/src/lib/push.js`).
  - Added coverage for existing-subscription behavior (`vibecheck/frontend/src/lib/push.test.js`).
- Smart notifications (push wiring):
  - Wire waiting states into idle escalation: when a session enters `waiting_approval`/`waiting_input`, an idle escalation push can fire at 5/10/15/30 min per intensity level (`vibecheck/push.py`).
  - Added regression coverage for 5-minute idle escalation on an approval wait (`vibecheck/tests/test_push.py`).
- Translation:
  - Added coverage for whitespace-only `target_lang` being rejected after stripping (`vibecheck/tests/test_translate.py`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test && npm run build` -> pass.

### Phase 6 hardening follow-ups (Push cleanup + voice validation + max recording + translate blank guard)
- Push:
  - Prune subscriptions on 404/410 send failures and restrict `push_subscriptions.json` perms to `0600` (`vibecheck/push.py`, `vibecheck/tests/test_push.py`).
- Voice:
  - Validate `language` query param (ja/en only), reject non-audio MIME types, and read raw bodies in a size-bounded stream (`vibecheck/routes/voice.py`, `vibecheck/tests/test_voice.py`).
- Mic:
  - Auto-stop long recordings (default 60s) and still upload on release even if the recorder already stopped (`vibecheck/frontend/src/lib/recorder.js`, `vibecheck/frontend/src/components/MicButton.svelte`, `vibecheck/frontend/src/lib/recorder.test.js`).
- Translation:
  - Reject whitespace-only `text` payloads before calling upstream (`vibecheck/routes/translate.py`, `vibecheck/tests/test_translate.py`).
- Verification:
  - `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` -> pass.
  - `cd vibecheck/frontend && npm test && npm run build` -> pass.

### WU-35: Gap 2 — Phone Prompts Visible in TUI (Stretch)

- Added a `TuiBridge` mount callback + FIFO one-shot dedupe so raw `UserMessageEvent` mounts a `UserMessage` widget in the Textual TUI when the prompt originated from phone (and skips duplicates for local prompts).
- `VibeCheckApp` now passes `mount_user_message` to `TuiBridge` and marks locally-submitted rendered prompts only after `bridge.inject_message()` succeeds.
- Follow-up: relaxed raw event detection to `*.endswith("UserMessageEvent")` (still guarded by `message_id`) and clarified deque overflow logging intent.
- Updated docs: removed the Gap 2 known limitation from `README.md`; manual test scenario `S6_GAP2_VISIBILITY` is now a strict pass.
- Verification:
  - `uv run pytest vibecheck/tests/test_tui_bridge.py vibecheck/tests/test_launcher.py -v` -> pass.
  - `uv run pytest vibecheck/tests/ -v` -> pass.
