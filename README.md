# vibecheck

**Check your vibes from anywhere.**

vibecheck is a mobile PWA that lets you monitor and control [Mistral Vibe](https://github.com/mistralai/mistral-vibe) coding agents from your phone. Approve tool calls from your pocket, talk to your agent in Japanese, get push notifications when it needs you, and manage multiple sessions at once. Built for the Mistral Hackathon Tokyo.

```
Terminal (Textual TUI) ──┐
                         ├── vibecheck-vibe ── AgentLoop ── Mistral API
Phone (PWA) ─────────────┘
         ↕ HTTPS/WSS
  EC2 (Caddy → :7870)
```

---

## What It Does

- **Live event streaming** — Agent output, tool calls, reasoning, and errors stream to your phone in real time over WebSocket. No polling.
- **Approve/deny from your phone** — When Vibe needs permission to run a tool, a panel pops up on your phone. Tap approve. The agent keeps going. Works from either the terminal or the phone — first to respond wins.
- **Push notifications** — Close the app, walk away. Your phone buzzes when the agent needs you. VAPID Web Push, works on Android and iOS 16.4+.
- **Voice input** — Hold the mic button, speak (Japanese, English, whatever), Voxtral transcribes it, and it goes straight to Vibe. ElevenLabs TTS reads agent responses back to you for a full voice loop.
- **Japanese auto-translation** — One toggle, and all English output gets translated to Japanese via Mistral Large. Code blocks and variable names stay untranslated.
- **Multi-session** — Discover, monitor, and switch between multiple running Vibe instances from one phone. Mission control for your AI fleet.
- **YOLO mode** — Auto-approve everything. Because you were going to anyway.

---

## Quick Start

### Prerequisites

- Python 3.12+ (via [uv](https://docs.astral.sh/uv/))
- Node.js 18+ (for building the frontend)
- A running EC2 instance with Caddy for HTTPS (or `localhost` for local dev, you can use `ngrok`, `tailscale`, or a similar tool to access the system from your phone without needing to be on the same network.)

### Environment Variables

```bash
# Required: pre-shared key for API auth (REST + WebSocket)
export VIBECHECK_PSK=your_secret_key

# Required for Vibe's coding agent + voice/translation features
export MISTRAL_API_KEY=your_mistral_key
```

### Install & Run

```bash
# Clone and install
git clone <repo-url> && cd vibecheck
uv sync

# Build the frontend (outputs to vibecheck/static/)
cd vibecheck/frontend && npm install && npm run build && cd ../..

# Run Vibe TUI + vibecheck bridge (recommended)
uv run vibecheck-vibe

# Or: server-only bridge (no terminal TUI)
uv run python -m vibecheck
```

Then open `https://your-domain/` (or `http://localhost:7870/`) on your phone, enter your PSK, pick a session, and connect.

> Push notifications and microphone require a secure context (HTTPS or `localhost`).

### Health Check

```bash
curl http://localhost:7870/api/health
curl -H "X-PSK: $VIBECHECK_PSK" http://localhost:7870/api/state
curl -H "X-PSK: $VIBECHECK_PSK" http://localhost:7870/api/sessions
```

---

## Architecture

vibecheck hooks directly into Vibe's Python event system — no terminal scraping, no tmux, no PTY bridging, and no upstream changes to Vibe. The `vibecheck-vibe` command wraps Vibe's CLI so the terminal TUI and the phone PWA share the **same `AgentLoop` in the same process**.

```
┌──────────────────────────────────────────────────────────────┐
│  EC2 Instance                                                │
│                                                              │
│  ┌──────────────────┐     ┌────────────────────────────────┐ │
│  │  Vibe AgentLoop  │────→│  vibecheck Bridge (FastAPI)    │ │
│  │  Events +        │←────│  WebSocket + REST on :7870     │ │
│  │  Callbacks       │     │                                │ │
│  └──────────────────┘     │  SessionManager                │ │
│                           │  Event broadcasting            │ │
│                           │  Voice / Translation / Push    │ │
│                           └──────────┬─────────────────────┘ │
│                           ┌──────────┴──────────┐            │
│                           │  Caddy (HTTPS/WSS)  │            │
│                           └──────────┬──────────┘            │
└──────────────────────────────────────┼───────────────────────┘
                                       │
                               ┌───────┴───────┐
                               │  Phone (PWA)  │
                               └───────────────┘
```

### Why Not Terminal Scraping?

Most mobile-to-agent bridges run the agent in tmux and shuttle raw terminal bytes to the phone. vibecheck takes a different path because Vibe exposes structured hooks:

- `AgentLoop.set_approval_callback()` — intercept tool approval requests
- `AgentLoop.set_user_input_callback()` — intercept agent questions
- `message_observer` — capture all events as typed Python objects

This means the phone gets `ToolCallEvent` as a tappable card with the tool name and args — not 40 columns of escape codes. Both surfaces resolve the same `asyncio.Future`, so approving from the phone or the terminal is equivalent.

The tradeoff: vibecheck is Vibe-specific. It hooks into Vibe's interfaces, not a generic terminal. Depth over breadth.

---

## Mistral Models Used

| Model | What It Does | Pricing |
|-------|-------------|---------|
| **Devstral 2** | Vibe's coding agent (the brain) | $0.40/M in, $2.00/M out |
| **Voxtral Mini** | Push-to-talk speech transcription | $0.003/min (batch), $0.006/min (realtime) |
| **Ministral 8B** | Notification copy, urgency classification, tool call summaries | $0.10/M in, $0.10/M out |
| **Mistral Large 3** | EN↔JA translation, camera/vision input | $2.00/M in, $6.00/M out |

### Partner API

| Service | What It Does |
|---------|-------------|
| **ElevenLabs** | Streaming TTS for agent responses — completes the voice loop (Voxtral in, ElevenLabs out). Supports 32 languages including Japanese. |

---

## Tech Stack

### Backend

| Component | Technology |
|-----------|-----------|
| Bridge server | FastAPI + Starlette (async) |
| WebSocket | Starlette WebSocket, room-based per session |
| Vibe integration | In-process `AgentLoop` hooks (same process as TUI) |
| Auth | PSK via `X-PSK` header or `?psk=` query param (timing-safe comparison) |
| Push notifications | pywebpush (VAPID) |

### Frontend

| Component | Technology |
|-----------|-----------|
| UI framework | Svelte 5 + Vite |
| PWA | Service Worker + Web App Manifest |
| Voice recording | MediaRecorder API (`audio/webm;codecs=opus`) |
| Push | Push API + Notification API |
| Build output | `vibecheck/static/` (served by FastAPI) |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Server | EC2 |
| Reverse proxy + TLS | Caddy (Let's Encrypt auto-cert) |
| Python | 3.12+ via uv |
| Process manager | systemd |

---

## API

All endpoints (except `/api/health`) require PSK auth via `X-PSK` header or `?psk=` query parameter.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check (no auth) |
| `GET` | `/api/state` | Fleet summary — N running, N waiting, N idle |
| `GET` | `/api/sessions` | List all discovered sessions with status |
| `GET` | `/api/sessions/{id}` | Session detail + event backlog |
| `POST` | `/api/sessions/{id}/approve` | Approve or deny a pending tool call |
| `POST` | `/api/sessions/{id}/input` | Respond to an agent question |
| `POST` | `/api/sessions/{id}/message` | Send a new user message to Vibe |
| `WS` | `/ws/events/{id}?psk=...` | Stream real-time events for a session |

---

## Development

### Backend Tests

```bash
uv run pytest vibecheck/tests/ -v
uv run pytest vibecheck/tests/ --cov=vibecheck --cov-report=term-missing
```

### Frontend Build

```bash
cd vibecheck/frontend
npm install
npm run build    # outputs to vibecheck/static/
npm run dev      # dev server with HMR
npm test         # vitest
```

After any frontend change, you must rebuild (`npm run build`) and restart the server for changes to go live. The build produces hashed filenames, so stale bundles won't match.

### Smoke Tests

```bash
scripts/smoke_test.sh http://localhost:7870
scripts/smoke_test.sh https://vibecheck.shisa.ai
```

### Event Replay (Frontend Dev Without Vibe)

```bash
uv run python scripts/replay_events.py --port 7870
```

Replays canned event sequences over WebSocket so you can develop the frontend without a running Vibe instance.

---

## Project Structure

```
vibecheck/
├── vibecheck/              # Python backend package
│   ├── bridge.py           # SessionBridge — per-session AgentLoop wrapper
│   ├── session_manager.py  # SessionManager — discover and manage sessions
│   ├── app.py              # FastAPI app, routes, WebSocket handler
│   ├── launcher.py         # vibecheck-vibe CLI entry point
│   ├── routes/             # Voice, translation, push, TTS endpoints
│   ├── frontend/           # Svelte 5 + Vite PWA source
│   │   └── src/
│   ├── static/             # Built frontend (served by FastAPI)
│   └── tests/              # pytest suite
├── docs/                   # Architecture docs, plans, analysis
├── demo/                   # Demo scripts and presentation materials
├── scripts/                # Smoke tests, event replay
├── prototypes/             # Standalone test pages
├── frontend-prototype/     # Standalone STT+TTS voice loop prototype
└── pyproject.toml          # uv/hatch project config
```

---

## How the Demo Works

The demo runs split-screen: terminal on the left (SSH into EC2 running `vibecheck-vibe`), phone mirrored via scrcpy on the right. The narrative:

1. **Core loop** — Events stream live to the phone. Approval prompt appears. Tap approve. Agent continues.
2. **Voice** — Hold mic, speak Japanese, Voxtral transcribes, send to Vibe. Agent responds, ElevenLabs reads it aloud.
3. **Push notifications** — Close the app. Phone buzzes. Approve from the lock screen.
4. **Translation** — Tap the translate toggle. Japanese appears. Code stays in English.
5. **Multi-session** — Switch between agents. Mission control.

Five Mistral models working together: **Devstral** codes, **Voxtral** transcribes, **Ministral** notifies, **Mistral Large** translates, **ElevenLabs** speaks.

See [demo/DEMO.md](demo/DEMO.md) for the full presentation script and setup checklist.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
