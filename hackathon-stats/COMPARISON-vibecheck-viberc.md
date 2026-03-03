# Comparison: tokyo/vibecheck vs global/mistral-vibe-rc

Analysis date: 2026-03-03 (local workspace snapshot)

Primary references:
- vibecheck: [https://github.com/lhl/vibecheck](https://github.com/lhl/vibecheck)
- mistral-vibe-rc: [https://github.com/mistral-hack-vah/mistral-vibe-rc](https://github.com/mistral-hack-vah/mistral-vibe-rc)

## Executive Summary

These are both "mobile interfaces to Vibe", but they are aiming at meaningfully different products:

- `tokyo/vibecheck` is a mobile control plane for *existing* Mistral Vibe coding-agent sessions. Its core is in-process integration with Vibe's `AgentLoop` (structured events, tool-call approvals, user-input prompts) plus a phone PWA UI, push notifications, multi-session discovery, and optional voice/translation/vision features. See [vibecheck/vibecheck/bridge.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/bridge.py) and [vibecheck/vibecheck/ws.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/ws.py).
- `global/mistral-vibe-rc` is a voice-first "talk to a coding assistant" app. The mobile client streams microphone audio over WebSocket, gets realtime transcription deltas, then streams agent text + sentence-level TTS audio back to the app. Today it runs the agent by spawning the `vibe` CLI as a subprocess per request and uses `git diff HEAD` as the source of truth for "edits". See [mistral-vibe-rc/python/main.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/main.py) and [mistral-vibe-rc/python/vibe_executor.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/vibe_executor.py).

If you want "remote controlling Vibe from your phone" (approvals, multi-session, push when blocked), vibecheck is already built around that constraint. If you want "low-latency voice conversation with a coding agent with native audio UX", mistral-vibe-rc is much closer on the voice pipeline.

## Stats Summary (Code + Git)

### Size and Languages (scc, "core code" excludes Markdown/JSON/TOML/etc)

| Project | Primary Languages | Core Code Lines | Tracked Files |
|---|---:|---:|---:|
| `tokyo/vibecheck` | Python + JS + Svelte | 22,097 | 227 |
| `global/mistral-vibe-rc` | TypeScript + Python | 7,475 | 183 |

Breakdown highlights (core languages only, from scc JSON):
- vibecheck core: Python 9,766 LOC, JS 4,664, Svelte 3,994, Shell 2,441, HTML 893, CSS 339.
- mistral-vibe-rc core: TypeScript 3,961 LOC, Python 2,212, HTML 998, JS 259, CSS 45.

### Activity (commits and authors)

| Project | Commits | Authors (shortlog) | Date Range | Commits/day (observed) |
|---|---:|---:|---|---|
| `tokyo/vibecheck` | 219 | 2 main humans (name/email variations show as 3) | 2026-02-28 to 2026-03-01 | 179 (Feb 28), 40 (Mar 1) |
| `global/mistral-vibe-rc` | 96 | 4 | 2026-02-28 to 2026-03-01 | 42 (Feb 28), 54 (Mar 1) |

Notes on cadence and commit "shape":
- vibecheck has many small, feature-focused commits and a strong "tight loop" of add tests then implement then verify, reflected directly in the worklog. See [vibecheck/WORKLOG.md](https://github.com/lhl/vibecheck/blob/main/WORKLOG.md).
- mistral-vibe-rc's commit history shows more iterative debugging on audio streaming and UI plumbing (for example, multiple "Try to fix audio" commits in sequence). See recent history in the local git log.

### Test Surface (static inspection)

| Project | Backend tests | Frontend/mobile tests | Notable test posture |
|---|---:|---:|---|
| `tokyo/vibecheck` | 19 pytest files under `vibecheck/tests/` | 22 vitest files under `vibecheck/frontend/src/**/*.test.js` | Explicit TDD and verification checklist in AGENTS/worklog |
| `global/mistral-vibe-rc` | 3 pytest files under `tests/` | 2 vitest tests under `apps/mobile/hooks/__tests__` | Some unit tests, plus multiple manual test scripts |

References:
- vibecheck test suite: [vibecheck/vibecheck/tests/](https://github.com/lhl/vibecheck/tree/main/vibecheck/tests)
- vibecheck frontend tests: [vibecheck/vibecheck/frontend/src/](https://github.com/lhl/vibecheck/tree/main/vibecheck/frontend/src)
- mistral-vibe-rc tests: [mistral-vibe-rc/tests/](https://github.com/mistral-hack-vah/mistral-vibe-rc/tree/main/tests)

### AI-Agent Tooling Evidence (committed artifacts)

| Project | Agent instruction files | Other agent artifacts | Notes |
|---|---|---|---|
| `tokyo/vibecheck` | `AGENTS.md` and `CLAUDE.md -> AGENTS.md` | Worklog references model/tool comparisons in commits | Strong "agent collaboration" framing and conventions |
| `global/mistral-vibe-rc` | `AGENTS.md` (minimal) | `.agents/skills/*` | Suggests some agent tooling was used, but process is less documented |

References:
- vibecheck agent instructions: [vibecheck/AGENTS.md](https://github.com/lhl/vibecheck/blob/main/AGENTS.md)
- mistral-vibe-rc agent instructions: [mistral-vibe-rc/AGENTS.md](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/AGENTS.md)
- mistral-vibe-rc agent skills directory: [mistral-vibe-rc/.agents/](https://github.com/mistral-hack-vah/mistral-vibe-rc/tree/main/.agents)

## Architecture Comparison

### 1. How Each Integrates With Vibe

vibecheck: in-process, structured integration
- Wraps Vibe's own Textual app so phone UI and terminal TUI share the same `AgentLoop` instance in the same process. Entry point is `vibecheck-vibe`. See [vibecheck/vibecheck/launcher.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/launcher.py).
- Hooks `AgentLoop.set_approval_callback()`, `set_user_input_callback()`, and a message observer to receive typed events and intercept approvals. The bridge state machine is implemented in [vibecheck/vibecheck/bridge.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/bridge.py).
- Consequence: the mobile client receives high-fidelity structured events (tool call name, args, call id) and can resolve the same underlying `asyncio.Future` as the TUI.

mistral-vibe-rc: subprocess CLI integration (current default)
- Uses [mistral-vibe-rc/python/vibe_executor.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/vibe_executor.py) to spawn `vibe -p "<prompt>" --output text` and streams stdout lines as `agent_delta` events.
- Consequence: you do not get Vibe's internal typed tool-call objects, and you cannot reliably intercept tool approval prompts unless you parse text output and re-implement an approval protocol.
- There is also a separate, unused-looking direct Mistral Agents implementation in [mistral-vibe-rc/python/mistral_agent.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/mistral_agent.py), but [mistral-vibe-rc/python/main.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/main.py) currently imports `get_vibe_agent_service()` from `python/vibe_agent.py`, which wraps the CLI executor.

Summary: vibecheck chose "depth over breadth" (tight coupling to Vibe internals for correctness). mistral-vibe-rc chose "black-box Vibe CLI" (faster to stand up, less capability and less correctness for approvals/tools).

### 2. Session Model and Multi-Session Support

vibecheck
- Discovers and lists multiple Vibe sessions by scanning `~/.vibe/logs/session` metadata, and can attach/resume, including observe-only mode for sessions it did not start. See `SessionManager.discover()/attach()/resume()` in [vibecheck/vibecheck/bridge.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/bridge.py).
- Exposes fleet-level summary `GET /api/state` and per-session websocket rooms `/ws/events/{session_id}`. See [vibecheck/vibecheck/routes/api.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/routes/api.py) and [vibecheck/vibecheck/ws.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/ws.py).

mistral-vibe-rc
- Implements an in-memory session store keyed by session_id and user_id (JWT "sub"). See [mistral-vibe-rc/python/session_manager.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/session_manager.py).
- This is a single backend instance conversation concept, not "discover and manage external Vibe sessions running elsewhere".

### 3. Transport and Event Streaming

vibecheck
- Core agent events stream via WebSocket `/ws/events/{session_id}` (FastAPI/Starlette). Structured event types are Pydantic discriminated unions in [vibecheck/vibecheck/events.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/events.py).
- REST endpoints exist for approvals/messages and also for "snapshot/backlog" on connect.

mistral-vibe-rc
- Audio and control are multiplexed over a single WebSocket endpoint `/ws/audio`. The server sends JSON frames with events like `transcript_delta`, `agent_delta`, `audio_delta`, `edit`, etc. See [mistral-vibe-rc/python/main.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/main.py).
- There is also a REST SSE endpoint `POST /api/message` for streaming agent responses to text input (separate from voice).

### 4. Auth Model

vibecheck: PSK
- Uses a pre-shared key (PSK) via `X-PSK` header or `?psk=` query param for REST and WS auth. Middleware is in [vibecheck/vibecheck/auth.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/auth.py).
- Good for "single operator controlling their EC2 box", minimal setup.
- Weakness: no per-user isolation, and query-param auth risks leaking via logs/history if used.

mistral-vibe-rc: JWT
- Uses JWT for both REST and WebSocket auth, defaulting to `JWT_SECRET=dev-secret-change-me` if not set. See auth helpers in [mistral-vibe-rc/python/main.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/main.py).
- Better fit for multi-user scaling, but requires real secret management to be safe.

### 5. Diff / "Edits" Model

vibecheck: tool-correlated diffs
- Captures before/after file content for specific Vibe tool calls (`write_file`, `search_replace`) and stores unified diffs in memory, exposed at `GET /api/sessions/{id}/diffs`. See `_capture_tool_call_file_state()` and `_finalize_tool_call_file_state()` in [vibecheck/vibecheck/bridge.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/bridge.py).
- Good: correlates edits to a tool-call id and knows which tool caused a change.
- Constraint: depends on structured tool events (which vibecheck has because it hooks the AgentLoop).

mistral-vibe-rc: repo-level `git diff HEAD`
- After each agent response, the server runs `git diff HEAD --unified=5` and emits one `edit` event per file in the diff. See `get_git_diffs()` usage in [mistral-vibe-rc/python/main.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/main.py).
- Good: simple and works without tool-call visibility.
- Weaknesses:
  - not correlated to a single "tool call" or operation (it is a coarse repo snapshot).
  - diffs repeat across turns (it always compares to HEAD, not "since last message").
  - any non-agent local changes show up too.

### 6. Client Surface and Packaging/Deployment

vibecheck (mobile web/PWA)
- Frontend is Svelte 5 + Vite, built into `vibecheck/static/` and served directly by FastAPI. See [vibecheck/vibecheck/app.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/app.py) and [vibecheck/vibecheck/frontend/](https://github.com/lhl/vibecheck/tree/main/vibecheck/frontend/).
- Service worker + web manifest enable installable PWA and Web Push (browser-dependent).
- Intended deployment is an internet-reachable host (example in docs: EC2 + Caddy terminating TLS/WSS). See plan docs in [vibecheck/docs/PLAN.md](https://github.com/lhl/vibecheck/blob/main/docs/PLAN.md).

mistral-vibe-rc (native mobile + optional web)
- Mobile client is an Expo React Native app with a fair amount of native-facing audio infrastructure (expo-audio, expo-file-system, etc). See [mistral-vibe-rc/apps/mobile/](https://github.com/mistral-hack-vah/mistral-vibe-rc/tree/main/apps/mobile/).
- Repo is a pnpm workspace monorepo including a basic web app and an (apparently unused) TypeScript server stub. See [mistral-vibe-rc/pnpm-workspace.yaml](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/pnpm-workspace.yaml) and [mistral-vibe-rc/apps/server/src/index.ts](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/apps/server/src/index.ts).
- Backend has a Dockerfile for container deployment. See [mistral-vibe-rc/Dockerfile](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/Dockerfile).

## Functionality Comparison

### Overlap (both have some version of these)

- A mobile UI for interacting with an agent, receiving streaming updates.
- Voice input pipeline (microphone capture -> Voxtral transcription).
- ElevenLabs TTS output, surfaced as audio on the client.
- Visualizing "edits" as diffs (tool-based diffs in vibecheck, git-based diffs in mistral-vibe-rc).

### vibecheck capabilities that are first-class (and mostly absent in mistral-vibe-rc today)

- Tool-call approvals/denials from the phone that directly settle Vibe's internal Futures (no terminal scraping). See [vibecheck/vibecheck/bridge.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/bridge.py) and [vibecheck/vibecheck/routes/api.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/routes/api.py).
- Multi-session "fleet" management by discovering Vibe sessions from logs, switching sessions, and resume flows. See `SessionManager` in [vibecheck/vibecheck/bridge.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/bridge.py).
- Web Push notifications with VAPID, including "intensity" escalation logic and tool-call summarization/urgency classification using Ministral. See [vibecheck/vibecheck/push.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/push.py) and [vibecheck/vibecheck/notifications/ministral.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/notifications/ministral.py).
- Auto-translate output (EN to JA toggle) via `POST /api/translate`. See [vibecheck/vibecheck/routes/translate.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/routes/translate.py).
- Vision upload endpoint `POST /api/vision` used by the mobile UI's composer attachment flow. See [vibecheck/vibecheck/routes/vision.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/routes/vision.py).

### mistral-vibe-rc capabilities that are first-class (and weaker/simpler in vibecheck today)

- Realtime transcription deltas (the user sees their speech appear live as they talk), implemented via Voxtral realtime streaming. See [mistral-vibe-rc/python/audio_processor.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/audio_processor.py) and `transcript_delta` handling in [mistral-vibe-rc/apps/mobile/hooks/use-agent.ts](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/apps/mobile/hooks/use-agent.ts).
- Sentence-level interleaved TTS streaming (low perceived latency). See `stream_agent_with_tts()` in [mistral-vibe-rc/python/main.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/main.py) and the chunked playback strategy in [mistral-vibe-rc/apps/mobile/hooks/use-audio-playback.ts](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/apps/mobile/hooks/use-audio-playback.ts).
- Native mobile UX primitives (haptics, low-latency audio APIs, potentially better mic handling) due to Expo/React Native. See [mistral-vibe-rc/apps/mobile/package.json](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/apps/mobile/package.json).

## Code Quality and Maintainability

### High-level: "cohesive product" vs "polyglot scaffolding"

vibecheck is cohesive:
- One clear goal and one architecture, reinforced in docs and code: in-process Vibe bridging with typed events.
- Separation of concerns: routers per feature area (`routes/api.py`, `routes/voice.py`, `routes/push.py`, `routes/translate.py`, `routes/vision.py`) and a dedicated event model module. See [vibecheck/vibecheck/routes/](https://github.com/lhl/vibecheck/tree/main/vibecheck/routes).
- Strong test posture across backend and frontend, plus a detailed worklog and an explicit TDD checklist. See [vibecheck/WORKLOG.md](https://github.com/lhl/vibecheck/blob/main/WORKLOG.md) and [vibecheck/AGENTS.md](https://github.com/lhl/vibecheck/blob/main/AGENTS.md).

mistral-vibe-rc is more "polyglot workspace":
- It contains at least three partial architectures:
  - Python FastAPI backend (used): [mistral-vibe-rc/python/main.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/main.py).
  - TypeScript Hono server stub (appears unused): [mistral-vibe-rc/apps/server/src/index.ts](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/apps/server/src/index.ts).
  - A JS/TS monorepo with packages (`@thread/db`, `@thread/ai`) not used by the Python backend (at least in this snapshot). See [mistral-vibe-rc/packages/](https://github.com/mistral-hack-vah/mistral-vibe-rc/tree/main/packages).
- There are also multiple Python project files (`pyproject.toml` at root and a separate `python/pyproject.toml`) with different dependency sets, which is a maintainability smell unless it is intentionally a workspace layout. See [mistral-vibe-rc/pyproject.toml](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/pyproject.toml) and [mistral-vibe-rc/python/pyproject.toml](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/pyproject.toml).
- There is a fairly detailed client architecture spec (two WebSocket channels, schema codegen, permission flows) that does not match the current backend implementation (single `/ws/audio`, base64 `audio_delta`, no control-channel protocol). That is normal for hackathon iteration, but it increases drift risk if the doc is treated as "source of truth". See [mistral-vibe-rc/docs/CLIENT_TASKS.md](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/docs/CLIENT_TASKS.md).

### Error handling and operational readiness

vibecheck
- Many endpoints implement size limits, content-type guards, upstream error mapping, and timeouts (examples: voice STT and translate routes). See [vibecheck/vibecheck/routes/voice.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/routes/voice.py) and [vibecheck/vibecheck/routes/translate.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/routes/translate.py).
- Static file serving is carefully path-traversal safe (safe join). See `_safe_join()` in [vibecheck/vibecheck/app.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/app.py).
- Push secret storage attempts to restrict file perms to 0600. See [vibecheck/vibecheck/push.py](https://github.com/lhl/vibecheck/blob/main/vibecheck/push.py).

mistral-vibe-rc
- The Python backend is a single large module that mixes REST, WS, auth, streaming, and git diffing. It is workable, but harder to test and evolve cleanly. See [mistral-vibe-rc/python/main.py](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/python/main.py).
- It uses permissive CORS and prints lots of debug output unconditionally. This is fine for hackathon, but would need tightening for deployment.
- It includes a Dockerfile, which is a real advantage for "turn it into a service quickly". See [mistral-vibe-rc/Dockerfile](https://github.com/mistral-hack-vah/mistral-vibe-rc/blob/main/Dockerfile).

## "What Would I Merge" (if the goal is one best mobile Vibe experience)

If the target is "control Vibe from your phone" with a voice-first UX:

- Keep vibecheck's integration approach (in-process AgentLoop hooks). That is the only design here that gives correct approvals and tool visibility without brittle terminal scraping.
- Port mistral-vibe-rc's realtime voice loop into vibecheck:
  - websocket-based PCM streaming and transcript deltas (Voxtral realtime),
  - sentence-level interleaved TTS, and
  - a native-app client if you want best audio/mic behavior (Expo), or implement streaming playback in the PWA (today vibecheck downloads the whole MP3 blob before playing).
- Standardize the event schema:
  - vibecheck already has Pydantic discriminated unions for events; mistral-vibe-rc could align to that to reduce client brittleness.
- If multi-user is important, prefer JWT auth, but do not ship with a default JWT secret. If single-operator is fine, PSK is simpler.

Conversely, if the target is "voice assistant that can run Vibe commands" (not necessarily approve tools), mistral-vibe-rc's Dockerized Python backend plus Expo client is the faster baseline, but you should clean up unused scaffolding (TS server stub, unused workspace packages, duplicate pyprojects) to reduce cognitive load.
