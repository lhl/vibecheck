# Design: Mistral Vibe Mobile Bridge — **vibecheck** ✅ — check your vibes from anywhere

> **Created:** 2026-02-28
> **Status:** Active
> **Working Name:** `vibecheck` (see [Naming](#naming))
> **Context:** Mistral Hackathon Tokyo (Japanese-friendly UX is a priority)
> **Related:** [mistral-vibe](https://github.com/mistralai/mistral-vibe)

## Goals

1. **Mobile web UI** for mistral-vibe — view agent output, send messages, approve/deny tool calls from your phone
2. **Push notifications** when Vibe is waiting for approval or user input
3. **Voice input (push-to-talk)** using Mistral's Voxtral transcription API so you can talk to Vibe from your phone
4. **Japanese auto-translation** — inline EN↔JA toggle on all messages for Tokyo Hackathon demo (with `🌐 自動翻訳` tag)
5. **EC2 direct deploy** — Caddy + Let's Encrypt on EC2, no tunnels needed (Tailscale available for local dev)
6. **Ministral micro-assistant** — notification copy (style-controlled), urgency classification, and tool call summaries
7. **Multi-session support** — discover, monitor, and switch between multiple running Vibe instances from one phone. Mission control for your AI fleet, not just a remote for one agent

---

## Quick Start

```bash
# Required: API auth for both REST + WebSocket (the PWA will prompt for this)
export VIBECHECK_PSK=YOUR_PSK

# Optional: enables cloud Devstral (Vibe) + voice/translation (push copy uses Ministral when set)
export MISTRAL_API_KEY=YOUR_KEY

# Recommended: Vibe TUI + vibecheck bridge (defaults to :7870)
uv run vibecheck-vibe

# Alternative: server-only bridge (serves built PWA from `vibecheck/static/`)
(cd vibecheck/frontend && npm run build)
uv run python -m vibecheck
```

---

## Running

### Terminal + phone (live attach)

```bash
uv run vibecheck-vibe
```

- Open the PWA at `https://your-domain/` (or `http://localhost:7870/` if local) and enter the PSK.
- Pick the live session from the dropdown and hit **Connect**.
- If `MISTRAL_API_KEY` is set and you haven't exported `VIBE_ACTIVE_MODEL`, `vibecheck-vibe` will prefer Vibe's `devstral-2` (Mistral API) over the `llamacpp` local model.

> Note: push notifications + microphone require a secure context (HTTPS or `localhost`).

### Server-only (no Vibe TUI)

```bash
(cd vibecheck/frontend && npm run build)
uv run python -m vibecheck
```

### Quick health/state checks

```bash
curl http://localhost:7870/api/health
curl -H "X-PSK: $VIBECHECK_PSK" http://localhost:7870/api/state
curl -H "X-PSK: $VIBECHECK_PSK" http://localhost:7870/api/sessions
```

## Hackathon Rubric Fit: Model Usage (Explicit)

- **Devstral 2**: Vibe's coding agent model. Vibecheck itself is built with Vibe.
- **Mistral Large 3**: EN↔JA translation with code preservation, plus optional multimodal/image reasoning.
- **Ministral**: notification copy (style-controlled), urgency classification, and 1-line tool call summaries.
- **Voxtral**: realtime voice transcription (push-to-talk UI), with a batch fallback.

### Model Pricing Snapshot (Official API Pricing)

> Last verified: 2026-02-28

| Model | Alias we use | Pricing | Typical latency |
|-------|---------------|---------|-----------------|
| Devstral 2 | `devstral-latest` | $0.40/M input, $2.00/M output tokens | Token-dependent (not fixed) |
| Mistral Small | `mistral-small-latest` | $0.10/M input, $0.30/M output tokens | Token-dependent (not fixed) |
| Mistral Large 3 (optional) | `mistral-large-latest` | $2.00/M input, $6.00/M output tokens | Token-dependent (not fixed) |
| Ministral 8B | `ministral-8b-latest` | $0.10/M input, $0.10/M output tokens | Token-dependent (not fixed) |
| Voxtral Mini (batch STT) | `voxtral-mini-latest` | $0.003/min audio | ~1–2s for short clips (network/audio dependent) |
| Voxtral Mini (realtime STT) | `voxtral-mini-transcribe-realtime-2602` | $0.006/min audio | 80ms–2.4s chunk latency (480ms recommended) |

### Partner API Usage

- **ElevenLabs** (stretch/L7): streaming TTS for agent responses — completes the voice loop (Voxtral STT in → ElevenLabs TTS out). Targets the **Best Voice Use Case** special prize. Supports 32 languages including Japanese.

---

## Naming

**Frontrunner: `vibecheck`** ✅ — `vibecheck` works better than `vibe-check` — it's one word, one concept, easier to type, and matches how people actually say it. The agent vibechecks *you* (notifications when it needs approval), and you vibecheck *it* (glance at your phone to see progress). The metaphor writes itself.

| Category | Name | Notes |
|----------|------|-------|
| **✅ Frontrunner** | **vibecheck** | "Checking on your Vibe" = notifications. Agent "vibechecks you" = approval requests. Meme-friendly, instantly understood, great hackathon energy. One word beats hyphenated — easier to type, say, and brand |
| Descriptive | vibe-remote | Clear, boring, accurate |
| Descriptive | vibe-mobile | Same energy |
| Descriptive | vibe-bridge | Follows claude-bridge convention |
| Descriptive | vibe-otg | "On the go" — but OTG = USB OTG to many devs |
| Voice-forward | vibe-talk | Simple, captures voice-first. "Talk to your Vibe" |
| Voice-forward | vibe-voice | Similar but less action-oriented |
| Voice-forward | ~~vibe-whisper~~ | Confusing (Whisper = OpenAI's ASR model) |
| Japanese 🇯🇵 | vibe-koe (声) | "Voice" in Japanese. Distinctive, memorable |
| Japanese 🇯🇵 | vibe-hanashi (話) | "Conversation/talk" |
| Japanese 🇯🇵 | vibegoe | Portmanteau of vibe + 声(koe), sounds like "vibe-go" |
| Playful | hey-vibe | Like calling out to it |
| Playful | **vibecheck** | See above ✅ |
| Playful | vibe-tap | Tap your phone, tap to approve |

### Why vibecheck Works Especially Well

- **Notification-first branding:** The core killer feature is knowing when your agent needs you. "Vibe check" = "is your vibe OK?" = exactly what the push notifications do
- **Bidirectional:** You check on Vibe (monitoring), Vibe checks on you (approval requests)
- **Hackathon-friendly:** Instantly memorable, easy to explain in a demo pitch
- **Push notification copy writes itself:**
  - 🔔 *"Vibe Check: bash wants to run `npm test`"*
  - 🔔 *"Vibe Check: Your agent has a question"*
  - 🔔 *"Vibe Check ✅: Task complete"*

---

## Table of Contents

- [Naming](#naming)
- [Why Vibe Is Different from Claude Code](#why-vibe-is-different-from-claude-code)
- [Architecture Overview](#architecture-overview)
- [Component Design](#component-design)
  - [Bridge Server (Python)](#bridge-server-python)
  - [Mobile Web Client (PWA)](#mobile-web-client-pwa)
  - [Voice Input Pipeline](#voice-input-pipeline)
  - [Notification System](#notification-system)
  - [Japanese Auto-Translation](#japanese-auto-translation)
- [Vibe Integration Points](#vibe-integration-points)
- [Networking / Tunnel Options](#networking--tunnel-options)
- [Voxtral API Reference](#voxtral-api-reference)
- [Implementation Plan](#implementation-plan)
- [Open Questions](#open-questions)

---

## Why Vibe Is Different from Claude Code

The claude-conduit/claude-bridge approach (tmux + node-pty + WebSocket terminal emulation) **does not directly apply** to mistral-vibe because:

| Aspect | Claude Code | Mistral Vibe |
|--------|-------------|--------------|
| **UI Framework** | Raw terminal (stdin/stdout) | Textual (Python TUI framework) |
| **Shell Access** | Interactive PTY session | Non-interactive subprocess (`stdin=DEVNULL`) |
| **I/O Model** | Terminal byte stream | Typed async events (`BaseEvent` hierarchy) |
| **Waiting States** | User types in terminal | `asyncio.Future` callbacks (approval + user input) |
| **Persistence** | Session snapshots | JSONL messages + metadata |

**Key insight:** Instead of emulating a terminal over WebSocket, we should **hook into Vibe's event system directly** — intercepting `BaseEvent` emissions and providing a custom `approval_callback` / `user_input_callback` that bridges to the mobile client.

This gives us a much cleaner, richer mobile experience than terminal scraping.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  EC2 Instance                                                            │
│                                                                          │
│  ┌──────────────────────┐                                                │
│  │  mistral-vibe #1      │     ┌──────────────────────────────────────┐  │
│  │  (AgentLoop)          │────→│  Vibe Bridge Server (Python)         │  │
│  │  Events + Callbacks   │←────│  FastAPI/Starlette on :7870          │  │
│  └──────────────────────┘     │                                      │  │
│  ┌──────────────────────┐     │  SessionManager                      │  │
│  │  mistral-vibe #2      │────→│    Dict[session_id, Bridge]         │  │
│  │  (AgentLoop)          │←────│    discover ~/.vibe/logs/session/    │  │
│  └──────────────────────┘     │    attach/detach per session         │  │
│  ┌──────────────────────┐     │                                      │  │
│  │  mistral-vibe #N      │────→│  WebSocket /ws/events/{session_id}  │  │
│  │  (AgentLoop)          │←────│    → stream events for one session  │  │
│  └──────────────────────┘     │                                      │  │
│                                │  REST API:                           │  │
│                                │  GET  /api/sessions                  │  │
│                                │  GET  /api/sessions/{session_id}     │  │
│                                │  POST /api/sessions/{session_id}/approve │  │
│                                │  POST /api/sessions/{session_id}/input   │  │
│                                │  POST /api/sessions/{session_id}/message │  │
│                                │  GET  /api/sessions/{session_id}/diffs   │  │
│                                │  GET  /api/state (fleet summary)     │  │
│                                │                                      │  │
│                                │  Notification / Voice / Translation  │  │
│                                │  (shared across all sessions)        │  │
│                                └──────────┬───────────────────────────┘  │
│                                           │                              │
│                                ┌──────────┴───────────────┐             │
│                                │  Caddy (Let's Encrypt)   │             │
│                                │  HTTPS + WSS on :443     │             │
│                                └──────────┬───────────────┘             │
└───────────────────────────────────────────┼──────────────────────────────┘
                                            │ HTTPS + WSS
                                            │
                                    ┌───────┴───────┐
                                    │    Phone      │
                                    │  PWA Browser  │
                                    │               │
                                    │  • Session    │
                                    │    switcher   │
                                    │  • Chat view  │
                                    │  • Approve/   │
                                    │    Deny panel │
                                    │  • 🎤 Voice   │
                                    │  • 🔔 Push    │
                                    └───────────────┘
```

---

## Component Design

### Bridge Server (Python)

Since Vibe is Python (async), the bridge server should also be Python to allow **in-process integration** — no subprocess/IPC overhead.

#### Option A: In-Process Plugin (Preferred)

Extend Vibe's `VibeApp` or `AgentLoop` directly:

```python
# vibe_bridge/server.py
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect
import asyncio
import json

class SessionBridge:
    """Bridge for a single Vibe AgentLoop session."""

    def __init__(self, session_id: str, agent_loop):
        self.session_id = session_id
        self.agent_loop = agent_loop
        self.clients: list[WebSocket] = []  # WS clients subscribed to this session
        self._pending_approval: asyncio.Future | None = None
        self._pending_input: asyncio.Future | None = None
        self._waiting_state: dict | None = None

        agent_loop.set_approval_callback(self._approval_callback)
        agent_loop.set_user_input_callback(self._user_input_callback)

class SessionManager:
    """Discover and manage multiple Vibe sessions."""

    def __init__(self):
        self.sessions: dict[str, SessionBridge] = {}

    def discover(self) -> list[dict]:
        """Scan ~/.vibe/logs/session/ for sessions."""
        ...

    def attach(self, session_id: str) -> SessionBridge:
        """Attach a bridge to a discovered session."""
        ...

    def detach(self, session_id: str):
        """Detach bridge, stop receiving events."""
        ...

class VibeBridge:
    """Top-level bridge server managing multiple Vibe sessions."""

    def __init__(self):
        self.app = FastAPI()
        self.session_manager = SessionManager()

        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.websocket("/ws/events/{session_id}")
        async def event_stream(ws: WebSocket, session_id: str):
            await ws.accept()
            self.clients.append(ws)
            try:
                # Keep alive, receive client messages
                while True:
                    data = await ws.receive_text()
                    msg = json.loads(data)
                    await self._handle_client_message(msg)
            except WebSocketDisconnect:
                self.clients.remove(ws)
        
        @self.app.post("/api/sessions/{session_id}/approve")
        async def approve(session_id: str, decision: ApprovalDecision):
            if self._pending_approval:
                self._pending_approval.set_result(
                    (decision.verdict, decision.feedback)
                )
                self._waiting_state = None
                return {"status": "ok"}
            return {"status": "no_pending_approval"}
        
        @self.app.post("/api/sessions/{session_id}/input")
        async def user_input(session_id: str, response: UserInputResponse):
            if self._pending_input:
                self._pending_input.set_result(response.text)
                self._waiting_state = None
                return {"status": "ok"}
            return {"status": "no_pending_input"}
        
        @self.app.post("/api/sessions/{session_id}/message")
        async def send_message(session_id: str, msg: MessageRequest):
            """Send a new user message to Vibe."""
            # Queue for the agent loop
            asyncio.create_task(self._inject_message(msg.text))
            return {"status": "queued"}
        
        @self.app.get("/api/state")
        async def get_state():
            """Get current agent state: running, waiting_approval, waiting_input, idle."""
            return {
                "state": self._get_state(),
                "waiting_context": self._waiting_state,
            }
    
    # --- Callbacks that Vibe's AgentLoop will call ---
    
    async def _approval_callback(self, tool_name, args, tool_call_id):
        """Called by Vibe when it needs tool execution approval."""
        self._pending_approval = asyncio.Future()
        self._waiting_state = {
            "type": "approval",
            "tool_name": tool_name,
            "args": args,
            "tool_call_id": tool_call_id,
        }
        
        # Notify all clients + send push notification
        await self._broadcast({
            "type": "waiting_approval",
            "tool_name": tool_name,
            "args": args,
            "tool_call_id": tool_call_id,
        })
        await self._send_push_notification(
            title="Vibe Check 🔧",
            body=f"{tool_name}: wants to run",
        )
        
        result = await self._pending_approval
        self._pending_approval = None
        return result
    
    async def _user_input_callback(self, args):
        """Called by Vibe when it asks the user a question."""
        self._pending_input = asyncio.Future()
        self._waiting_state = {
            "type": "user_input",
            "question": args.question if hasattr(args, 'question') else str(args),
        }
        
        await self._broadcast({
            "type": "waiting_input",
            "question": self._waiting_state["question"],
        })
        await self._send_push_notification(
            title="Vibe Check ❓",
            body=self._waiting_state["question"][:100],
        )
        
        result = await self._pending_input
        self._pending_input = None
        return result
    
    # --- Event broadcasting ---
    
    async def _broadcast(self, event: dict):
        """Send event to all connected WebSocket clients."""
        data = json.dumps(event)
        disconnected = []
        for ws in self.clients:
            try:
                await ws.send_text(data)
            except:
                disconnected.append(ws)
        for ws in disconnected:
            self.clients.remove(ws)
    
    async def _send_push_notification(self, title: str, body: str):
        """Send Web Push notification via VAPID."""
        # See Notification System section
        pass
```

#### Option B: Sidecar Process (Fallback)

If modifying Vibe's internals is undesirable, run a sidecar that:

1. Launches Vibe inside tmux (like claude-conduit)
2. Watches `~/.vibe/logs/session/` JSONL files (like claude-conduit watches `~/.claude/projects/`)
3. Polls tmux capture-pane for terminal output
4. Detects "waiting" state by parsing terminal content for Vibe's approval UI patterns

This is less clean but requires zero Vibe modifications.

---

### Mobile Web Client (PWA)

#### UI Components

```
┌────────────────────────────────────┐
│  🟢 Vibe Mobile           🔔 ⚙️   │  ← Status bar (connected/disconnected)
├────────────────────────────────────┤
│                                    │
│  🤖 Assistant                      │  ← Chat messages (scrollable)
│  I'll create a new REST endpoint   │
│  for user authentication...        │
│                                    │
│  🔧 Tool: write_file              │  ← Tool call (collapsible)
│  📁 src/auth/handler.py           │
│  ├─ args: { path: "src/..." }     │
│  └─ ✅ Result: File written        │
│                                    │
│  🧠 Reasoning                      │  ← Reasoning block (collapsible)
│  Let me think about the best...    │
│                                    │
│  ⚠️ APPROVAL NEEDED               │  ← Approval banner (sticky)
│  ┌────────────────────────────────┐│
│  │ 🔧 bash                        ││
│  │ $ npm test                     ││
│  │                                ││
│  │  [✅ Approve]  [❌ Deny]       ││
│  │  [📝 Edit & Approve]          ││
│  └────────────────────────────────┘│
│                                    │
├────────────────────────────────────┤
│  [🎤]  Type or speak...    [Send]  │  ← Input bar with mic button
└────────────────────────────────────┘
```

#### Key Features

1. **Structured event rendering** — not terminal emulation, but proper chat UI with typed message components
2. **Sticky approval/input panels** — always visible when Vibe is waiting
3. **Collapsible tool calls** — show tool name + result summary, expand for full args/output
4. **Reasoning blocks** — collapsible, dimmed styling
5. **Voice button** — push-to-talk (tap-and-hold) to record, sends to Voxtral for transcription

#### PWA Manifest

```json
{
    "name": "Vibe Mobile",
    "short_name": "Vibe",
    "display": "standalone",
    "orientation": "portrait",
    "theme_color": "#FF7000",
    "background_color": "#1a1a1a",
    "start_url": "/",
    "icons": [
        { "src": "/icons/vibe-192.png", "sizes": "192x192", "type": "image/png" },
        { "src": "/icons/vibe-512.png", "sizes": "512x512", "type": "image/png" }
    ]
}
```

#### Service Worker (Notifications + Offline)

```javascript
// sw.js
self.addEventListener('push', (event) => {
    const data = event.data.json();
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/icons/vibe-192.png',
            badge: '/icons/vibe-badge.png',
            tag: data.tag || 'vibe-notification',
            requireInteraction: true,  // Stay until user acts
            actions: data.type === 'approval' ? [
                { action: 'approve', title: '✅ Approve' },
                { action: 'deny', title: '❌ Deny' },
            ] : [],
            vibrate: [200, 100, 200],
            data: data,
        })
    );
});

self.addEventListener('notificationclick', (event) => {
    const action = event.action;
    const data = event.notification.data;
    
    if (action === 'approve' || action === 'deny') {
        // Quick-action from notification without opening app
        event.waitUntil(
            fetch(`/api/sessions/${data.session_id}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    approved: action === 'approve',
                    tool_call_id: data.tool_call_id,
                }),
            })
        );
    } else {
        // Open the app
        event.waitUntil(clients.openWindow('/'));
    }
    event.notification.close();
});
```

---

### Voice Input Pipeline

Use Mistral's **Voxtral Mini Transcribe** (`voxtral-mini-latest`) via API for batch transcription of recorded audio, or **Voxtral Realtime** (`voxtral-mini-transcribe-realtime-2602`) for live streaming.

#### Approach A: Push-to-Talk Record-and-Send (Simpler, Recommended for Mobile)

```
Phone Mic → MediaRecorder (webm/opus) → POST /api/voice/transcribe → Voxtral API → Text → Inject as message
```

**Browser side:**
```javascript
class VoiceInput {
    constructor(bridge) {
        this.bridge = bridge;
        this.mediaRecorder = null;
        this.chunks = [];
    }
    
    async startRecording() {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: { 
                channelCount: 1,
                sampleRate: 16000,
                echoCancellation: true,
                noiseSuppression: true,
            } 
        });
        
        this.mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus',
        });
        
        this.chunks = [];
        this.mediaRecorder.ondataavailable = (e) => this.chunks.push(e.data);
        this.mediaRecorder.onstop = () => this._sendToTranscribe();
        this.mediaRecorder.start();
        
        // Visual feedback
        document.getElementById('mic-btn').classList.add('recording');
    }
    
    stopRecording() {
        this.mediaRecorder?.stop();
        this.mediaRecorder?.stream.getTracks().forEach(t => t.stop());
        document.getElementById('mic-btn').classList.remove('recording');
    }
    
    async _sendToTranscribe() {
        const blob = new Blob(this.chunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', blob, 'voice.webm');
        
        const resp = await fetch('/api/voice/transcribe', {
            method: 'POST',
            body: formData,
        });
        const { text } = await resp.json();
        
        if (text?.trim()) {
            // Show transcribed text in input, let user confirm or edit
            document.getElementById('chat-input').value = text;
            // Or auto-send:
            // this.bridge.sendMessage(text);
        }
    }
}

// Push-to-talk wiring (tap-and-hold)
const voiceInput = new VoiceInput(bridge);
const micBtn = document.getElementById('mic-btn');
micBtn.addEventListener('pointerdown', () => voiceInput.startRecording());
micBtn.addEventListener('pointerup', () => voiceInput.stopRecording());
micBtn.addEventListener('pointerleave', () => voiceInput.stopRecording());
```

**Server side (proxy to Voxtral API):**
```python
from mistralai import Mistral
import os

mistral_client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

@app.post("/api/voice/transcribe")
async def voice_transcribe(audio: UploadFile):
    """Transcribe uploaded audio via Voxtral Mini Transcribe API."""
    content = await audio.read()
    
    response = mistral_client.audio.transcriptions.complete(
        model="voxtral-mini-latest",  # points to voxtral-mini-2602
        file={
            "content": content,
            "file_name": audio.filename or "voice.webm",
        },
        language="en",  # or detect
    )
    
    return {"text": response.text}
```

#### Approach B: Live Streaming (Lower Latency, More Complex)

Stream mic audio chunks over WebSocket to server, which forwards to Voxtral Realtime API:

```
Phone Mic → AudioWorklet (PCM 16kHz) → WS /ws/voice → Server → Voxtral Realtime WS → Partial text deltas → WS back to phone
```

**Server side (streaming proxy):**
```python
from mistralai.extra.realtime import UnknownRealtimeEvent
from mistralai.models import AudioFormat, TranscriptionStreamTextDelta

@app.websocket("/ws/voice")
async def voice_stream(ws: WebSocket):
    """Stream mic audio to Voxtral Realtime, return text deltas."""
    await ws.accept()
    
    audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=16000)
    
    async def audio_from_client():
        """Yield audio chunks from the WebSocket client."""
        try:
            while True:
                data = await ws.receive_bytes()
                yield data
        except WebSocketDisconnect:
            return
    
    async for event in mistral_client.audio.realtime.transcribe_stream(
        audio_stream=audio_from_client(),
        model="voxtral-mini-transcribe-realtime-2602",
        audio_format=audio_format,
    ):
        if isinstance(event, TranscriptionStreamTextDelta):
            await ws.send_json({
                "type": "transcript_delta",
                "text": event.text,
            })
```

**Cost comparison:**
| Model | Price | Latency | Use Case |
|-------|-------|---------|----------|
| `voxtral-mini-latest` (batch) | $0.003/min | ~1-2s for short clips | Tap-to-record, release to send |
| `voxtral-mini-transcribe-realtime-2602` | $0.006/min | <500ms | Live dictation with streaming text |

**Recommendation:** Start with **Approach A** (push-to-talk record-and-send). It's simpler, cheaper, and the UX of "hold mic button, release, see text, confirm" is well-understood on mobile. Add Approach B later for live dictation if needed.

---

### Voice Output — ElevenLabs TTS (Stretch/L7)

Completes the voice loop: Voxtral handles speech-to-text (input), ElevenLabs handles text-to-speech (output). Together they enable a full conversational experience with your agent.

**Why ElevenLabs over browser SpeechSynthesis:**
- Much higher quality, natural-sounding voices
- 32 languages including Japanese (critical for Tokyo demo)
- Streaming support for low-latency playback
- Targets the **Best Voice Use Case** special prize ($2K-6K in credits)

#### Architecture

```
Agent AssistantEvent → vibecheck server → POST /api/tts → ElevenLabs Streaming TTS API
                                                              ↓
                                           audio/mpeg chunks streamed back
                                                              ↓
                                              Phone: AudioContext playback
```

#### Server-side TTS proxy

```python
from fastapi import Response
from fastapi.responses import StreamingResponse
import httpx

ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "Rachel")  # default voice

@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    """Stream ElevenLabs TTS audio back to client."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{req.voice_id or ELEVENLABS_VOICE_ID}/stream",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": req.text,
                "model_id": "eleven_multilingual_v2",  # supports JA + EN
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
        )
        return StreamingResponse(
            response.aiter_bytes(),
            media_type="audio/mpeg",
        )
```

#### Client-side playback

```javascript
async function speakText(text, voiceId) {
    const response = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice_id: voiceId }),
    });

    const audioContext = new AudioContext();
    const audioData = await response.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(audioData);
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContext.destination);
    source.start();
}
```

#### Full Voice Loop (Walkie-Talkie Mode)

```
Hold mic → Voxtral STT → text → agent processes → AssistantEvent → ElevenLabs TTS → hear response
   🎤          📝              🤖                        🔊
```

State machine: `idle → recording → transcribing → agent_working → speaking → idle`

#### Fallback

If ElevenLabs quota is exhausted or unavailable, fall back to browser `SpeechSynthesis` API (free, lower quality, still supports Japanese on most devices).

---

### Notification System

#### Web Push Notifications (VAPID)

The gold standard for mobile browser notifications that work even when the tab is closed.

**Server setup:**
```python
# pip install pywebpush
from pywebpush import webpush, WebPushException
import json

VAPID_PRIVATE_KEY = os.environ["VAPID_PRIVATE_KEY"]
VAPID_PUBLIC_KEY = os.environ["VAPID_PUBLIC_KEY"]  # Share with client
VAPID_CLAIMS = {"sub": "mailto:you@example.com"}

# Store client subscriptions
push_subscriptions: list[dict] = []

@app.post("/api/push/subscribe")
async def push_subscribe(subscription: dict):
    """Register a client's push subscription."""
    push_subscriptions.append(subscription)
    return {"status": "subscribed"}

async def send_push_notification(title: str, body: str, data: dict = {}):
    """Send push notification to all subscribed clients."""
    payload = json.dumps({
        "title": title,
        "body": body,
        "type": data.get("type", "info"),
        "tool_call_id": data.get("tool_call_id"),
        **data,
    })
    
    for sub in push_subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
            )
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                push_subscriptions.remove(sub)  # Expired subscription
```

**Client registration:**
```javascript
// Register service worker + subscribe to push
async function setupPushNotifications() {
    const registration = await navigator.serviceWorker.register('/sw.js');
    
    const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
    });
    
    // Send subscription to our server
    await fetch('/api/push/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(subscription.toJSON()),
    });
}
```

**Generate VAPID keys:**
```bash
# One-time setup
uv add pywebpush
uv run python -c "
from pywebpush import webpush
from py_vapid import Vapid
v = Vapid()
v.generate_keys()
print('Private:', v.private_pem())
print('Public:', v.public_key)
"
```

#### When Notifications Fire

| Vibe State | Notification | Priority |
|------------|-------------|----------|
| `_pending_approval` set | "🔧 Vibe Check: `bash` wants to run `npm test`" | High (requireInteraction) |
| `_pending_input` set | "❓ Vibe Check: Your agent has a question" | High (requireInteraction) |
| Agent error/crash | "⚠️ Vibe Check: Something went wrong" | Normal |
| Agent task complete | "✅ Vibe Check: Task complete" | Low (optional) |
| Agent idle timeout | "💤 Vibe Check: Agent idle for 5min" | Low (optional) |

#### Ministral-Powered Notification Copy + Urgency + Tool Summaries

Use **Ministral** to turn raw events into short, human-friendly push text and a simple urgency class. Also produce a 1-line tool summary for the approval banner.

**Style spec (example):**
```json
{
  "tone": "short, calm, slightly playful",
  "max_chars": 80,
  "emojis": "errors_only",
  "language": "en"
}
```

**Output contract:** `title`, `body`, `urgency`, `tool_summary`  
Map `urgency` to push priority and intensity behavior.

#### Notification Actions (Quick Approve/Deny)

Push notifications can include **action buttons** that work without opening the app:

```
┌──────────────────────────────────┐
│ 🔧 Vibe Check                   │
│ bash wants to run: npm test      │
│                                  │
│  [✅ Approve]    [❌ Deny]       │
└──────────────────────────────────┘
```

This is handled in the service worker's `notificationclick` event (see PWA section above).

#### Intensity Mode ("How Hard Are You Going?")

A fun, opinionated notification dial that controls how aggressively vibe-check nags you. Think of it as a **focus/commitment level** — how locked-in are you right now?

```
┌──────────────────────────────────────┐
│  🔥 Intensity                        │
│                                      │
│  😴 ──────●────────────────── 🔥     │
│  Chill            ↑           Locked │
│                 Vibing               │
│                                      │
│  Currently: Vibing                   │
│  "Approval alerts + idle nudges"     │
│                                      │
│  💤 Snooze: [30m] [1h] [Until AM]   │
└──────────────────────────────────────┘
```

**Intensity Levels:**

| Level | Name | Emoji | Behavior |
|-------|------|-------|----------|
| 1 | **Chill** | 😴 | Only notify on errors/crashes. Agent runs free, you'll check in later |
| 2 | **Vibing** | 🎵 | Approval requests + questions only. No idle alerts. Default level |
| 3 | **Dialed In** | 🎯 | Above + task completion alerts + idle nudges (5min) |
| 4 | **Locked In** | 🔥 | Above + progress updates every N tool calls + escalating idle alerts |
| 5 | **Ralph** | 💀 | Everything. Repeat notifications if ignored. Buzzes every 30s when waiting. Named after [Ralph Wiggum](https://github.com/anthropics/claude-code/issues/1774), the Claude Code extension that force-loops the agent. Your agent won't stop and neither will your notifications |

**Escalating idle alerts (levels 3+):**

```
  0:00  Agent finishes task, waits for input
  5:00  💤 "Vibe Check: Agent idle for 5min"
 10:00  😐 "Vibe Check: Still waiting on you..."
 15:00  🫠 "Vibe Check: Your agent is getting lonely"        (Locked In+)
 30:00  💀 "Vibe Check: HELLO? Agent has been idle for 30min" (Ralph mode only)
```

**Snooze:**

When you get an idle/progress notification but you're busy:

```
┌──────────────────────────────────────┐
│ 💤 Vibe Check: Agent idle for 5min   │
│                                      │
│ [😴 Snooze 30m]  [⏰ Snooze 1h]     │
│ [🌙 Until Morning]  [👀 Open App]   │
└──────────────────────────────────────┘
```

Snooze suppresses idle/progress notifications but **never** suppresses approval/question/error notifications — those always come through because the agent is literally blocked.

**Implementation:**

```python
class IntensityManager:
    """Controls notification aggressiveness."""
    
    LEVELS = {
        1: "chill",      # 😴
        2: "vibing",     # 🎵 (default)
        3: "dialed_in",  # 🎯
        4: "locked_in",  # 🔥
        5: "ralph",      # 💀
    }
    
    def __init__(self):
        self.level = 2  # Default: vibing
        self.snooze_until: datetime | None = None
        self.idle_since: datetime | None = None
        self._idle_notify_count = 0
    
    def should_notify(self, event_type: str) -> bool:
        """Determine if we should send a push notification."""
        
        # Approval + question + error: ALWAYS notify (agent is blocked)
        if event_type in ("approval", "user_input", "error"):
            return True
        
        # Snoozed? Suppress non-critical
        if self.snooze_until and datetime.now() < self.snooze_until:
            return False
        
        # Level-based filtering
        match self.level:
            case 1:  # Chill: errors only (already handled above)
                return False
            case 2:  # Vibing: approval + questions only (already handled above)
                return False
            case 3:  # Dialed In: + completion + idle
                return event_type in ("task_complete", "idle")
            case 4:  # Locked In: + progress updates
                return event_type in ("task_complete", "idle", "progress")
            case 5:  # Ralph: everything + repeated
                return True
    
    def get_idle_message(self) -> tuple[str, str] | None:
        """Get escalating idle notification copy."""
        if not self.idle_since:
            return None
        
        minutes = (datetime.now() - self.idle_since).total_seconds() / 60
        self._idle_notify_count += 1
        
        if minutes < 5:
            return None
        elif minutes < 10:
            return ("💤 Vibe Check", "Agent idle for 5min")
        elif minutes < 15:
            return ("😐 Vibe Check", "Still waiting on you...")
        elif minutes < 30:
            return ("🫠 Vibe Check", "Your agent is getting lonely")
        else:
            return ("💀 Vibe Check", f"HELLO? Agent idle for {int(minutes)}min")
    
    def snooze(self, duration: str):
        """Snooze non-critical notifications."""
        match duration:
            case "30m":
                self.snooze_until = datetime.now() + timedelta(minutes=30)
            case "1h":
                self.snooze_until = datetime.now() + timedelta(hours=1)
            case "morning":
                tomorrow = datetime.now().replace(hour=8, minute=0)
                if tomorrow < datetime.now():
                    tomorrow += timedelta(days=1)
                self.snooze_until = tomorrow
```

**Client-side intensity selector:**
```javascript
// Intensity dial — could be a slider or segmented control
const intensityLevels = [
    { level: 1, emoji: '😴', name: 'Chill',     desc: 'Errors only. Agent runs free.' },
    { level: 2, emoji: '🎵', name: 'Vibing',    desc: 'Approval + questions. Default.' },
    { level: 3, emoji: '🎯', name: 'Dialed In', desc: '+ completion + idle nudges' },
    { level: 4, emoji: '🔥', name: 'Locked In', desc: '+ progress + escalating alerts' },
    { level: 5, emoji: '💀', name: 'Ralph',     desc: 'Everything. Repeated. Relentless. 🚌' },
];
```

---

### Japanese Auto-Translation

#### Context: Tokyo Hackathon

For the hackathon demo, we want the UI to be accessible to Japanese-speaking audience members. Since Vibe's agent output (code explanations, tool descriptions, reasoning) is typically in English, we add an **inline auto-translation layer** with a toggle.

#### Do We Even Need This?

> **Open question:** In theory, you can just type Japanese into Vibe and Mistral's models should reply in Japanese. Voxtral also supports Japanese transcription (one of 13 languages). So you could:
> 1. Speak Japanese → Voxtral transcribes Japanese → Vibe receives Japanese prompt → Mistral replies in Japanese
> 2. Type Japanese directly → same flow
>
> **However**, there are cases where translation is still valuable:
> - Agent **tool output** (bash stdout, file contents, error messages) is always English
> - Agent **reasoning** tends to default to English regardless of user language
> - **Code comments** and **commit messages** generated by the agent will be English
> - Existing session history may already be in English
> - Mixed EN/JA conversations where the model switches languages unpredictably
>
> **Recommendation:** Support both approaches. Let users talk in Japanese natively, AND provide auto-translation as a fallback for English-only content. The translation toggle makes this opt-in per message.

#### UX Design

Each message bubble gets a small translation toggle:

```
┌─────────────────────────────────────────┐
│  🤖 Assistant                           │
│  I'll create a REST endpoint for user   │
│  authentication using JWT tokens...     │
│                                         │
│  [🌐 自動翻訳]                           │  ← click to toggle
└─────────────────────────────────────────┘

        ↓ (after clicking toggle)

┌─────────────────────────────────────────┐
│  🤖 Assistant                  🌐 自動翻訳│  ← tag shows translation active
│  JWTトークンを使用したユーザー認証用の       │
│  RESTエンドポイントを作成します...          │
│                                         │
│  [EN Original]                          │  ← click to switch back
└─────────────────────────────────────────┘
```

#### Global Toggle

A settings toggle for "Auto-translate all EN→JA" so you don't have to click per-message:

```
┌──────────────────────────────────────┐
│  ⚙️ Settings                         │
│                                      │
│  🔥 Intensity                        │
│  😴 ──────●────────────────── 🔥     │
│           Vibing (default)           │
│                                      │
│  🌐 Auto-translate EN→JA   [🔘 ON]  │
│  🎤 Voice language          [JA 🇯🇵] │
│  🔔 Notifications           [🔘 ON]  │
│  💤 Snooze        [30m] [1h] [🌙]   │
└──────────────────────────────────────┘
```

When enabled, all new `AssistantEvent` and `ToolResultEvent` messages are automatically translated, with the `🌐 自動翻訳` tag visible. The original is always one click away.

#### Implementation

**Server-side translation endpoint:**
```python
from mistralai import Mistral

@app.post("/api/translate")
async def translate(req: TranslateRequest):
    """Translate text between EN and JA using Mistral chat API."""
    
    # Hackathon demo default: use Mistral Large 3 (translation + vision in one model).
    response = mistral_client.chat.complete(
        model="mistral-large-latest",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a translator. Translate the following text. "
                    "Output ONLY the translation, no explanations. "
                    "Preserve code blocks, file paths, and technical terms untranslated. "
                    "Preserve markdown formatting."
                ),
            },
            {
                "role": "user",
                "content": f"Translate from {req.source_lang} to {req.target_lang}:\n\n{req.text}",
            },
        ],
        temperature=0.1,
    )
    
    return {
        "translated_text": response.choices[0].message.content,
        "source_lang": req.source_lang,
        "target_lang": req.target_lang,
    }
```

**Client-side caching + lazy translation:**
```javascript
class TranslationManager {
    constructor() {
        this.cache = new Map();  // messageId → translated text
        this.autoTranslate = false;
    }
    
    async getTranslation(messageId, text, sourceLang = 'en', targetLang = 'ja') {
        const key = `${messageId}:${sourceLang}→${targetLang}`;
        if (this.cache.has(key)) return this.cache.get(key);
        
        const resp = await fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, source_lang: sourceLang, target_lang: targetLang }),
        });
        const { translated_text } = await resp.json();
        this.cache.set(key, translated_text);
        return translated_text;
    }
    
    detectLanguage(text) {
        // Simple heuristic: if >50% characters are CJK, it's likely Japanese
        const cjk = text.match(/[\u3000-\u9fff\uff00-\uffef]/g);
        return (cjk && cjk.length / text.length > 0.3) ? 'ja' : 'en';
    }
}
```

**Auto-translate on event broadcast (server-side, optional):**
```python
async def _broadcast_with_translation(self, event: dict):
    """Broadcast event, auto-translating if enabled."""
    await self._broadcast(event)
    
    # If auto-translate is enabled and content is English, also send JA version
    if self.auto_translate_ja and event.get("content"):
        detected = self._detect_lang(event["content"])
        if detected == "en":
            translated = await self._translate(event["content"], "en", "ja")
            await self._broadcast({
                **event,
                "type": event["type"] + "_translated",
                "content": translated,
                "translation_meta": {
                    "source_lang": "en",
                    "target_lang": "ja",
                    "auto": True,
                },
            })
```

#### Voice Input in Japanese

Voxtral supports Japanese transcription natively. The voice pipeline becomes:

```
📱 Speak Japanese → Voxtral (language="ja") → Japanese text → Vibe
📱 Speak English  → Voxtral (language="en") → English text → (auto-translate JA overlay) → Vibe
```

Update the Voxtral transcription call to support language selection:

```python
@app.post("/api/voice/transcribe")
async def voice_transcribe(audio: UploadFile, language: str = "ja"):
    """Transcribe audio. Default to Japanese for Tokyo Hackathon."""
    content = await audio.read()
    response = mistral_client.audio.transcriptions.complete(
        model="voxtral-mini-latest",
        file={"content": content, "file_name": audio.filename or "voice.webm"},
        language=language,  # "ja" for Japanese, "en" for English
    )
    return {"text": response.text, "language": language}
```

#### Translation Cost Estimate

Using `mistral-large-latest` for translation in the demo:
- Average assistant message: ~200 tokens → ~50 output tokens translated
- Lazy + cached, so it only triggers when user clicks toggle or enables auto-translate

For hackathon execution, translation stays on `mistral-large-latest` to keep quality and model-role clarity consistent.

---

## Vibe Integration Points

### Where to Hook In

Vibe's architecture provides clean integration points:

```python
# 1. Event Observer — capture all events for broadcasting
agent_loop = AgentLoop(
    config,
    message_observer=bridge.on_message_change,  # Called on new/updated messages
)

# 2. Approval Callback — intercept tool approval requests
agent_loop.set_approval_callback(bridge._approval_callback)

# 3. User Input Callback — intercept ask_user_question
agent_loop.set_user_input_callback(bridge._user_input_callback)

# 4. Event Handler — tap into the event stream
# In vibe/cli/textual_ui/handlers/event_handler.py
# Each BaseEvent flows through handle_event() — add a bridge hook here
```

### Vibe's Event Types (What to Broadcast)

```python
BaseEvent
├── UserMessageEvent(content, message_id)           → User prompt event
├── AssistantEvent(content, stopped_by_middleware)   → Show assistant reply
├── ReasoningEvent(content, message_id)              → Show reasoning block
├── ToolCallEvent(tool_name, tool_class, args)       → Show tool invocation
├── ToolResultEvent(tool_name, result/error, skipped)→ Show tool result
├── ToolStreamEvent(tool_name, message)              → Update tool progress
├── CompactStartEvent(context_tokens, threshold)     → Show compaction notice
└── CompactEndEvent(old_tokens, new_tokens)          → Show compaction result
```

#### Live Attach Known Limitations (Phase 3.1)

- `VibeCheckApp._handle_agent_loop_turn()` delegates to `bridge.inject_message()` for queue ownership. This intentionally drops Vibe's loading widget lifecycle, Ctrl+C turn interrupt behavior, and history refresh in the terminal path.

### Vibe's Waiting States (What Triggers Notifications)

| State | Detection | Source |
|-------|-----------|--------|
| **Waiting for tool approval** | `_pending_approval` Future is set, not done | `AgentLoop._should_execute_tool()` → `_ask_approval()` |
| **Waiting for user input** | `_pending_input` Future is set, not done | `ask_user_question` tool → `user_input_callback()` |
| **Agent running** | `_agent_running` flag is True | `AgentLoop.act()` in progress |
| **Idle** | No pending futures, agent not running | Between user messages |

---

## Networking

### Primary: EC2 Direct (Production / Demo)

Vibe + vibecheck run together on EC2. Caddy handles TLS termination:

```
Phone → HTTPS → EC2 (Caddy :443 → vibecheck :7870 → Vibe in-process)
```

No tunnels needed. Caddy auto-provisions Let's Encrypt certificates.

**HTTPS is required** for Web Push API, `getUserMedia()` (mic), and Service Worker registration.

### Local Dev: Tailscale (Optional)

If you're running Vibe on your local machine and want phone access without deploying to EC2:

1. Install [Tailscale](https://tailscale.com/) on dev machine and phone
2. Enable HTTPS certificates: `tailscale cert your-machine.tailnet-name.ts.net`
3. Configure Caddy to proxy through Tailscale IP, or access directly via `https://your-machine.tailnet-name.ts.net:7870`

This gives you a stable HTTPS URL on your tailnet without exposing anything to the public internet.

---

## Voxtral API Reference

### Batch Transcription (voxtral-mini-latest → voxtral-mini-2602)

```python
from mistralai import Mistral

client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

# From file
with open("audio.mp3", "rb") as f:
    response = client.audio.transcriptions.complete(
        model="voxtral-mini-latest",
        file={"content": f, "file_name": "audio.mp3"},
        language="en",                                    # optional, boosts accuracy
        # diarize=True,                                   # speaker labels
        # timestamp_granularities=["segment", "word"],    # timestamps
        # context_bias="technical,terms,here",            # up to 100 words
    )
print(response.text)

# From URL
response = client.audio.transcriptions.complete(
    model="voxtral-mini-latest",
    file_url="https://example.com/audio.mp3",
)
```

**Pricing:** $0.003/min | **Formats:** mp3, wav, m4a, flac, ogg, webm | **Max:** 3 hours

### Realtime Streaming (voxtral-mini-transcribe-realtime-2602)

```python
from mistralai import Mistral
from mistralai.extra.realtime import UnknownRealtimeEvent
from mistralai.models import (
    AudioFormat, 
    TranscriptionStreamTextDelta,
    TranscriptionStreamDone,
    RealtimeTranscriptionSessionCreated,
    RealtimeTranscriptionError,
)

client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=16000)

async def audio_source():
    """Yield PCM audio chunks from any source."""
    # ... yield bytes ...

async for event in client.audio.realtime.transcribe_stream(
    audio_stream=audio_source(),
    model="voxtral-mini-transcribe-realtime-2602",
    audio_format=audio_format,
):
    if isinstance(event, TranscriptionStreamTextDelta):
        print(event.text, end="", flush=True)
    elif isinstance(event, TranscriptionStreamDone):
        print("\n[Done]")
```

**Pricing:** $0.006/min | **Latency:** configurable 80ms-2.4s (recommend 480ms) | **Format:** PCM 16-bit mono, 16kHz
**Requires:** `pip install mistralai[realtime]`

### Model Summary

| Model | Endpoint | Price | Use Case |
|-------|----------|-------|----------|
| `voxtral-mini-latest` | `POST /v1/audio/transcriptions` | $0.003/min | Batch: record → transcribe |
| `voxtral-mini-transcribe-realtime-2602` | WebSocket via SDK | $0.006/min | Live: stream audio → stream text |
| `voxtral-mini-4b-realtime-2602` | Self-hosted (Apache 2.0) | Free (GPU) | On-device, 4B params, vLLM |

---

## Implementation Plan

> **Source of truth:** [docs/PLAN.md](docs/PLAN.md) (layer-based architecture) and [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) (WU-01 through WU-35, phased execution with parallelism).
>
> The legacy phase list that was here has been replaced. See those docs for the current work breakdown.

### Stretch Goals

See [PLAN.md L7–L9](docs/PLAN.md) and [IMPLEMENTATION.md Phase 7](docs/IMPLEMENTATION.md) for stretch work (Voxtral Realtime streaming, multi-agent dashboard, smart autonomy, etc.).

#### Optional Fine-Tune Track: SOTA Japanese ASR

Separate from the core vibecheck submission. If time allows:

- Fine-tune Voxtral-mini-4B on Japanese ASR datasets (ReazonSpeech, CommonVoice JA, JSUT)
- Benchmark against Whisper large-v3, Qwen2-Audio, base Voxtral
- Self-host on hackathon GPU for zero-latency on-device JA transcription
- Publish to HuggingFace: `shisa-ai/shisa-asr-v1-voxtral-mini-4b-rt`

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| In-process vs sidecar? | **In-process.** Hook into `AgentLoop` directly. See [PLAN.md](./PLAN.md). |
| Tunnel approach? | **None needed.** Vibe runs on EC2, Caddy handles HTTPS. Tailscale for local dev. |
| Voxtral self-hosted vs API? | **API** for hackathon. Self-hosted is stretch if GPU available. |
| Multiple simultaneous clients? | Bridge broadcasts to all WS clients; first-responder wins for approvals. |
| Audio format from mobile? | MediaRecorder produces `audio/webm;codecs=opus`; Voxtral batch API supports it. |
| JA-native vs translation overlay? | Test at hackathon. Translation layer (Mistral Large) is the safe path. |

---

*See also: [docs/REMOTING-UI.md](docs/REMOTING-UI.md) for the general mobile-to-TUI bridge landscape.*
