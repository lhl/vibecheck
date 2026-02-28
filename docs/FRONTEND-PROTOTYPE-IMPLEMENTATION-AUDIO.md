# Frontend Prototype Implementation Punchlist (Audio)

## Purpose

Build a minimal, working end-to-end voice loop prototype for mobile browsers:

- Record audio in the browser
- Send audio to Voxtral STT (Mistral), display transcript
- Send transcript to ElevenLabs TTS, play audio back in a selected voice
- Keep all secrets server-side via a tiny proxy service

This is a fast-iteration baseline, not a production UI.

## Scope

In scope:
- Single-page mobile-first UI with record/stop, voice dropdown, transcript area, and status
- One small backend proxy with `/api/stt`, `/api/tts`, `/api/voices`
- Simple error handling and retry paths
- Manual mobile verification (iOS Safari and Android Chrome)

Out of scope:
- Auth, persistence, session history
- Complex UI/animations
- Push notifications, background processing, or offline support

## Assumptions

- Voxtral is the STT provider and ElevenLabs is the TTS provider for this prototype.
- The backend runs in `frontend-prototype/server` and is the only place that knows `MISTRAL_API_KEY` and `ELEVENLABS_API_KEY`.
- The frontend runs in `frontend-prototype/frontend` and stays intentionally simple.
- Confirm current Voxtral STT and ElevenLabs TTS API requirements at implementation time (endpoints, payloads, audio codecs).

## Milestones

**Milestone 0: Scaffold and Dev Workflow**
- Create `frontend-prototype/frontend` with Svelte 5 + Vite, single-page app
- Create `frontend-prototype/server` with FastAPI + uv config
- Add minimal README with local dev commands and env var requirements
- Ensure frontend can call backend in local dev (CORS or proxy config)

Exit criteria:
- `npm run dev` serves the frontend
- `uv run python -m server.app` (or equivalent) starts the backend
- Frontend and backend can communicate locally

**Milestone 1: Backend Proxy Skeleton**
- Implement `GET /api/voices` returning a small, static list of voices
- Implement `POST /api/stt` to accept multipart audio upload and return transcript JSON (Voxtral)
- Implement `POST /api/tts` to accept text + voice_id and return `audio/mpeg`
- Add request validation, size limits, and clear error mapping
- Add backend tests with mocked STT/TTS upstream helper calls

Exit criteria:
- `GET /api/voices` returns a valid list for the dropdown
- `POST /api/stt` returns `{"text": "...", "language": "en"}` for valid audio
- `POST /api/tts` returns valid `audio/mpeg` (streaming or full binary)
- `uv run pytest` for server tests passes

**Milestone 2: Frontend UI Skeleton**
- Mobile-first layout with record/stop button, voice selector, transcript area, status indicator
- State machine for `idle`, `recording`, `transcribing`, `speaking`, `error`
- Basic styling for touch targets and safe-area spacing

Exit criteria:
- UI renders on mobile with readable controls and correct touch target sizing
- All five states (`idle`, `recording`, `transcribing`, `speaking`, `error`) are visually distinguishable without real API calls (e.g. hardcoded state prop or dev toggle)

**Milestone 3: STT Integration**
- Implement MediaRecorder flow with mic permission handling
- Validate minimal audio duration before upload
- Send audio blob to `/api/stt` and render transcript on success
- Handle errors with a clear retry path

Exit criteria:
- Record and stop produces a transcript in the UI
- Mic denial and short recordings show actionable errors

**Milestone 4: TTS Integration + Playback**
- Send transcript + selected voice to `/api/tts`
- Play returned `audio/mpeg` using `Audio` or `AudioContext`
- Show speaking state during playback

Exit criteria:
- Transcript is spoken back in the selected voice
- Playback errors are surfaced and retryable

**Milestone 5: Hardening + Mobile QA**
- Retry buttons for STT and TTS
- Confirm behavior on iOS Safari and Android Chrome
- Verify no secrets appear in frontend source or network calls
- Add small UX touches for stability (disable buttons during requests, clear states)

Exit criteria:
- End-to-end flow works reliably on phones
- Acceptance criteria in `docs/FRONTEND-PROTOTYPE-PLAN-AUDIO.md` are satisfied

## Verification Checklist

- Backend tests: `cd frontend-prototype/server && uv run pytest tests -v`
- Frontend build: `cd frontend-prototype/frontend && npm run build`
- Manual mobile test on iOS Safari and Android Chrome

## Worklog

- Update `docs/FRONTEND-WORKLOG-AUDIO.md` and `WORKLOG.md` with major actions and decisions for this prototype.
