# vibecheck — Frontend Worklog (Audio)

## 2026-02-28

### Frontend prototype ngrok host allowlist (mobile testing)
- Updated `frontend-prototype/frontend/vite.config.js` to allow Vite host `hilario-femoral-verda.ngrok-free.dev` via `server.allowedHosts`.
- Purpose: enable phone access through ngrok forwarding to local dev server on `localhost:5178`.

### Phase 0 punchlist reset (frontend portions)
- Updated WU-02 mobile acceptance note to target 360px–428px phone widths and retained explicit frontend build gate

### Phase 0 implementation (frontend portions)
- Implemented frontend scaffold (`WU-02`) via `npm create vite@latest vibecheck/frontend -- --template svelte`:
  - Configured `vite.config.js` proxy (`/api`, `/ws`) to `localhost:7870` and build output to `../static`.
  - Replaced default app with mobile shell layout in `src/App.svelte` (safe-area insets, 44px targets, dark theme vars).
  - Added PWA files (`public/manifest.json`, `public/sw.js`) and registered SW in `src/main.js`.
  - Generated placeholder icons: `public/icons/vibe-192.png` and `public/icons/vibe-512.png`.
- Updated ignore policy:
  - Added `vibecheck/frontend/node_modules/` and `vibecheck/static/` to root `.gitignore`.
- Verification results:
  - Frontend: `cd vibecheck/frontend && npm install && npm run build` succeeded; output in `vibecheck/static/`.
  - Frontend dev probe: `npm run dev` served on `:5173` and responded to `curl`.

### Frontend prototype planning
- Added `docs/FRONTEND-PROTOTYPE-IMPLEMENTATION-AUDIO.md` with milestone-based punchlist for the Voxtral STT + ElevenLabs TTS voice loop prototype

### Frontend prototype reviewer corrections
- Updated `frontend-prototype/server/server/app.py` to stream `/api/tts` responses back to clients instead of buffering full audio in memory.
- Hardened STT upload handling with chunked reads and early 413 rejection when payload size exceeds `STT_MAX_UPLOAD_BYTES`.
- Added explicit dev-intent comment for wildcard CORS in prototype backend.
- Removed unused `mistralai` dependency from `frontend-prototype/server/pyproject.toml` and aligned lockfile.
- Added `frontend-prototype/server/pytest.ini` and removed test-time `sys.path` mutation.
- Expanded backend tests for voice entry shape, STT 413 branch, STT auth-error mapping, and empty TTS upstream audio branch.
- Aligned prototype docs to implemented backend contract and corrected backend verification command to run from `frontend-prototype/server`.

### Frontend prototype milestone 2 (UI skeleton)
- Added frontend component test setup for Svelte 5 (`vitest`, `@testing-library/svelte`, `@testing-library/jest-dom`, `jsdom`) with Vite `svelteTesting()` integration.
- Wrote red-first component tests in `frontend-prototype/frontend/src/App.test.js` for Milestone 2 acceptance: explicit state-preview controls and error-state preview behavior.
- Implemented a `State Preview` panel in `frontend-prototype/frontend/src/App.svelte` so `idle`, `recording`, `transcribing`, `speaking`, and `error` can be forced without API calls.
- Added state-specific visual styling in `frontend-prototype/frontend/src/app.css` for clearer differentiation across all five UI states while preserving mobile-safe spacing and touch target sizing.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 2 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.

### Frontend prototype review fixes (milestone 2 hardening)
- Fixed preview-state safety regression in `frontend-prototype/frontend/src/App.svelte`: changing preview state now stops active `MediaRecorder` sessions and suppresses processing for intentionally dropped preview cancellations.
- Added status accessibility announcement (`role="status"`, `aria-live="polite"`) so state/status changes are announced to assistive tech.
- Expanded frontend tests in `frontend-prototype/frontend/src/App.test.js`:
  - Assert per-state preview transitions update state pill + surface classes for all five states.
  - Assert preview transition during active recording calls recorder `stop()` and stops audio tracks (prevents orphan mic capture).
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 4 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
- Mobile verification attempt:
  - Tried Playwright mobile screenshot smoke check (`iPhone 12`, `Pixel 7`) against local Vite dev server.
  - Blocked in current environment due missing host browser libs required by Playwright runtime (`libevent-2.1-7t64`, `libgstreamer-plugins-bad1.0-0`, `libflite1`, `libavif16`).
  - Manual on-device iOS/Android check remains pending.

### Frontend prototype Playwright setup (CLI + project integration)
- Added Playwright as a project dev dependency in `frontend-prototype/frontend` (`@playwright/test`) to avoid transient `npx` installs.
- Added `frontend-prototype/frontend/playwright.config.js` with:
  - Mobile projects (`Pixel 7`, `iPhone 12`)
  - Local dev `webServer` startup on `127.0.0.1:4178`
  - HTML report output enabled
- Added mobile smoke test `frontend-prototype/frontend/e2e/mobile-smoke.spec.js`:
  - Verifies core UI render on mobile projects
  - Stubs `/api/voices` so test is backend-independent
  - Verifies all five preview states update the visible state pill
- Added npm scripts:
  - `test:e2e`
  - `test:e2e:headed`
- Updated `frontend-prototype/.gitignore` for Playwright artifacts:
  - `frontend/playwright-report/`
  - `frontend/test-results/`
- Updated Vitest include pattern in `frontend-prototype/frontend/vite.config.js` so unit test runs exclude Playwright e2e specs.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 4 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 2 passed (`Mobile Chrome`, `Mobile Safari`).

### Frontend prototype follow-up review fixes (race + test isolation)
- Hardened recording lifecycle in `frontend-prototype/frontend/src/App.svelte` to prevent stale `onstop` callbacks from prior recordings mutating active recorder state:
  - Added per-recording session IDs.
  - Switched preview-cancel tracking from single boolean to session ID set.
  - Scoped `onstop`/`onerror` handlers to captured recorder/stream instances.
  - Updated `stopTracks` to support targeted stream shutdown.
- Removed unreachable `if (!currentAudio)` branch in `playAudioBlob` by using a local `audio` instance binding.
- Simplified state pill rendering to display `uiState` directly (removed redundant state-label mapping).
- Improved unit test isolation in `frontend-prototype/frontend/src/App.test.js` by restoring `navigator.mediaDevices` descriptors in tests that override them.
- Added regression test for rapid re-record scenario:
  - Start recording A -> preview-cancel A -> start recording B -> flush delayed onstop for A.
  - Assert stream B is not stopped by A’s stale callback.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 5 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 2 passed.

### Frontend prototype reviewer sync fixes (style + stale onerror guard)
- Updated event handler syntax in `frontend-prototype/frontend/src/App.svelte` from legacy `on:click` to Svelte 5 style `onclick` for all button handlers.
- Replaced `void` fire-and-forget async calls with explicit `.catch(...)` handling:
  - `loadVoices().catch(...)` in `onMount`
  - `processRecording(...).catch(...)` in recorder `onstop`
- Added stale-session isolation in recorder `onerror`:
  - Old recorder errors now return early without forcing global `uiState=error` when the recorder/session is no longer active.
- Added regression coverage in `frontend-prototype/frontend/src/App.test.js`:
  - New test confirms stale errors from prior recorder sessions do not disrupt an active newer recording.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 6 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 2 passed.

### Frontend prototype final race fix (stale onerror before delayed onstop)
- Added regression test in `frontend-prototype/frontend/src/App.test.js` for ordering:
  - preview-cancel recording A
  - start recording B
  - stale `onerror` from A fires before delayed `onstop` from A
  - assert A is still treated as dropped and does not disrupt recording B
- Fixed stale callback handling in `frontend-prototype/frontend/src/App.svelte`:
  - stale `recorder.onerror` no longer clears dropped-session marker, so delayed `onstop` still short-circuits as canceled.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 7 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 2 passed.

### Frontend prototype milestone 3 kickoff (STT integration verification)
- Read `docs/PLAN.md`, `docs/IMPLEMENTATION.md`, `docs/FRONTEND-PROTOTYPE-PLAN-AUDIO.md`, and `docs/FRONTEND-PROTOTYPE-IMPLEMENTATION-AUDIO.md` to align milestone scope before changes.
- Added Milestone 3-focused frontend tests in `frontend-prototype/frontend/src/App.test.js`:
  - record -> stop -> `/api/stt` upload -> transcript render
  - microphone permission denied path with actionable UI error
  - short recording validation path (no STT call)
  - STT failure retry path (`Retry STT` re-attempts transcription)
- Result: all new tests passed with current `App.svelte` implementation, confirming Milestone 3 behavior was already present and stable.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 11 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.

### Frontend prototype reviewer-feedback fixes (milestone 3)
- Addressed reviewer gap in M3 success-path testing by mocking `/api/tts` and playback dependencies in frontend unit tests:
  - Added deterministic playback mocks (`Audio`, `URL.createObjectURL`, `URL.revokeObjectURL`) so STT + TTS can run to completion in jsdom.
  - Updated M3 success test to assert clean completion (`state=idle`, status `Playback complete`, no error panel).
- Added frontend test coverage requested by reviewers:
  - STT FormData shape check (`audio` + `language`).
  - Unsupported browser path (`MediaRecorder` unavailable).
  - Empty STT response text mapping (`Transcription came back empty`).
  - Explicit byte-size short-audio guard coverage.
- Replaced fragile microtask flush (`await Promise.resolve()`) with `waitFor(...)` in delayed-stop race test.
- Aligned frontend short-audio threshold with backend default:
  - Updated `MIN_AUDIO_BYTES` in `frontend-prototype/frontend/src/App.svelte` from `1024` to `2048`.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 15 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 2 passed.

### Frontend prototype milestone 4 kickoff (TTS integration + playback)
- Read `docs/PLAN.md`, `docs/IMPLEMENTATION.md`, `docs/FRONTEND-PROTOTYPE-PLAN-AUDIO.md`, and `docs/FRONTEND-PROTOTYPE-IMPLEMENTATION-AUDIO.md` to align Milestone 4 scope and exit criteria.
- Added Milestone 4 frontend tests first in `frontend-prototype/frontend/src/App.test.js`:
  - selected voice ID is sent in `/api/tts` payload
  - speaking state includes explicit playback status messaging during active audio playback
  - playback failures surface actionable errors and recover through `Retry TTS`
- Confirmed red-first failure for the new speaking-status expectation (`Expected: "Speaking...", Received: "Generating speech..."`).
- Implemented Milestone 4 UI behavior in `frontend-prototype/frontend/src/App.svelte` by switching status to `Speaking...` when audio playback starts.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 17 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/server && uv run pytest tests -v` -> 17 passed.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 2 passed (`Mobile Chrome`, `Mobile Safari`).

### Frontend prototype milestone 4 reviewer-feedback hardening
- Addressed M4 frontend test gaps and duplication in `frontend-prototype/frontend/src/App.test.js`:
  - Switched milestone 4 tests to use shared `installPlaybackMocks()` setup/teardown via `beforeEach`/`afterEach` (removed duplicated manual `URL.createObjectURL`, `URL.revokeObjectURL`, and restore blocks).
  - Added frontend test for `/api/tts` HTTP error mapping with detail message assertion and `Retry TTS` visibility.
  - Added frontend test for empty-audio response path (`audioBlob.size === 0`) asserting `TTS returned empty audio`.
  - Added regression test ensuring `Retry TTS` is hidden after a later STT failure so stale transcript text cannot be replayed.
- Hardened milestone 4 UI behavior in `frontend-prototype/frontend/src/App.svelte`:
  - `Retry TTS` now renders only when `lastFailedStage === 'tts'`.
  - `retryTts()` now guards by failure stage and retries current transcript only.
  - Removed redundant `lastTtsText` state and dead fallback path.
  - Removed duplicate normal-path transcribing status assignment by making it conditional (still set for retry STT path).
  - Removed ineffective `audio.preload` assignment after `new Audio(src)`.
- Added browser-level mobile e2e coverage in `frontend-prototype/frontend/e2e/mobile-smoke.spec.js`:
  - deterministic in-page mocks for `MediaRecorder`, `Audio`, `mediaDevices`, and `Date.now`
  - success path coverage: `/api/stt -> /api/tts -> playback complete` with selected voice payload assertion
  - failure/recovery coverage: `/api/tts` HTTP 502 detail surfaced, then `Retry TTS` succeeds
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 20 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 6 passed (`Mobile Chrome`, `Mobile Safari`).
  - `cd frontend-prototype/server && uv run pytest tests -v` -> 17 passed.

### Frontend prototype backend hotfix (TTS stream consumed twice)
- Investigated production-like runtime error during `/api/tts` playback: `httpx.StreamConsumed` raised from `server/app.py` while streaming ElevenLabs response.
- Root cause: endpoint consumed `upstream_response.aiter_bytes()` once to probe first chunk, then called `aiter_bytes()` again in `stream_body()`. `httpx` streams are single-pass.
- Added red-first regression test in `frontend-prototype/server/tests/test_api.py`:
  - `test_tts_reads_upstream_stream_in_single_pass` uses a single-pass fake upstream response that raises `httpx.StreamConsumed` on second iterator construction.
- Fixed `frontend-prototype/server/server/app.py`:
  - create one shared iterator (`upstream_stream = upstream_response.aiter_bytes()`)
  - read first non-empty chunk from that iterator
  - continue streaming remaining chunks from the same iterator
  - broadened stream-read exception handling to include `httpx.StreamError` in both preflight read and mid-stream path
- Updated mid-stream failure test to model single-iterator semantics and keep expected abort behavior.
- Verification:
  - `cd frontend-prototype/server && uv run pytest tests/test_api.py::test_tts_reads_upstream_stream_in_single_pass -v` -> passed (after initial red failure).
  - `cd frontend-prototype/server && uv run pytest tests -v` -> 18 passed.
  - Startup smoke: `uv run uvicorn server.app:app --host 127.0.0.1 --port 8780` + `curl http://127.0.0.1:8780/health` -> `{"status":"ok"}`.

### Frontend prototype milestone 5 kickoff (hardening + mobile QA)
- Read `docs/PLAN.md`, `docs/IMPLEMENTATION.md`, `docs/FRONTEND-PROTOTYPE-PLAN-AUDIO.md`, and `docs/FRONTEND-PROTOTYPE-IMPLEMENTATION-AUDIO.md` to align Milestone 5 scope and exit criteria.
- Added Milestone 5 frontend tests first in `frontend-prototype/frontend/src/App.test.js`:
  - clears stale transcript state when starting a new recording after a completed prior run
  - disables non-essential controls (preview buttons) while transcription requests are in flight
  - verifies browser request shape uses only local `/api/*` proxy routes with no provider auth headers
- Confirmed red-first failures for new hardening requirements:
  - stale transcript not cleared on new recording start
  - preview controls remained enabled during active transcription
- Implemented Milestone 5 hardening in `frontend-prototype/frontend/src/App.svelte`:
  - added `requestInFlight` state to lock non-essential controls only during real network work (without breaking preview-mode state demos)
  - cleared stale transcript and stale retry blob state on new recording start
  - added retry guards/disabled states to prevent concurrent retry actions during active work
- Expanded mobile e2e QA in `frontend-prototype/frontend/e2e/mobile-smoke.spec.js`:
  - STT failure + `Retry STT` recovery flow
  - control-lock assertions during in-flight transcription
  - proxy-only network behavior assertion (no direct `api.mistral.ai` or `api.elevenlabs.io` calls; no browser provider auth headers)
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 23 passed.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 12 passed (`Mobile Chrome`, `Mobile Safari`).
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/server && uv run pytest tests -v` -> 18 passed.
  - `cd frontend-prototype/frontend && rg -n "MISTRAL_API_KEY|ELEVENLABS_API_KEY|api\\.mistral\\.ai|api\\.elevenlabs\\.io|xi-api-key|Authorization" src dist --glob '!src/**/*.test.js'` -> no matches.

### Frontend prototype milestone 5 reviewer follow-up fixes
- Addressed high-severity race in `frontend-prototype/frontend/src/App.svelte`:
  - added `micPermissionInFlight` lock to prevent concurrent `startRecording()` re-entry while `getUserMedia()` is pending.
  - updated `Record` button guard/disabled conditions to include explicit in-flight locks (`requestInFlight`, `micPermissionInFlight`) rather than relying only on `uiState`.
- Added red-first unit coverage in `frontend-prototype/frontend/src/App.test.js`:
  - `blocks a second record start while microphone permission request is still pending` (failed before fix, passed after).
  - `keeps controls disabled while retry tts request is in flight` to cover missing reviewer-noted path.
- Expanded e2e coverage in `frontend-prototype/frontend/e2e/mobile-smoke.spec.js`:
  - `/api/voices` failure fallback to built-in voice list (`George`, `Bella`, `Adam`).
- Added repeatable frontend secret-scan gate:
  - new script `frontend-prototype/frontend/scripts/check-no-secrets.mjs`.
  - new npm command `npm run test:secrets`.
- Added manual phone QA execution artifact:
  - `frontend-prototype/MOBILE-QA-CHECKLIST.md` for physical iOS Safari + Android Chrome validation.
- Updated `frontend-prototype/README.md` to include `test`, `test:e2e`, and `test:secrets` commands and manual checklist reference.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 25 passed.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 14 passed (`Mobile Chrome`, `Mobile Safari`).
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/frontend && npm run test:secrets` -> passed.
  - `cd frontend-prototype/server && uv run pytest tests -v` -> 18 passed.
- Note:
  - Physical-device manual QA is still pending execution by a teammate with access to iOS Safari and Android Chrome hardware.

### Frontend prototype phone recording diagnostics fix (insecure origin clarity)
- Trigger: real-phone report that tapping `Record` showed generic error `This browser does not support recording.`
- Added red-first unit test in `frontend-prototype/frontend/src/App.test.js`:
  - `shows https-required error when microphone APIs are blocked by insecure context`.
  - Captures common mobile dev case (`http://<LAN-IP>:5178`) where mic APIs are blocked by non-secure context.
- Updated capability detection in `frontend-prototype/frontend/src/App.svelte`:
  - added `isSecureOrigin()` check with localhost exemptions.
  - added `getRecordingSupportError()` to map failure reason to specific user-facing messages:
    - HTTPS required on phones
    - microphone API unavailable
    - MediaRecorder unavailable
  - `startRecording()` now reports precise root cause instead of generic unsupported-browser text.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 26 passed.
  - `cd frontend-prototype/frontend && npm run build` -> succeeded.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 14 passed (`Mobile Chrome`, `Mobile Safari`).

### Frontend prototype voice dropdown expansion (JP voices + language tags)
- Added Japanese voices requested for the prototype dropdown:
  - `Kuon` (`B8gJV1IhpuegLxdpXFOE`)
  - `Hinata` (`j210dv0vWm7fCknyQpbA`)
  - `Otani` (`3JDquces8E8bkmvbh6Bc`)
- Updated backend static voice list in `frontend-prototype/server/server/app.py` to include per-voice `language` metadata (`EN`/`JP`).
- Updated frontend fallback voice list in `frontend-prototype/frontend/src/App.svelte` to match backend voice set and IDs.
- Updated dropdown rendering in `App.svelte` to display `Name (LANG)` labels when language metadata is present.
- Added tests:
  - backend: presence of requested JP names and language-tag metadata (`frontend-prototype/server/tests/test_api.py`)
  - frontend unit: language-tag rendering in voice options (`frontend-prototype/frontend/src/App.test.js`)
  - frontend e2e: fallback voice list now expects 6 tagged options (`frontend-prototype/frontend/e2e/mobile-smoke.spec.js`)
- Verification:
  - `cd frontend-prototype/server && uv run pytest tests -v` -> 20 passed.
  - `cd frontend-prototype/frontend && npm test` -> 27 passed.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 14 passed.

### Frontend prototype Japanese recommendation copy (UI)
- Added a simple in-app recommendation line under voice selector:
  - `Recommended for Japanese: Otani (JP).`
- Added unit coverage in `frontend-prototype/frontend/src/App.test.js` to assert the recommendation line is rendered.
- Added lightweight styling in `frontend-prototype/frontend/src/app.css` to match existing muted helper copy.
- Verification:
  - `cd frontend-prototype/frontend && npm test` -> 27 passed.
  - `cd frontend-prototype/frontend && npm run test:e2e` -> 14 passed.
