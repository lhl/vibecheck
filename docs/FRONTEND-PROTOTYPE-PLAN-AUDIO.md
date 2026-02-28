# Frontend Prototype Plan (Audio)

## Goal

Build a very simple web prototype that does one round-trip flow:

1. Record voice from the browser
2. Send audio to Voxtral (Mistral) Speech-to-Text
3. Show transcription text on screen
4. Send transcription text to ElevenLabs Text-to-Speech
5. Play synthesized audio back in a selected ElevenLabs voice

This is a base scaffold, not final product UI.

Mobile is a first-class target: this prototype is primarily for phone usage and should be designed, tested, and validated on mobile form factors first.

## Scope (v0)

- Single page app with:
  - `Record` / `Stop` button
  - Voice selector (dropdown)
  - Transcript output area
  - `Play back` status indicator
- One backend proxy service to keep `MISTRAL_API_KEY` and `ELEVENLABS_API_KEY` server-side
- No persistence, auth, session history, or advanced UX yet
- Mobile-first interaction and layout (touch targets, responsive spacing, safe-area awareness)

## High-Level Architecture

```text
Browser (MediaRecorder)
  -> POST /api/stt (audio blob)
      -> Voxtral STT API (Mistral)
      <- transcript text
  -> POST /api/tts (text + voice_id)
      -> ElevenLabs TTS API
      <- audio/mpeg stream
Browser plays returned audio
```

## Why Proxy Through Backend

- Prevent exposing `MISTRAL_API_KEY` and `ELEVENLABS_API_KEY` in browser code
- Centralize error handling and request shaping
- Keep frontend simple and replaceable later

## API Contract (Prototype)

### `POST /api/stt`

Proxies to Voxtral (`voxtral-mini-latest`) via backend HTTP call to the Mistral STT API. Uses `MISTRAL_API_KEY`.

- Request: multipart form-data
  - `audio`: recorded file (webm/opus from MediaRecorder)
  - `language`: optional (default `en`)
- Response:

```json
{
  "text": "transcribed text",
  "language": "en"
}
```

### `POST /api/tts`

Proxies to ElevenLabs TTS API. Uses `ELEVENLABS_API_KEY`.

- Request JSON:

```json
{
  "text": "transcribed text",
  "voice_id": "elevenlabs_voice_id"
}
```

- Response: `audio/mpeg` (stream or full binary)

### `GET /api/voices`

- Returns a small list of available ElevenLabs voices for dropdown selection
- Can be static cached list in v0

## Frontend Flow

1. User clicks `Record`
2. Browser starts `MediaRecorder` with `audio/webm;codecs=opus` if supported
3. User clicks `Stop`
4. Frontend uploads blob to `/api/stt`
5. UI renders returned transcript
6. Frontend immediately posts transcript to `/api/tts` with selected `voice_id`
7. Browser receives audio, creates object URL or decodes buffer, and plays
8. UI shows success/error state

Note: controls and interactions should prioritize touch input (tap-and-hold or tap-to-record behavior) with desktop support as secondary.

## Error Handling (v0)

- Mic permission denied -> clear message and retry button
- Empty/very short recording -> do not call STT; show validation message
- STT failure -> show error and keep recording controls enabled
- TTS failure -> transcript remains visible; user can retry TTS only

## Minimal UI State

- `idle`
- `recording`
- `transcribing`
- `speaking`
- `error`

## Suggested File Layout

```text
frontend-prototype/
  PLAN.md
  frontend/            # Svelte 5 + Vite app
    index.html
    src/
      main.js          # Vite entry point (mounts App)
      App.svelte       # root component (state machine + layout)
      lib/
        Recorder.svelte    # MediaRecorder + record/stop logic
        VoiceSelect.svelte # voice dropdown
        Transcript.svelte  # transcript display
  server/              # tiny FastAPI proxy service (uv)
    app.py             # /api/stt, /api/tts, /api/voices
    pyproject.toml
```

## Implementation Phases

### Phase 1: Skeleton
- Create page with record button, voice dropdown, transcript area
- Add basic state rendering (`idle`, `recording`, `transcribing`, `speaking`, `error`)

### Phase 2: STT Path
- Implement recording start/stop
- Send blob to `/api/stt`
- Display returned transcript

### Phase 3: TTS Path
- Send transcript to `/api/tts` with selected voice
- Play returned audio in browser

### Phase 4: Hardening
- Add user-facing error messages
- Add retry buttons for STT and TTS
- Confirm mobile browser behavior (iOS/Android) as primary acceptance path

## Acceptance Criteria (Prototype Complete)

- User can record voice and stop recording
- Transcript appears from Voxtral STT
- Same text is spoken back using selected ElevenLabs voice
- No API keys (`MISTRAL_API_KEY`, `ELEVENLABS_API_KEY`) appear in frontend source or network calls from browser
- Prototype is usable on modern phone browsers with mobile-first layout and touch-friendly controls
