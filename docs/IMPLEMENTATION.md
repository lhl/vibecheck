# vibecheck — Implementation Punchlist

> **Derived from:** [PLAN.md](./PLAN.md) (Layers L0–L9)
> **Last updated:** 2026-02-28
> **Approach:** Build backend and frontend scaffolds, then build/test FE browser-API components in isolation (`prototypes/`), then integrate layer by layer.
> **Team:** 2 humans + N coding agents working in parallel

---

## Table of Contents

- [Dependency Graph](#dependency-graph)
- [Work Units & Parallelism](#work-units--parallelism)
- [Testing Strategy](#testing-strategy)
- [Directory Structure](#directory-structure)
- [Phase 0: Scaffolds](#phase-0-scaffolds)
- [Phase 1: Prototypes](#phase-1-prototypes-standalone-fe-components)
- [Phase 2: Backend Core (L0–L1)](#phase-2-backend-core-l0l1)
- [Phase 3: Live Attach (L1.5)](#phase-3-live-attach-l15)
- [Phase 3.1: TUI Integration Hardening](#phase-31-tui-integration-hardening)
- [Phase 4: Frontend Core (L2)](#phase-4-frontend-core-l2)
- [Phase 5: Integration #1](#phase-5-integration-1--first-live-mobile-demo)
- [Phase 6: Feature Branches (L3–L5)](#phase-6-feature-branches-l3l5-parallel)
- [Phase 7: Polish (L6)](#phase-7-polish-l6)
- [Phase 8: Stretch (L7–L9)](#phase-8-stretch-l7l9)
- [Deployment Checklist](#deployment-checklist)

---

## Dependency Graph

```
                    ┌──────────────────┐
                    │   Phase 0A       │
                    │ Backend Scaffold │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Phase 2        │
                    │ Backend Core     │
                    │ (bridge, events, │
                    │  WS, REST)       │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Phase 3        │
                    │ Live Attach      │
                    │ (TUI + Mobile    │
                    │  Bridge, L1.5)   │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Phase 3.1      │
                    │ TUI Integration  │─────────────┐
                    │ Hardening        │             │
                    └──────────────────┘             │
                                                    │
┌──────────────────┐  ┌──────────────────┐          │
│   Phase 0B       │  │   Phase 1        │          │
│ Frontend Scaffold│  │ All 6 Prototypes │          │
└────────┬─────────┘  │ (independent)    │          │
         │            └────────┬─────────┘          │
         │    ┌────────────────┘                    │
         ▼    ▼                                     │
  ┌──────────────────┐                              │
  │   Phase 4        │                              │
  │ Frontend Core    │──────────────────┐           │
  └──────────────────┘                  │           │
                              ┌─────────┴───────────┴──┐
                              │   Phase 5               │
                              │ Integration #1          │◀── GATE
                              │ (first live mobile demo)│
                              └─────────┬───────────────┘
                    ┌───────────────────┼──────────┬─────────────┐
                    ▼                   ▼          ▼             │
             ┌──────────┐        ┌────────┐ ┌────────┐          │
             │ Phase 6A │        │Phs 6B  │ │Phs 6D  │          │
             │ Voice L3 │        │Push L4a│ │Trans L5│          │
             └──────────┘        └───┬────┘ └────────┘          │
                                     │                          │
                                     ▼                          ▼
                               ┌──────────┐           ┌──────────┐
                               │ Phase 6C │           │ Phase 7  │
                               │Smart L4b │           │ Polish   │
                               └──────────┘           └──────────┘
```

### Key constraints

| Rule | Detail |
|------|--------|
| Phase 0A and 0B are **fully parallel** | No dependencies between backend and frontend scaffolds |
| Phase 1 prototypes are **all independent** | Any prototype can be built by any agent at any time — no deps on scaffolds or each other |
| Phase 2 **requires** Phase 0A | Backend core builds on the scaffold |
| Phase 3 **requires** Phase 2 | Live attach builds on bridge + events + WS infrastructure |
| Phase 3.1 **requires** Phase 3 | TUI integration hardening builds on live attach bridge mechanics |
| Phase 4 **requires** Phase 0B | Frontend core builds on the scaffold; reuses Proto 1 (WS reconnect) code |
| Phase 3.1 and Phase 4 are **parallel** | TUI hardening and frontend core are independent tracks |
| Phase 5 **requires** Phase 3.1 + Phase 4 | Gate acceptance test needs TUI to not freeze on remote approval |
| Phase 6A/6B/6D are **fully parallel** | Voice, Push, Translation are independent feature branches |
| Phase 6C **requires** Phase 6B | Smart notifications build on push infrastructure |
| Phase 7 **requires** Phase 5 | Polish is post-integration |
| Prototypes **feed into** later phases | Proto 1→Phase 4, Proto 2→Phase 6A, Proto 3→Phase 6B, Proto 4→Phase 8/L8, Proto 8→Phase 8/L7 |

---

## Work Units & Parallelism

Each work unit (WU) is a self-contained task that one agent can complete independently. Listed with dependencies and estimated scope.

| WU | Phase | Name | Depends On | Parallel With | Scope |
|----|-------|------|------------|---------------|-------|
| WU-01 | 0A | Backend scaffold | — | WU-02, WU-03–08 | S |
| WU-02 | 0B | Frontend scaffold | — | WU-01, WU-03–08 | S |
| WU-03 | 1 | Proto: WebSocket reconnect | — | all other WUs | S |
| WU-04 | 1 | Proto: MediaRecorder + Opus | — | all other WUs | S |
| WU-05 | 1 | Proto: Push notifications | — | all other WUs | S |
| WU-06 | 1 | Proto: Camera capture | — | all other WUs | S |
| WU-07 | 1 | Proto: PWA install | — | all other WUs | S |
| WU-08 | 1 | Proto: Speech synthesis | — | all other WUs | S |
| WU-09 | 2 | Event models (Pydantic) | WU-01 | WU-10, WU-11 | S |
| WU-10 | 2 | WebSocket manager | WU-01, WU-09 | WU-11 | M |
| WU-11 | 2 | REST endpoints (stub → real) | WU-01, WU-09 | WU-10 | M |
| WU-12 | 2 | Vibe bridge (AgentLoop hooks) | WU-09, WU-10, WU-11 | — | L |
| WU-25 | 3 | Bridge `attach_to_loop()` | WU-12 | WU-26 | S |
| WU-26 | 3 | Event tee + TUI bridge rendering | WU-25 | — | M |
| WU-27 | 3 | VibeCheckApp + launcher | WU-25, WU-26 | — | M |
| WU-28 | 3 | Live attach integration test | WU-27 | — | S |
| WU-32 | 3.1 | TUI approval/question UI cleanup on remote resolve | WU-28 | WU-33, WU-13–15 | M |
| WU-33 | 3.1 | Remote injection UX + lifecycle parity audit | WU-28 | WU-32, WU-13–15 | S |
| WU-34 | 3.1 | Manual validation with real Vibe | WU-32, WU-33 | — | S |
| WU-13 | 4 | FE WebSocket client + stores | WU-02, WU-03 | WU-14, WU-15 | M |
| WU-14 | 4 | FE chat components | WU-02 | WU-13, WU-15 | M |
| WU-15 | 4 | FE approval panel + input bar | WU-02 | WU-13, WU-14 | M |
| WU-16 | 5 | Integration: static build + E2E | WU-13–15, WU-34 | — | M |
| WU-17 | 6A | Voice: backend transcribe endpoint | WU-16 | WU-19, WU-21 | S |
| WU-18 | 6A | Voice: FE mic button | WU-16, WU-04 | WU-19, WU-21 | M |
| WU-19 | 6B | Push: backend VAPID + pywebpush | WU-16 | WU-17, WU-21 | M |
| WU-20 | 6B | Push: FE service worker + subscribe | WU-16, WU-05 | WU-17, WU-21 | M |
| WU-21 | 6D | Translation: backend + FE | WU-16 | WU-17, WU-19 | M |
| WU-22 | 6C | Smart notifications (Ministral) | WU-19 | WU-21 | M |
| WU-23 | 7 | Polish: FE settings, theme, diff viewer | WU-16, WU-24 | — | L |
| WU-24 | 7 | Polish: BE session resume + diff endpoints | WU-12 | WU-23 | M |
| WU-35 | 7 | Gap 2: phone prompts visible in TUI (stretch) | WU-24 | — | M |

**Scope:** S = small (< 1 hour), M = medium (1–3 hours), L = large (3+ hours)

### Maximum parallelism by phase

| Moment | Agents that can work simultaneously |
|--------|-------------------------------------|
| Start | WU-01 + WU-02 + WU-03 through WU-08 = **up to 8 parallel** |
| After Phase 0A done | WU-09, WU-10, WU-11 (+ any remaining prototypes) = **3–6 parallel** |
| After Phase 2 done | WU-25, WU-26 (live attach) + FE WUs if Phase 0B done = **2–5 parallel** |
| After Phase 3 done | WU-32 + WU-33 (TUI hardening) + WU-13 + WU-14 + WU-15 = **up to 5 parallel** |
| After Phase 5 gate | WU-17 + WU-18 + WU-19 + WU-20 + WU-21 + WU-24 = **6 parallel** |

---

## Testing Strategy

Every work unit must include tests. Agents verify their own work before marking a WU complete.

### Backend Testing (Python)

**Framework:** pytest + httpx (AsyncClient for FastAPI)

```bash
# Run all backend tests
uv run pytest vibecheck/tests/ -v

# Run a specific test file
uv run pytest vibecheck/tests/test_api.py -v

# Run with coverage
uv run pytest vibecheck/tests/ --cov=vibecheck --cov-report=term-missing
```

**What to test:**
- Every REST endpoint: request/response, auth (with and without PSK), error cases
- Pydantic event models: serialization, validation, edge cases
- WebSocket: connect, receive events, auth rejection, reconnect
- PSK auth: valid key, invalid key, missing key, timing-safe comparison
- Bridge state machine: state transitions, concurrent approvals
- TTS proxy (`/api/tts`): stream response headers/chunks, auth failure, upstream error mapping

**Test file layout:**
```
vibecheck/tests/
├── conftest.py              # Fixtures: FastAPI test client, mock bridge, sample events
├── test_auth.py             # PSK middleware tests
├── test_events.py           # Pydantic model serialization/validation
├── test_api.py              # REST endpoint tests
├── test_ws.py               # WebSocket tests
├── test_bridge.py           # AgentLoop integration tests (mocked)
├── test_tui_bridge.py       # TUI bridge adapter tests
├── test_launcher.py         # vibecheck-vibe launcher tests
├── test_live_attach.py      # Live attach integration tests
├── test_voice.py            # Voxtral transcription proxy tests
├── test_tts.py              # ElevenLabs TTS proxy tests
├── test_translate.py        # Translation endpoint tests
└── test_push.py             # Push notification tests
```

**Key fixture: mock bridge** — Tests should NOT require a running Vibe instance. Create a `MockBridge` that simulates AgentLoop events:
```python
# conftest.py
@pytest.fixture
def mock_bridge():
    """Bridge that emits canned events without a real AgentLoop."""
    bridge = MockBridge()
    bridge.emit_assistant("Hello, I'll help you with that.")
    bridge.emit_tool_call("bash", {"command": "npm test"}, call_id="tc-001")
    bridge.set_state("waiting_approval", pending_call_id="tc-001")
    return bridge
```

### Frontend Testing

**Build verification** (minimum bar):
```bash
cd vibecheck/frontend && npm run build
# Must exit 0 with no errors
```

**Svelte component tests** (if time permits): vitest + @testing-library/svelte
```bash
cd vibecheck/frontend && npm test
```

**What to test at minimum:**
- Build succeeds (`npm run build` exit 0)
- Vite dev server starts (`npm run dev` — check port responds)
- No TypeScript/lint errors

### Prototype Testing

Each prototype includes a `test.sh` that exercises its server:
```bash
cd prototypes/websocket-reconnect && ./test.sh
# Starts server, connects client, verifies messages received, kills server
```

Pattern for prototype `test.sh`:
```bash
#!/bin/bash
set -euo pipefail
echo "=== Testing: $(basename $(pwd)) ==="

# Start server in background
uv run python server.py &
SERVER_PID=$!
sleep 1

# Run checks
curl -sf http://localhost:8080/ > /dev/null && echo "PASS: index.html serves"
# ... additional checks ...

# Cleanup
kill $SERVER_PID 2>/dev/null
echo "=== All tests passed ==="
```

### Smoke Tests (Integration)

**`scripts/smoke_test.sh`** — hit all backend endpoints, verify responses:
```bash
#!/bin/bash
# Run against a live server (local or EC2)
BASE_URL="${1:-http://localhost:7870}"
PSK="${VIBECHECK_PSK:?VIBECHECK_PSK must be set}"

echo "Testing $BASE_URL..."
curl -sf "$BASE_URL/api/health" | jq -e '.status == "ok"'
curl -sf -H "X-PSK: $PSK" "$BASE_URL/api/state" | jq -e '.total >= 0'
curl -sf -H "X-PSK: $PSK" "$BASE_URL/api/sessions" | jq -e 'type == "array"'
# ... WebSocket test with websocat ...
echo "All smoke tests passed"
```

### Event Replay for UI Development

**`scripts/replay_events.py`** — replay canned events over WebSocket for FE testing without a live Vibe:
```bash
uv run python scripts/replay_events.py --port 7870
# Sends a scripted sequence: assistant message → tool call → wait for approval → result
# Frontend can connect and render without needing real Vibe
```

**`tests/fixtures/`** — sample event sequences:
```
tests/fixtures/
├── basic_conversation.json      # Simple assistant messages
├── tool_approval_flow.json      # Tool call → approval → result
├── multi_tool_sequence.json     # Several tool calls in a row
├── error_scenario.json          # Tool call that errors
└── ask_user_question.json       # Input request flow
```

---

## Directory Structure

Target layout after scaffolding:

```
vibecheck/
├── pyproject.toml
├── __init__.py
├── __main__.py              # uvicorn entrypoint
├── app.py                   # FastAPI app factory
├── auth.py                  # PSK middleware
├── bridge.py                # AgentLoop integration + callbacks
├── events.py                # Event types (Pydantic models)
├── ws.py                    # WebSocket manager (broadcast)
├── tui_bridge.py            # Adapter: bridge events → Textual TUI rendering
├── launcher.py              # vibecheck-vibe entry point (TUI + WebSocket in same process)
├── routes/
│   ├── api.py               # REST endpoints
│   ├── voice.py             # POST /api/voice/transcribe
│   ├── tts.py               # POST /api/tts (ElevenLabs proxy)
│   ├── translate.py         # POST /api/translate
│   └── push.py              # Push subscription + VAPID
├── notifications/
│   ├── manager.py           # IntensityManager + escalation
│   └── ministral.py         # Ministral copy/urgency/summaries
├── tests/
│   ├── conftest.py          # Fixtures: test client, mock bridge, sample events
│   ├── test_auth.py
│   ├── test_events.py
│   ├── test_api.py
│   ├── test_ws.py
│   ├── test_bridge.py
│   ├── test_voice.py
│   ├── test_tts.py
│   ├── test_translate.py
│   └── test_push.py
├── frontend/                # Svelte 5 + Vite PWA
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── public/
│   │   ├── manifest.json
│   │   └── sw.js
│   └── src/
│       ├── App.svelte
│       ├── main.js
│       ├── lib/
│       │   ├── ws.js
│       │   ├── auth.js
│       │   ├── push.js
│       │   ├── recorder.js
│       │   └── translate.js
│       ├── stores/
│       │   ├── events.js
│       │   ├── connection.js
│       │   └── settings.js
│       └── components/
│           ├── ChatMessage.svelte
│           ├── ToolCallCard.svelte
│           ├── ApprovalPanel.svelte
│           ├── InputBar.svelte
│           ├── MicButton.svelte
│           ├── ConnectionStatus.svelte
│           ├── SessionList.svelte
│           └── SettingsPanel.svelte
├── static/                  # Vite build output (served by FastAPI in prod)
tests/
├── fixtures/                # Sample event sequences for replay/testing
│   ├── basic_conversation.json
│   ├── tool_approval_flow.json
│   ├── multi_tool_sequence.json
│   ├── error_scenario.json
│   └── ask_user_question.json
prototypes/                  # Standalone browser-API test pages
├── README.md
├── websocket-reconnect/
│   ├── index.html
│   ├── server.py
│   └── test.sh
├── media-recorder/
│   ├── index.html
│   ├── server.py
│   └── test.sh
├── push-notifications/
│   ├── index.html
│   ├── sw.js
│   ├── server.py
│   └── test.sh
├── camera-capture/
│   ├── index.html
│   ├── server.py
│   └── test.sh
├── pwa-install/
│   ├── index.html
│   ├── manifest.json
│   ├── sw.js
│   └── test.sh
└── speech-synthesis/
    ├── index.html
    └── test.sh
frontend-prototype/              # Standalone STT+TTS voice loop (Voxtral + ElevenLabs)
├── README.md
├── MOBILE-QA-CHECKLIST.md
├── frontend/                    # Svelte 5 app (record → STT → TTS → playback)
│   ├── src/App.svelte
│   ├── src/App.test.js
│   └── e2e/mobile-smoke.spec.js
└── server/                      # FastAPI proxy (/api/stt, /api/tts, /api/voices)
    ├── server/app.py
    └── tests/test_api.py
scripts/
├── smoke_test.sh            # Hit all endpoints, verify responses
└── replay_events.py         # Replay canned events over WS for FE dev
```

---

## Phase 0: Scaffolds

> **Parallelism:** 0A and 0B are fully independent. Assign to separate agents.

### WU-01: Backend Scaffold (Phase 0A)

**Depends on:** nothing
**Parallel with:** WU-02, all prototypes

- [ ] **`vibecheck/pyproject.toml`**
  - deps: fastapi, uvicorn[standard], websockets, pydantic>=2, mistralai, pywebpush, httpx
  - dev deps: pytest, pytest-asyncio, httpx, pytest-cov
  - `[project.scripts]` entry or `__main__.py` for `uv run python -m vibecheck`
- [ ] **`vibecheck/__init__.py`**, **`vibecheck/__main__.py`**
  - `__main__.py`: `uvicorn.run("vibecheck.app:create_app", factory=True, host="0.0.0.0", port=7870)`
- [ ] **`vibecheck/app.py`** — FastAPI app factory
  - CORS (allow all origins for dev, lock down later)
  - Lifespan context manager (startup/shutdown hooks for bridge)
  - Mount routes
- [ ] **`vibecheck/auth.py`** — PSK middleware
  - Read PSK from `VIBECHECK_PSK` env var (always required, fail-fast on missing)
  - Check `X-PSK` header or `?psk=` query param
  - `hmac.compare_digest` for timing-safe comparison
  - Exempt paths: `/`, `/api/health`, static files
- [ ] **`vibecheck/routes/api.py`** — stub endpoints
  - `GET /api/health` → `{"status": "ok"}`
  - `GET /api/state` → `{"total": 0, "running": 0, "waiting": 0, "idle": 0}`
  - `GET /api/sessions` → `[]`
  - `GET /api/sessions/{session_id}` → 501
  - `POST /api/sessions/{session_id}/approve` → 501
  - `POST /api/sessions/{session_id}/input` → 501
  - `POST /api/sessions/{session_id}/message` → 501
- [ ] **`vibecheck/ws.py`** — WebSocket stub
  - `WS /ws/events/{session_id}` — accept, send `{"type": "connected", "session_id": "<id>"}`, heartbeat every 30s
  - `ConnectionManager` class: connect, disconnect, broadcast
- [ ] **`vibecheck/tests/conftest.py`** + **`vibecheck/tests/test_auth.py`**
  - Fixture: `client` (httpx AsyncClient with app)
  - Tests: health no-auth, state with valid PSK, state with bad PSK → 401, state with no PSK → 401, app startup fails when `VIBECHECK_PSK` is unset

**Verify:**
```bash
export VIBECHECK_PSK=dev
uv run python -m vibecheck &                                  # starts on :7870
curl -sf http://localhost:7870/api/health                      # {"status": "ok"}
curl -sf -H "X-PSK: $VIBECHECK_PSK" http://localhost:7870/api/state  # {"total":0,...}
curl -sf http://localhost:7870/api/state && exit 1 || true     # 401 expected
uv run pytest vibecheck/tests/test_auth.py -v                  # WU-01 targeted tests pass
uv run pytest vibecheck/tests/ -v                              # full backend suite passes
```

### WU-02: Frontend Scaffold (Phase 0B)

**Depends on:** nothing
**Parallel with:** WU-01, all prototypes

- [ ] **`vibecheck/frontend/`** — Svelte 5 + Vite
  - `npm create vite@latest . -- --template svelte`
  - Add to `.gitignore`: `vibecheck/frontend/node_modules/`, `vibecheck/static/`
- [ ] **`vite.config.js`**
  - Proxy `/api/*` and `/ws/*` to `http://localhost:7870`
  - Build output: `outDir: '../static'`
- [ ] **`public/manifest.json`** — PWA manifest
  - name, short_name, display: standalone, orientation: portrait
  - theme_color: `#FF7000`, background_color: `#1a1a1a`
  - Icons: 192x192 + 512x512 (generate simple placeholder)
- [ ] **`public/sw.js`** — service worker shell
  - Cache index.html on install (offline fallback)
  - Push event listener: `console.log("push received", event)` (stub)
- [ ] **`src/App.svelte`** — shell layout
  - Header bar (app name + connection indicator placeholder)
  - Main scrollable area (placeholder text)
  - Bottom input bar (placeholder)
  - Mobile CSS: viewport-fit cover, safe area insets, touch targets ≥ 44px (design for 360px–428px widths)
  - Dark theme via CSS custom properties
- [ ] **Register SW** in `src/main.js`

**Verify:**
```bash
cd vibecheck/frontend && npm install && npm run build  # exit 0, output in ../static/
npm run dev &                                          # dev server on :5173
curl -sf http://localhost:5173/                         # returns HTML
ls ../static/index.html                                # build output exists
# If any frontend file changed, rerun build before commit:
npm run build
```

---

## Phase 1: Prototypes (standalone FE components)

> **Parallelism:** All 6 prototypes are fully independent of each other AND of the scaffolds. Up to 6 agents can work on these simultaneously. Each agent can start immediately.

Each prototype is a **standalone HTML page** (no build step) with a `server.py` (if needed) and `test.sh`. Tests one browser API in isolation.

### WU-03: Proto — WebSocket Reconnect (`prototypes/websocket-reconnect/`)

**Depends on:** nothing
**Feeds into:** WU-13 (FE WebSocket client)

- [ ] **`server.py`** — asyncio WebSocket server (:8080)
  - Send JSON events every 2s mimicking Vibe events (assistant, tool_call, tool_result)
  - `/drop` endpoint or random connection drops (1-in-10 chance every 10s) to test reconnect
  - Heartbeat ping every 30s
- [ ] **`index.html`**
  - Connect/disconnect toggle button
  - Connection state indicator (green/yellow/red dot + text)
  - Message log (scrollable div, newest at bottom)
  - Reconnect counter and backoff timer display
  - Auto-reconnect: exponential backoff 1s → 2s → 4s → 8s → 30s cap
  - Reset backoff on successful connection
  - Heartbeat: if no message for 45s, force reconnect
- [ ] **`test.sh`** — start server, connect via websocat, verify messages arrive, kill server

**Verify:** Open on phone → see events streaming → kill server → see reconnecting → restart server → auto-reconnects

### WU-04: Proto — MediaRecorder + Opus (`prototypes/media-recorder/`)

**Depends on:** nothing
**Feeds into:** WU-18 (FE mic button)
**Prior art:** `frontend-prototype/frontend/src/App.svelte` has a working MediaRecorder flow (record/stop/upload) — reuse for integration.

- [ ] **`server.py`** — HTTP server (:8080)
  - `POST /upload` — receive audio blob, log size + content-type, return `{"text": "テスト", "language": "ja", "duration_ms": 1234}`
  - Serve `index.html` on `GET /`
- [ ] **`index.html`**
  - Push-to-talk button (touchstart/touchend + mousedown/mouseup)
  - `navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}})`
  - `MediaRecorder` with `mimeType: "audio/webm;codecs=opus"`
  - Visual: pulsing red dot + duration counter while recording
  - On stop: show blob size, create `<audio>` playback element
  - Upload button → POST blob to `/upload`
  - Display server response (transcription text)
  - On-page log of all events (start, dataavailable, stop, upload, response)
- [ ] **`test.sh`** — start server, POST a dummy audio file, verify response JSON

**Verify:** Open on phone → hold button → speak → release → hear playback → upload → see transcription response

### WU-05: Proto — Push Notifications (`prototypes/push-notifications/`)

**Depends on:** nothing
**Feeds into:** WU-19, WU-20 (push backend + frontend)

- [ ] **`server.py`** — HTTP server (:8080) with pywebpush
  - Generate VAPID keys on startup (save to `vapid_keys.json` for reuse)
  - `GET /vapid-public-key` → return public key
  - `POST /subscribe` — store subscription JSON
  - `POST /send-test` — send test push to all stored subscriptions
  - Serve index.html and sw.js
- [ ] **`sw.js`** — service worker
  - `push` event → `self.registration.showNotification()` with title, body, icon, actions: [{action: "approve", title: "Approve"}, {action: "deny", title: "Deny"}]
  - `notificationclick` event → `clients.openWindow()` or `postMessage` to client
- [ ] **`index.html`**
  - Show notification permission state
  - "Request Permission" button → `Notification.requestPermission()`
  - "Subscribe" button → register SW, subscribe with VAPID key, POST subscription to server
  - "Send Test Push" button → POST to `/send-test`
  - Display subscription JSON for debugging
  - Listen for `message` from SW (notification click feedback)
- [ ] **`test.sh`** — start server, verify VAPID key endpoint, POST subscription, send test push

**Verify:** Open on phone → subscribe → send test push → notification appears → tap action → client receives callback

### WU-06: Proto — Camera Capture (`prototypes/camera-capture/`)

**Depends on:** nothing
**Feeds into:** Phase 7 stretch (L8 camera input)

- [ ] **`server.py`** — HTTP server (:8080)
  - `POST /upload` — receive image, log size, return `{"description": "A whiteboard with code"}`
  - Serve index.html on `GET /`
- [ ] **`index.html`**
  - "Take Photo" button → `<input type="file" accept="image/*" capture="environment">`
  - Image preview (`FileReader` → img src)
  - Upload button → POST to `/upload` (multipart/form-data)
  - Display response
  - On-page log
- [ ] **`test.sh`** — start server, POST a test image, verify response

**Verify:** Open on phone → tap take photo → camera opens → snap → preview shows → upload → response displayed

### WU-07: Proto — PWA Install (`prototypes/pwa-install/`)

**Depends on:** nothing
**Feeds into:** WU-02 (frontend scaffold PWA config)

- [ ] **`manifest.json`** — minimal valid PWA manifest
  - name, short_name, start_url, display: standalone, icons (placeholder)
- [ ] **`sw.js`** — minimal: cache `index.html` on install
- [ ] **`index.html`**
  - Register service worker
  - Listen for `beforeinstallprompt` → show install button
  - "Install" button → trigger deferred prompt
  - Detect standalone mode: `window.matchMedia('(display-mode: standalone)').matches`
  - Display: is installable? is installed? is standalone?
  - On-page log
- [ ] **`test.sh`** — serve with `uv run python -m http.server`, check that manifest and sw.js are served correctly

**Verify:** Open on phone Chrome → "Add to Home Screen" prompt available → install → opens in standalone mode

### WU-08: Proto — Speech Synthesis / TTS (`prototypes/speech-synthesis/`)

**Depends on:** nothing
**Feeds into:** Phase 7 stretch (L7 TTS)
**Prior art:** `frontend-prototype/server/server/app.py` has a working ElevenLabs TTS streaming proxy (`POST /api/tts`) with voice list, error mapping, and tests. `frontend-prototype/frontend/src/App.svelte` has browser audio playback. See `docs/FRONTEND-PROTOTYPE-PLAN.md`.

Two approaches to validate — browser-native (free fallback) and ElevenLabs (high quality, prize target):

- [ ] **`browser-tts.html`** — browser SpeechSynthesis API (no server needed)
  - Text input area
  - Language selector: ja-JP, en-US
  - Voice picker: populate from `speechSynthesis.getVoices()`
  - Rate slider (0.5–2.0), pitch slider (0.5–2.0)
  - "Speak" button → `speechSynthesis.speak(new SpeechSynthesisUtterance(...))`
  - Speaking indicator (active while speaking)
  - "Stop" button → `speechSynthesis.cancel()`
  - On-page log of events (start, end, error, boundary)
- [ ] **`elevenlabs-tts.py`** — ElevenLabs streaming TTS proof-of-concept
  - `pip install elevenlabs` (or `uv add elevenlabs`)
  - Text input → ElevenLabs streaming TTS API → save to file + play
  - Test with English and Japanese text
  - Measure latency: time from request to first audio byte
  - List available voices, pick a good default for "agent assistant"
  - Test streaming endpoint (`/v1/text-to-speech/{voice_id}/stream`)
- [ ] **`elevenlabs-tts-server.py`** — FastAPI proxy prototype
  - `POST /api/tts` — accepts `{text, language, voice_id?}`
  - Streams ElevenLabs response back as `audio/mpeg` chunked response
  - Keeps `ELEVENLABS_API_KEY` server-side
- [ ] **`test.sh`** — verify browser HTML is valid + ElevenLabs API key works

**Verify:**
- Browser TTS: Open on phone → type text → select Japanese voice → tap speak → hear audio
- ElevenLabs: `uv run python elevenlabs-tts.py "Hello from vibecheck"` → hear audio, check latency

---

## Phase 2: Backend Core (L0–L1)

> **Parallelism:** WU-09 first, then WU-10 + WU-11 in parallel, then WU-12 last (needs WS manager).

### WU-09: Event Models (`vibecheck/events.py`)

**Depends on:** WU-01 (backend scaffold)
**Parallel with:** nothing initially (fast, do first)

- [ ] **Pydantic v2 models** for all event types:
  ```python
  class EventBase(BaseModel):
      type: str
      id: str = Field(default_factory=lambda: uuid4().hex[:8])
      timestamp: float = Field(default_factory=time.time)

  class AssistantEvent(EventBase):
      type: Literal["assistant"] = "assistant"
      content: str

  class ToolCallEvent(EventBase):
      type: Literal["tool_call"] = "tool_call"
      tool_name: str
      args: dict
      call_id: str

  class ToolResultEvent(EventBase):
      type: Literal["tool_result"] = "tool_result"
      call_id: str
      output: str
      is_error: bool = False

  class ApprovalRequest(EventBase):
      type: Literal["approval_request"] = "approval_request"
      call_id: str
      tool_name: str
      args: dict

  class InputRequest(EventBase):
      type: Literal["input_request"] = "input_request"
      request_id: str
      question: str
      options: list[str] = []

  class StateChange(EventBase):
      type: Literal["state"] = "state"
      state: Literal["idle", "running", "waiting_approval", "waiting_input"]

  class UserMessage(EventBase):
      type: Literal["user_message"] = "user_message"
      content: str

  # Discriminated union for deserialization
  Event = Annotated[AssistantEvent | ToolCallEvent | ..., Field(discriminator="type")]
  ```
- [ ] **`vibecheck/tests/test_events.py`**
  - Serialize each event type to JSON, deserialize back, assert round-trip
  - Validate discriminated union parsing
  - Test default field generation (id, timestamp)
  - Test validation errors for bad data

**Verify:**
```bash
uv run pytest vibecheck/tests/test_events.py -v  # all pass
```

### WU-10: WebSocket Manager (`vibecheck/ws.py`)

**Depends on:** WU-01, WU-09
**Parallel with:** WU-11

- [ ] **`ConnectionManager`** class (session-aware)
  - `connect(websocket, session_id, psk)` — validate PSK, add to session room
  - `disconnect(websocket)` — remove from session room
  - `broadcast(session_id, event: EventBase)` — serialize + send to session subscribers
  - `broadcast_all(event: EventBase)` — send to all clients (fleet-level events)
  - `send_personal(websocket, event)` — send to one client
  - Internal: `rooms: dict[str, set[WebSocket]]` — per-session connection tracking
  - Track connected client count (total + per-session)
- [ ] **WebSocket endpoint** `WS /ws/events/{session_id}`
  - Auth: check `?psk=` query param on upgrade
  - On connect: join session room, send `StateChange` with session state + last 50 events (backlog)
  - Main loop: receive messages (for future bidirectional use), handle disconnect
  - Heartbeat: send `{"type": "heartbeat"}` every 30s
- [ ] **`vibecheck/tests/test_ws.py`**
  - Test: connect with valid PSK → receives connected event
  - Test: connect with bad PSK → connection rejected
  - Test: broadcast to session only reaches that session's subscribers
  - Test: disconnect removes client from session room
  - Test: backlog delivered on connect
  - Test: two clients on different sessions get independent events

**Verify:**
```bash
uv run pytest vibecheck/tests/test_ws.py -v
# Manual: websocat ws://localhost:7870/ws/events/SESSION_ID?psk=dev → see heartbeats
```

### WU-11: REST Endpoints — Real Implementation (`vibecheck/routes/api.py`)

**Depends on:** WU-01, WU-09
**Parallel with:** WU-10

- [ ] **`GET /api/sessions/{session_id}/state`** — return session state + pending request info
  - `{state, pending_approval?: {call_id, tool_name, args}, pending_input?: {request_id, question}}`
- [ ] **`GET /api/sessions`** — list discovered sessions from `~/.vibe/logs/session/`
  - Scan directory, return `[{id, started_at, last_activity, message_count, status}]`
  - Status: running / waiting_approval / waiting_input / idle / disconnected
- [ ] **`GET /api/sessions/{session_id}`** — session detail + event backlog
- [ ] **`POST /api/sessions/{session_id}/approve`** — `{call_id: str, approved: bool, edited_args?: dict}`
  - Look up pending approval Future by `call_id` on the session's `SessionBridge`
  - Resolve Future with approval result
  - Broadcast `ApprovalResolution` event to session subscribers
  - 404 if no pending approval with that call_id
- [ ] **`POST /api/sessions/{session_id}/input`** — `{request_id: str, response: str}`
  - Resolve pending input Future on session's bridge
  - Broadcast resolution event to session subscribers
- [ ] **`POST /api/sessions/{session_id}/message`** — `{content: str}`
  - Queue message for session bridge to inject into AgentLoop
  - Broadcast `UserMessage` event to session subscribers
- [ ] **`GET /api/state`** — fleet summary: `{total, running, waiting, idle}`
- [ ] **`vibecheck/tests/test_api.py`**
  - Test each endpoint with mock bridge
  - Test approve with no pending → 404
  - Test approve with pending → 200, Future resolved
  - Test all endpoints without PSK → 401

**Verify:**
```bash
uv run pytest vibecheck/tests/test_api.py -v
```

### WU-12: Vibe Bridge (`vibecheck/bridge.py`)

**Depends on:** WU-09, WU-10, WU-11
**Parallel with:** nothing (this is the critical integration piece)

- [ ] **`SessionBridge` class** — per-session bridge wrapping one AgentLoop
  - State: `idle | running | waiting_approval | waiting_input`
  - `session_id: str`
  - `pending_approval: dict[str, asyncio.Future]`
  - `pending_input: dict[str, asyncio.Future]`
  - `event_backlog: deque(maxlen=50)`
  - Reference to `ConnectionManager` for session-scoped broadcasting
  - `resolve_approval(call_id, approved, edited_args=None)` — resolve Future
  - `resolve_input(request_id, response)` — resolve Future
  - `inject_message(content)` — send user message to AgentLoop
- [ ] **`SessionManager` class** — discover and manage multiple sessions
  - `sessions: dict[str, SessionBridge]`
  - `discover()` — scan `~/.vibe/logs/session/`, return session metadata
  - `attach(session_id)` — create SessionBridge in `observe_only` mode (discovered sessions from unmanaged `vibe` processes cannot be live-controlled — Vibe has no IPC; live control requires `vibecheck-vibe`)
  - `detach(session_id)` — unhook callbacks, remove from active sessions
  - `get(session_id)` — return SessionBridge or raise 404
  - `list()` — return all sessions with status summary
  - `fleet_status()` — aggregate: `{total, running, waiting, idle}`
- [ ] **AgentLoop integration** (inside SessionBridge)
  - Import Vibe's `AgentLoop`, `VibeConfig`, `ToolManager`, etc.
  - `async def start_session(message: str, working_dir: Path)`
  - `set_approval_callback` → creates Future, broadcasts ApprovalRequest, awaits Future
  - `set_user_input_callback` → creates Future, broadcasts InputRequest, awaits Future
  - `message_observer` → convert Vibe events to our Pydantic models, broadcast to session subscribers
- [ ] **`vibecheck/tests/test_bridge.py`**
  - Mock AgentLoop (don't require real Vibe installation for tests)
  - Test: SessionBridge approval callback creates Future + broadcasts event
  - Test: resolve_approval resolves the correct Future
  - Test: SessionManager discover/attach/detach lifecycle
  - Test: state transitions
  - Test: fleet_status aggregation
  - Test: event backlog fills correctly

**Verify:**
```bash
uv run pytest vibecheck/tests/test_bridge.py -v
# Integration: start vibecheck with real Vibe, send message, verify events flow
```

---

## Phase 3: Live Attach (L1.5)

> **Parallelism:** WU-25 first, then WU-26 (can start slightly parallel with WU-25), then WU-27 (needs both), then WU-28 (integration test).
> **Fallback:** If VibeApp subclassing proves unworkable, fall back to tmux/PTY sidecar (Option C in `docs/ANALYSIS-session-attachment.md`).

This phase implements the core product promise: run Vibe in your terminal, walk away, control it from your phone. The terminal TUI and mobile PWA share the **same** AgentLoop in the **same** process. See `docs/ANALYSIS-session-attachment.md` for the full architecture decision.

### WU-25: Bridge `attach_to_loop()` (Phase 3)

**Depends on:** WU-12 (complete)
**Parallel with:** WU-26 (can start once interface is defined)

- [ ] **`SessionBridge.attach_to_loop(agent_loop, vibe_runtime)`** — wire callbacks on an **existing** AgentLoop
  - Calls `agent_loop.set_approval_callback()` with bridge's approval handler
  - Calls `agent_loop.set_user_input_callback()` with bridge's input handler
  - `message_observer` must be passed at `AgentLoop(...)` construction time (it's a constructor param, not a public setter — `MessageList` receives it in `__init__`). The launcher (WU-27) is responsible for creating the AgentLoop with bridge's observer wired in.
  - Does NOT create a new AgentLoop (unlike `_ensure_agent_loop()`)
  - Sets `self.attach_mode = "live"`
- [ ] **`attach_mode` field** on SessionBridge: `"live" | "replay" | "observe_only" | "managed"`
  - Default: `"managed"` (current behavior — bridge creates its own loop)
  - `"live"`: bridge attached to externally-created loop (via `attach_to_loop()`)
  - `"observe_only"`: discovered unmanaged session, read-only (no callback control)
- [ ] **`controllable` property** derived from `attach_mode`:
  - `True` for `live`, `managed`, `replay` (bridge owns or can drive the loop)
  - `False` for `observe_only` (no IPC to unmanaged process)
  - Frontend uses `controllable` to show/hide approve, input, and message controls
- [ ] **Update `state_payload()`** and **`SessionManager.session_detail()`** to include `attach_mode`
- [ ] **Update `_run_agent_turn()`** for live mode
  - Bridge is the **sole consumer** of `act()` in all modes (live and managed)
  - In `"live"` mode, the bridge drives `act()` and tees events to both the TUI renderer and WebSocket
  - The TUI does NOT call `act()` directly — it receives events from the bridge via `TuiBridge` callback
- [ ] **`vibecheck/tests/test_bridge.py`** additions:
  - Test: `attach_to_loop()` wires callbacks on FakeAgentLoop
  - Test: `attach_mode` appears in `state_payload()` as `"live"`
  - Test: approval/input callbacks work the same as managed mode
  - Test: `attach_mode` defaults to `"managed"` for existing behavior

**Verify:**
```bash
uv run pytest vibecheck/tests/test_bridge.py -v
```

### WU-26: Event Tee + TUI Bridge Rendering (Phase 3)

**Depends on:** WU-25
**Files:** `vibecheck/tui_bridge.py` (new), `vibecheck/tests/test_tui_bridge.py` (new)

- [ ] **`TuiBridge`** adapter that connects SessionBridge events to Textual's event handler
  - `on_bridge_event(event)` → calls Textual `event_handler.handle_event()`
  - Runs in the same asyncio loop as Textual (no threading needed)
- [ ] **Event tee**: when bridge processes `act()` events, fan out to both:
  - WebSocket broadcast (existing)
  - TUI renderer (new, via `TuiBridge`)
- [ ] **Override mechanism** for `_handle_agent_loop_turn`:
  - Bridge drives `act()` instead of TUI
  - TUI input (`on_chat_input_container_submitted`) posts to `bridge.inject_message()`
  - Bridge's `_message_worker` calls `act()` and broadcasts events
  - TUI receives events via the tee callback and renders them
- [ ] **Approval UI in TUI**: when bridge enters `waiting_approval`, TUI shows approve/deny controls
  - Either surface (TUI keyboard or mobile REST) can resolve the pending Future — first response wins
  - Both surfaces show pending state; resolution broadcasts to the other via WebSocket/callback
- [ ] **`vibecheck/tests/test_tui_bridge.py`**:
  - Mock TUI event handler, verify events reach it
  - Verify events reach both TUI and WebSocket consumers
  - Verify approval state indicator triggers on bridge state change

**Verify:**
```bash
uv run pytest vibecheck/tests/test_tui_bridge.py -v
```

### WU-27: VibeCheckApp + Launcher (Phase 3)

**Depends on:** WU-25, WU-26
**Files:** `vibecheck/launcher.py` (new), `vibecheck/tests/test_launcher.py` (new), `pyproject.toml`

- [ ] **`VibeCheckApp(VibeApp)`** Textual subclass:
  - Constructor takes `bridge: SessionBridge` + `ws_port: int`
  - `on_mount()`: override to NOT set TUI's own callbacks (bridge already owns them)
  - Start uvicorn as Textual worker (`self.run_worker(self._run_server())`)
  - Route keyboard input to `bridge.inject_message()`
  - Register bridge event callback for TUI rendering via `TuiBridge`
- [ ] **`launch()`** entry point function:
  - Parse CLI args (reuse Vibe's argparse + add `--ws-port`)
  - Load VibeConfig, create AgentLoop
  - Create SessionBridge, call `attach_to_loop()`
  - Create vibecheck FastAPI app, configure it with the bridge's session_manager
  - Create VibeCheckApp, pass bridge + agent_loop
  - `app.run()` — starts Textual TUI + uvicorn in same asyncio loop
- [ ] **`[project.scripts]`** entry in `pyproject.toml`: `vibecheck-vibe = "vibecheck.launcher:launch"`
- [ ] **Uvicorn config**: `log_level="warning"` to avoid terminal output interleaving with TUI
- [ ] **Spike: Textual + uvicorn in same asyncio loop** — validate this works before building the full launcher. If it fails, fall back to running uvicorn in a background thread with cross-loop bridges. This is the highest technical risk in Phase 3.
- [ ] **`vibecheck/tests/test_launcher.py`**:
  - Verify launcher creates components correctly (bridge, app, uvicorn config)
  - Verify `vibecheck-vibe` entry point is registered

**Verify:**
```bash
uv run pytest vibecheck/tests/test_launcher.py -v
# Manual: vibecheck-vibe starts, Textual TUI visible, curl localhost:7870/api/health returns ok
```

### WU-28: Live Attach Integration Test (Phase 3)

**Depends on:** WU-27
**Files:** `vibecheck/tests/test_live_attach.py` (new), `scripts/test_live_attach.sh` (new)

- [ ] **Integration test** (mocked AgentLoop, real FastAPI server, simulated TUI):
  - Start launcher with FakeAgentLoop
  - Connect WebSocket client
  - Send message via REST → verify events appear on WebSocket
  - Trigger approval → verify pending state on REST API
  - Approve via REST → verify AgentLoop proceeds
  - Verify `attach_mode: "live"` in session detail response
- [ ] **Shell script smoke test** (`scripts/test_live_attach.sh`):
  - Start `vibecheck-vibe` with a test config
  - curl health endpoint on :7870
  - websocat connects and receives events
  - Verify Textual TUI process is running (check PID)
- [ ] **Acceptance test** matches the product promise:
  > Terminal shows Vibe TUI. Phone shows vibecheck PWA. Pending approval visible on both surfaces.
  > Approve from phone → terminal shows tool proceeding. Phone shows tool result.

**Verify:**
```bash
uv run pytest vibecheck/tests/test_live_attach.py -v
scripts/test_live_attach.sh
```

---

## Phase 3.1: TUI Integration Hardening

> **Context:** Phase 3 proved bridge mechanics (60 tests). Phase 3.1 addresses Vibe Textual UI integration gaps that only manifest with the real app — discovered during Phase 3 code review. See `docs/ANALYSIS-session-attachment.md` § "Phase 3 Validation: Confirmed Gaps" for full technical analysis.
> **Parallelism:** WU-32 and WU-33 are independent and can run in parallel. WU-34 requires both. All three run in parallel with Phase 4 (Frontend Core).

### WU-32: TUI Approval/Question UI Cleanup on Remote Resolution (Phase 3.1)

**Depends on:** WU-28
**Parallel with:** WU-33, WU-13–15
**Files:** `vibecheck/bridge.py`, `vibecheck/launcher.py`, `vibecheck/tests/test_launcher.py`

**The problem:** `_settle_local_approval_state()` resolves the asyncio Future (layer 1) but doesn't trigger Vibe's Textual UI cleanup (layer 2). In Vibe, switching from the approval widget back to the input area happens in `on_approval_app_approval_granted` / `on_approval_app_approval_rejected` — Textual event handlers fired when the user clicks buttons, not when the Future resolves. After mobile resolves, the TUI stays stuck showing a dead approval dialog.

Same pattern for `_pending_question` / `on_question_app_answered` / `on_question_app_cancelled`.

- [ ] After `_settle_local_approval_state()` sets the Future result, trigger Vibe's UI cleanup:
  - **Preferred:** Fire a synthetic Textual message (`self.post_message(ApprovalAppApprovalGranted())` or equivalent) to trigger Vibe's existing event handler cleanup path
  - **Fallback:** Call `_switch_to_input_app()` directly on the VibeApp instance
  - Both approaches require accessing the VibeApp instance from the settle path — may need to pass app reference to bridge or use a callback
- [ ] Same fix for question UI: fire `QuestionAppAnswered` or call `_switch_to_question_complete_app()`
- [ ] Test: verify that after remote resolution, the TUI app receives the synthetic message and the UI state updates

**Verify:**
```bash
uv run pytest vibecheck/tests/test_launcher.py -v
# Manual: start vibecheck-vibe, trigger approval, approve from REST, confirm TUI exits approval UI
```

### WU-33: Remote Injection UX + Lifecycle Parity Audit (Phase 3.1)

**Depends on:** WU-28
**Parallel with:** WU-32, WU-13–15
**Files:** `vibecheck/tui_bridge.py`, `vibecheck/launcher.py`, `docs/ANALYSIS-session-attachment.md`

Two sub-items:

**A. Mobile-injected prompts invisible in TUI (document or fix):**

Vibe's `EventHandler.handle_event()` no-ops on `UserMessageEvent` (reference `event_handler.py:65`) because the TUI mounts the widget before `act()`. Phone-injected messages skip that mount.

- [ ] **Decision:** Fix or document as known limitation
  - **Fix:** In `TuiBridge.on_bridge_raw_event()`, detect `UserMessageEvent` and explicitly mount a user message widget via the Textual app
  - **Document:** Accept that terminal shows agent output but not phone-originated prompts. Phone user sees everything.
- [ ] If documenting: add to ANALYSIS § "Phase 3 Validation" and to README known limitations

**B. `_handle_agent_loop_turn` bypass audit:**

Our override routes keyboard input to `bridge.inject_message()`, dropping Vibe's loading widget, interrupt behavior, and history refresh.

- [ ] Document explicitly what's dropped and why it's acceptable:
  - `_agent_running` guard → replaced by bridge queue serialization (equivalent)
  - Loading widget → dropped (no "thinking" indicator)
  - Ctrl+C interrupt → dropped (can't interrupt running turn from terminal)
  - History refresh → dropped (stale if scrolling up)
- [ ] **Optional (nice-to-have):** Reintroduce loading widget — mount before inject, unmount via event listener when turn completes

**Verify:**
```bash
uv run pytest vibecheck/tests/test_tui_bridge.py vibecheck/tests/test_launcher.py -v
```

### WU-34: Manual Validation with Real Vibe (Phase 3.1)

**Depends on:** WU-32, WU-33
**Files:** (none — validation only, update WORKLOG.md with results)

Run the full acceptance test against a real Vibe installation. This is the test that unit tests cannot perform.

- [ ] Start `vibecheck-vibe` with real Vibe installed
- [ ] **Approval flow (primary):**
  - [ ] Trigger a tool call that requires approval
  - [ ] Approve from phone (REST API or PWA)
  - [ ] Agent continues after mobile approval
  - [ ] Terminal exits approval UI back to normal input (WU-32 fix)
- [ ] **Question/input flow (second callback surface):**
  - [ ] Trigger an `ask_user_question` prompt (e.g., a tool that asks for confirmation)
  - [ ] Respond from phone (REST API or PWA)
  - [ ] Terminal exits question UI back to normal input (WU-32 fix)
  - [ ] No stuck `_pending_question` future or orphaned question widget
- [ ] **Remote injection:**
  - [ ] Send a message from phone while at the terminal
  - [ ] Phone-injected user prompt is visible in terminal (or explicitly documented as known limitation per WU-33)
  - [ ] Loading widget behavior is acceptable (or documented per WU-33)
- [ ] **Reconnect/background (coffee-walk condition):**
  - [ ] Phone disconnects (close browser tab or lose connectivity) while approval is pending
  - [ ] Phone reconnects (reopen tab)
  - [ ] Pending approval state is visible on reconnect (backlog delivery)
  - [ ] Approve from phone after reconnect → agent continues, TUI updates
- [ ] **Cross-check:** No stuck tasks, no orphaned futures, no visual artifacts after all scenarios
- [ ] **Evidence requirements:**
  - [ ] Timestamped command log (terminal session transcript or `script` output)
  - [ ] Runtime context noted (at minimum Vibe version; commit hash optional)
  - [ ] Screenshots/recordings optional (not required for phase closure)
  - [ ] Pass/fail for each checklist item logged in WORKLOG.md

**Verify:**
```bash
# Manual test — no automated verification possible
# Log artifact locations or summary outputs in WORKLOG.md
```

---

## Phase 4: Frontend Core (L2)

> **Parallelism:** WU-13, WU-14, WU-15 can all start in parallel once WU-02 is done. WU-13 reuses code from Proto WU-03.
> **Note:** Frontend development can proceed in parallel with Phase 3.1 (TUI Hardening) since it depends only on the scaffold + prototypes.

### WU-13: FE WebSocket Client + Stores

**Depends on:** WU-02 (frontend scaffold), WU-03 (proto websocket-reconnect)
**Parallel with:** WU-14, WU-15

- [ ] **`lib/ws.js`** — adapted from Proto 1
  - `createWebSocket(url, psk)` → returns `{connect, disconnect, send, state}`
  - Auto-reconnect with exponential backoff (1s → 30s cap)
  - Heartbeat detection (45s timeout)
  - Parse JSON → dispatch to event store
  - Handle backlog on connect (merge with existing events)
- [ ] **`stores/connection.js`** — writable store
  - `{status: "connected"|"connecting"|"disconnected", reconnectAttempts: number}`
- [ ] **`stores/events.js`** — writable store
  - Append events, max 500 (FIFO)
  - Derived: `messages` (assistant + user events)
  - Derived: `pendingApproval` (latest approval_request without resolution)
  - Derived: `pendingInput` (latest input_request without resolution)
- [ ] **`lib/auth.js`** — PSK management
  - Read PSK from localStorage or URL hash
  - PSK entry screen if not set

**Verify:**
```bash
npm run build  # no errors
# Start replay_events.py on :7870, open frontend, verify events appear in console
```

### WU-14: FE Chat Components

**Depends on:** WU-02
**Parallel with:** WU-13, WU-15

- [ ] **`ChatMessage.svelte`**
  - Render assistant messages (left-aligned, dark bubble)
  - Render user messages (right-aligned, orange bubble)
  - Basic markdown: code blocks (```), inline code (`), bold, links
  - Timestamp display
- [ ] **`ToolCallCard.svelte`**
  - Collapsed: tool name badge + 1-line args preview
  - Expanded: full args JSON, syntax highlighted
  - Result section: appears when matching ToolResultEvent arrives
  - Error styling: red border + icon if `is_error`
  - Click to expand/collapse
- [ ] **`ConnectionStatus.svelte`**
  - Green/yellow/red dot + status text in header
  - Reconnect attempt count when reconnecting
- [ ] **Auto-scroll behavior**
  - Scroll to bottom on new event
  - If user has scrolled up (> 100px from bottom), don't auto-scroll
  - "New messages ↓" button when not at bottom

**Verify:**
```bash
npm run build
# Visual: mock data in stores → components render correctly
```

### WU-15: FE Approval Panel + Input Bar

**Depends on:** WU-02
**Parallel with:** WU-13, WU-14

- [ ] **`ApprovalPanel.svelte`** — sticky bottom panel
  - Shows when `$pendingApproval` is non-null
  - Tool name + args summary (1-2 lines)
  - Approve button (green) — POST to `/api/sessions/{session_id}/approve` with `approved: true`
  - Deny button (red) — POST to `/api/sessions/{session_id}/approve` with `approved: false`
  - Auto-hide after resolution (watch for approval_resolution event)
  - Loading state while POST is in-flight
- [ ] **`InputBar.svelte`** — bottom text input
  - Text input field + send button
  - Send → POST to `/api/sessions/{session_id}/message` or `/api/sessions/{session_id}/input` depending on state
  - Disabled when disconnected
  - Placeholder changes based on state: "Send a message..." vs "Answer the question..."
  - Enter key to send, Shift+Enter for newline
- [ ] Wire up to stores: `$pendingApproval`, `$pendingInput`, `$connection`

**Verify:**
```bash
npm run build
# Visual: set mock pendingApproval → panel appears → tap approve → panel hides
```

---

## Phase 5: Integration #1 — First Live Mobile Demo

> **GATE:** This is the critical convergence point. All subsequent work depends on this.
> **Depends on:** WU-12 (backend core) + WU-25–28 (live attach) + WU-32–34 (TUI hardening) + WU-13–15 (frontend core)

### WU-16: Integration + E2E Verification

- [ ] **Vite build output served by FastAPI**
  - `npm run build` → `vibecheck/static/`
  - `app.mount("/", StaticFiles(directory="static", html=True), name="static")`
  - Fallback: serve `index.html` for all non-API routes (SPA routing)
- [ ] **E2E test script** (`scripts/e2e_test.py`)
  - Start `vibecheck-vibe` (live attach mode) or `uv run python -m vibecheck` (standalone bridge mode)
  - Connect WebSocket client
  - Verify state event received with `attach_mode` field
  - Inject a message via POST `/api/sessions/{session_id}/message`
  - Verify UserMessage event on WebSocket
  - Simulate approval flow: set pending approval, POST `/api/sessions/{session_id}/approve`, verify resolution
  - Verify terminal TUI session is controllable from REST API (live attach validation)
- [ ] **Deploy to EC2**
  - Build frontend, push to EC2 (git pull or rsync)
  - Start via `vibecheck-vibe` (runs Textual TUI + WebSocket bridge in same process)
  - Fallback: `uv run python -m vibecheck` for standalone bridge without TUI
  - Caddy proxies :7870 → https://vibecheck.shisa.ai
- [ ] **Phone test checklist:**
  - [ ] Open `https://vibecheck.shisa.ai` → see UI
  - [ ] Connection indicator shows green
  - [ ] Events stream in from Vibe
  - [ ] Trigger tool call → approval panel appears
  - [ ] Tap Approve → Vibe continues
  - [ ] Type message → Vibe receives it
  - [ ] Test on Android Chrome (Pixel 9)

**Verify:**
```bash
uv run python scripts/e2e_test.py    # automated E2E
scripts/smoke_test.sh https://vibecheck.shisa.ai  # remote smoke test
```

---

## Phase 6: Feature Branches (L3–L5, parallel)

> **Parallelism:** After Integration #1, 6A, 6B, and 6D are fully independent. Assign to 3 separate agents. 6C depends on 6B.

### WU-17 + WU-18: Voice Input (L3)

**Depends on:** WU-16 (integration), WU-04 (proto media-recorder)
**Prior art:** `frontend-prototype/` has a complete Voxtral STT proxy (`POST /api/stt`) with Mistral API integration, multipart upload, error mapping, and backend tests. Frontend has MediaRecorder + transcript display. Port the proxy logic to `vibecheck/routes/voice.py` and adapt the Svelte recorder for `MicButton.svelte`.

**Backend (WU-17):**
- [ ] **`POST /api/voice/transcribe`** (`routes/voice.py`)
  - Accept raw body `audio/webm;codecs=opus` or multipart
  - `language` query param (default `ja`)
  - Proxy to: `mistral_client.audio.transcriptions.create(model="voxtral-mini-latest", file=audio_bytes)`
  - Return `{text, language, duration_ms}`
- [ ] **`vibecheck/tests/test_voice.py`**
  - Mock Mistral SDK, test endpoint with dummy audio
  - Test missing audio → 400
  - Test language param forwarding

**Frontend (WU-18):**
- [ ] **`lib/recorder.js`** — adapted from Proto 2
  - `startRecording()` / `stopRecording()` → returns Blob
  - Check `MediaRecorder.isTypeSupported("audio/webm;codecs=opus")`
- [ ] **`MicButton.svelte`**
  - Hold-to-record (touch + mouse events)
  - Pulsing red dot + duration counter
  - On release: POST blob to `/api/voice/transcribe`
  - Insert transcription text into InputBar (editable before send)
- [ ] **Language selector** in settings (JA / EN)

**Verify:**
```bash
uv run pytest vibecheck/tests/test_voice.py -v
# Phone: hold mic → speak → release → see transcription → send to Vibe
```

### WU-19 + WU-20: Push Notifications (L4a)

**Depends on:** WU-16, WU-05 (proto push-notifications)

**Backend (WU-19):**
- [ ] **VAPID key generation** — on first run, save to `~/.vibecheck/vapid_keys.json`
- [ ] **`routes/push.py`**
  - `GET /api/push/vapid-key` → public key
  - `POST /api/push/subscribe` — store subscription
  - `POST /api/push/unsubscribe` — remove subscription
- [ ] **Push triggers** in bridge:
  - On `approval_request` → push with `requireInteraction: true`
  - On `input_request` → push with `requireInteraction: true`
  - On error → push (normal priority)
- [ ] **`vibecheck/tests/test_push.py`**
  - Mock pywebpush, verify push sent on approval_request
  - Test subscribe/unsubscribe endpoints

**Frontend (WU-20):**
- [ ] **`sw.js`** push handler — adapted from Proto 3
  - `showNotification` with actions: Approve / Deny
  - `notificationclick` → open app or postMessage
- [ ] **`lib/push.js`**
  - Subscribe with VAPID key from server
  - Send subscription to backend
- [ ] "Enable notifications" prompt in settings

**Verify:**
```bash
uv run pytest vibecheck/tests/test_push.py -v
# Phone: subscribe → close app → trigger approval → phone buzzes → tap → app opens
```

### WU-21: Japanese Auto-Translation (L5)

**Depends on:** WU-16
**Parallel with:** WU-17/18, WU-19/20

**Backend:**
- [ ] **`POST /api/translate`** (`routes/translate.py`)
  - `{text, source_lang?, target_lang}` → `{translated_text, source_lang, target_lang}`
  - Use `mistral-large-latest`, `temperature=0.1`
  - System prompt: preserve code blocks, file paths, technical terms untranslated; preserve markdown
- [ ] **`vibecheck/tests/test_translate.py`**
  - Mock Mistral SDK, verify prompt construction
  - Test code block preservation instruction in prompt

**Frontend:**
- [ ] Per-message `🌐` toggle → calls `/api/translate`, swaps content
- [ ] Client-side cache by event ID (don't re-translate)
- [ ] CJK ratio detection: if > 30% CJK characters, skip translation
- [ ] Global auto-translate toggle in settings

**Verify:**
```bash
uv run pytest vibecheck/tests/test_translate.py -v
# Phone: English message → tap 🌐 → Japanese appears → tap again → English back
```

### WU-22: Smart Notifications — Ministral (L4b)

**Depends on:** WU-19 (push backend)

- [ ] **`notifications/ministral.py`**
  - `generate_notification_copy(tool_name, args) → str` (max 80 chars)
  - `classify_urgency(event) → "low" | "normal" | "high"`
  - `summarize_tool_call(tool_name, args) → str` (1-line)
  - Use `ministral-8b-latest`
- [ ] **`notifications/manager.py`** — IntensityManager
  - 5 levels: Chill, Vibing (default), Dialed In, Locked In, Ralph
  - Filter matrix: which events push at each level
  - Escalating idle alerts (5min, 10min, 15min, 30min)
  - Snooze: 30min / 1hr / Until Morning (never suppresses approval/question/error)
- [ ] Tests for urgency classification, intensity filtering, snooze logic

**Verify:**
```bash
uv run pytest vibecheck/tests/ -k "ministral or intensity" -v
```

---

## Phase 7: Polish (L6)

**Depends on:** WU-16 (integration gate); WU-24 must land before WU-23 can wire up diff UI.

> **Note:** Basic session listing and switching are built into L1/L2 (SessionManager + session switcher). This phase adds deeper session features: resume past sessions, diff viewing.

### WU-24: Backend Session Resume + Diff Endpoints

**Depends on:** WU-12 (SessionManager already handles discover/attach/list)
**Parallel with:** WU-17–WU-22 (feature WUs after integration gate)

- [ ] **`POST /api/sessions/{session_id}/resume`** — reattach SessionBridge to a past/disconnected session
- [ ] **`GET /api/sessions/{session_id}/diffs`** — return file-change diffs produced during session
- [ ] **Tests** — `vibecheck/tests/test_sessions.py`
  - Resume reattaches bridge and returns event backlog
  - Diffs endpoint returns structured before/after data
  - Resume of already-attached session is a no-op

**Verify:**
```bash
uv run pytest vibecheck/tests/test_sessions.py -v
```

### WU-23: Polish & UX (Frontend)

**Depends on:** WU-16, WU-24

- [ ] **Session detail view** — tap session in switcher → expanded view with event backlog
- [ ] **Session resume** — tap disconnected session → reattach via `POST /api/sessions/{session_id}/resume`
- [ ] **Settings panel** — `SettingsPanel.svelte`
  - Intensity slider (if L4b done)
  - Translation toggle + voice language
  - Notification on/off
  - Theme toggle
- [ ] **Dark/light theme** — CSS custom properties, `prefers-color-scheme` default
- [ ] **Tool call diff viewer** — for write_file/search_replace: `GET /api/sessions/{session_id}/diffs` → before/after
- [ ] **Offline cache** — store last 50 events in localStorage, render on reconnect
- [ ] **Error states** — friendly messages, retry buttons
- [ ] **Loading states** — skeletons, spinners
- [ ] **Haptic feedback** — `navigator.vibrate(200)` on approval request

### WU-35: Gap 2 — Phone Prompts Visible in TUI (Stretch)

**Depends on:** WU-24
**Parallel with:** WU-23
**Design doc:** [`docs/PLAN-gap2.md`](./PLAN-gap2.md)

Stretch goal. Makes phone-injected user messages render as user bubbles in the Vibe TUI, eliminating the "ghost conversation" known limitation.

- [ ] Add mount callback (`mount_user_message`) from `VibeCheckApp` to `TuiBridge`
- [ ] `TuiBridge`: on raw `UserMessageEvent`, dispatch first (preserves `finalize_streaming()`), then mount user bubble via callback
- [ ] FIFO one-shot dedupe queue (`maxlen=32`) on `TuiBridge` — local prompts marked by `_handle_agent_loop_turn()` are skipped, remote prompts mount
- [ ] Mark the **rendered** prompt (after `_render_path_prompt()`), not raw input; mark only after `inject_message()` succeeds (no mark on failure = no stale state)
- [ ] Update `README.md` — remove Gap 2 known limitation
- [ ] Update `scripts/manual-test/manual-test.howto.md` — S6 becomes strict pass
- [ ] **Tests:**
  - TuiBridge mounts user bubble for unmarked `UserMessageEvent`
  - TuiBridge skips mount for locally marked prompt
  - `_handle_agent_loop_turn()` marks prompt only after successful inject
  - Graceful no-op when mount callback is `None`
  - No mark on inject failure — next remote event is not swallowed
  - Repeated identical local prompts each render exactly once (proves FIFO, not set)

**Pre-implementation:** Verify Vibe widget API per checklist in `docs/PLAN-gap2.md`.

**Verify:**
```bash
uv run pytest vibecheck/tests/test_tui_bridge.py vibecheck/tests/test_launcher.py -v
# Manual: S6 scenario strict pass (phone prompt visible as TUI user bubble)
```

---

## Phase 8: Stretch (L7–L9)

Stretch goals — implement if time allows. L7 (ElevenLabs TTS) is highest priority stretch because it targets the **Best Voice Use Case** prize ($2K-6K credits).

### L7: Advanced Voice + ElevenLabs TTS

> **Execution units (stretch):** These WUs activate only after Phase 5 gate is stable.

#### WU-29: L7 Backend — ElevenLabs TTS Proxy

**Depends on:** WU-16, WU-08 (proto validation)
**Parallel with:** WU-30, WU-31
**Prior art:** `frontend-prototype/server/server/app.py` has a working ElevenLabs streaming TTS proxy (`POST /api/tts`, `GET /api/voices`) with error mapping, voice list, and mocked tests (`frontend-prototype/server/tests/test_api.py`). Port to `vibecheck/routes/tts.py` and add PSK auth.

- [ ] **`POST /api/tts`** (`routes/tts.py`)
  - Accept `{text, language?, voice_id?}` → stream ElevenLabs response as `audio/mpeg`
  - Keep `ELEVENLABS_API_KEY` server-side
  - Default voice fallback via config/env (`ELEVENLABS_VOICE_ID`)
  - Error mapping: 401/402/429/5xx from ElevenLabs → user-safe API errors
- [ ] **`vibecheck/tests/test_tts.py`**
  - Mock ElevenLabs upstream streaming response + headers
  - Test auth missing/bad PSK → 401
  - Test upstream non-200 response handling
  - Test chunked response content type (`audio/mpeg`)

**Verify:**
```bash
uv run pytest vibecheck/tests/test_tts.py -v
```

#### WU-30: L7 Frontend — TTS Playback + Auto-Read

**Depends on:** WU-16, WU-29
**Parallel with:** WU-31
**Prior art:** `frontend-prototype/frontend/src/App.svelte` has browser audio playback of TTS responses (blob URL + Audio element). Adapt for auto-read on `AssistantEvent` and add voice selector wiring.

- [ ] Frontend TTS playback (`AudioContext` or `<audio>`)
  - On `AssistantEvent`: if auto-read enabled, fetch `/api/tts` → play audio
  - Play indicator (speaker icon animating while reading)
  - Tap to stop / skip
- [ ] Auto-read toggle in settings panel: "Read agent responses aloud" (off by default)
- [ ] Voice selector in settings (wired to `voice_id` payload)
- [ ] Browser `SpeechSynthesis` fallback if ElevenLabs is unavailable/quota-exhausted

**Verify:**
```bash
cd vibecheck/frontend && npm run build
# Manual: enable auto-read → trigger AssistantEvent → hear playback; force TTS failure → fallback speaks
```

#### WU-31: L7 Voice Loop — Walkie-Talkie + Realtime STT

**Depends on:** WU-17, WU-18, WU-29, WU-30
**Parallel with:** none (integration-heavy)

- [ ] Full voice loop UX:
  - Hold mic → Voxtral STT → agent processes → ElevenLabs TTS → hear response
  - State machine: `idle → recording → transcribing → waiting → speaking → idle`
  - Haptic feedback on state transitions
- [ ] Voxtral Realtime streaming transcription:
  - AudioWorklet PCM pipeline (16kHz mono)
  - WS path for streaming + partial subtitle updates

**Verify:**
```bash
scripts/smoke_test.sh http://localhost:7870
# Manual phone flow: hold-to-talk, live subtitles, spoken response
```

### L8: Spawn/Orchestrate & Rich Media

- [ ] L8: Spawn/kill sessions from mobile (`POST/DELETE /api/sessions`)
- [ ] L8: Camera → Mistral Large 3 multimodal (use Proto 4)

### L9: Smart Autonomy & Showmanship

- [ ] L9: Autonomy slider
- [ ] L9: Live demo mode (public read-only URL)
- [ ] L9: QR code for audience participation
- [ ] L9: Cost/token tracker

---

## Deployment Checklist

### Done
- [x] EC2: Ubuntu 24.04 LTS, Elastic IP 54.199.185.108
- [x] Security group: 22, 80, 443 open
- [x] DNS: `vibecheck.shisa.ai` → 54.199.185.108
- [x] Caddy 2.6.2: auto TLS (Let's Encrypt E7), reverse proxy → :7870
- [x] uv installed, repo cloned

### Remaining
- [ ] Vibe installed: `uv tool install mistral-vibe`
- [ ] `MISTRAL_API_KEY` in env (or `~/.vibe/.env`)
- [ ] `VIBECHECK_PSK` generated: `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] VAPID keys generated (by push notification backend on first run)
- [ ] systemd unit: vibecheck bridge
- [ ] systemd unit: Vibe (or tmux session)
- [ ] Test: full phone round-trip (open URL, see events, approve, send message)

---

*See also: [PLAN.md](./PLAN.md) (architecture), [README.md](../README.md) (product brief)*
