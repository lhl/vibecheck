# vibecheck — Frontend Worklog (Visual)

## 2026-02-28

### Milestone 4 - hardening coverage expansion (automated)
- Expanded stale-response guard regression coverage in `frontend-prototype/frontend/src/App.test.js`:
  - added stale-success path test to ensure outdated `200` responses do not overwrite a newer image selection
  - added stale-non-2xx detail path test to ensure outdated error-detail parsing does not overwrite newer state
- Extended proxy/security assertions to explicitly include vision flow:
  - unit-level proxy/header test now performs a visual describe request and asserts `/api/vision` is proxy-only with no provider auth headers
  - e2e proxy/header test in `frontend-prototype/frontend/e2e/mobile-smoke.spec.js` now includes a visual describe step and verifies no provider direct calls plus no auth-key headers on vision requests
- Verification run:
  - `cd frontend-prototype/frontend && npm test -- src/App.test.js -t "ignores stale success response from an outdated describe request|ignores stale non-2xx detail parsing from an outdated describe request|sends browser requests only to proxy endpoints without provider API auth headers"` -> passed (`3` tests)
  - `cd frontend-prototype/frontend && npm run test:e2e -- --grep "mobile browser uses local proxy routes only and does not send provider auth headers"` -> passed (`2` tests)
  - `cd frontend-prototype/frontend && npm test` -> passed (`45` tests)
  - `cd frontend-prototype/frontend && npm run test:e2e` -> passed (`22` tests)
  - `cd frontend-prototype/frontend && npm run test:secrets` -> passed
  - `cd frontend-prototype/frontend && npm run build` -> passed
- Manual Android/desktop device QA evidence for Milestone 4 remains pending user-run by request.

### Milestone 3 - reviewer remediation follow-up
- Addressed stale-response and failure-branch gaps in `frontend-prototype/frontend/src/App.svelte`:
  - added stale guard check in the invalid-JSON response branch before calling `setVisionError(...)`
  - updated invalid-replacement and preview-failure paths to use retry guidance when a prior valid image is still selected (`Tap Describe to retry.`)
- Expanded milestone-3 frontend unit coverage in `frontend-prototype/frontend/src/App.test.js`:
  - stale-response regression: outdated request with delayed invalid-JSON parse cannot overwrite current selection state
  - transport failure path (`fetch` throw) -> retryable error contract
  - invalid JSON success-body path -> retryable error contract
  - empty description-text payload path -> retryable error contract
  - non-JSON error-body fallback path -> status-based detail message contract
  - retained-image invalid replacement now asserts retry guidance text
- Added backend helper-coverage parity test in `frontend-prototype/server/tests/test_api.py`:
  - `test_describe_image_connect_error_raises_upstream_error`
- Verification run:
  - `cd frontend-prototype/frontend && npm test -- src/App.test.js -t "App visual milestone 3 end-to-end flow"` -> passed (`16` tests in scope)
  - `cd frontend-prototype/frontend && npm test` -> passed (`43` tests)
  - `cd frontend-prototype/frontend && npm run test:e2e` -> passed (`22` tests)
  - `cd frontend-prototype/frontend && npm run test:secrets` -> passed
  - `cd frontend-prototype/frontend && npm run build` -> passed
  - `cd frontend-prototype/server && uv run pytest tests/test_api.py -v` -> passed (`44` tests)

### Milestone 3 - end-to-end vision flow wiring
- Replaced the milestone-2 simulated describe path in `frontend-prototype/frontend/src/App.svelte` with real backend integration:
  - `Describe` now submits multipart `FormData` (`image`) to `POST /api/vision`
  - successful responses render backend `text` content in the Image Description panel
  - non-2xx and transport failures map to actionable UI errors with retry guidance (`Tap Describe to retry.`)
  - selected image is preserved across failures so retry uses the same current selection
- Updated visual state handling in `App.svelte`:
  - no-file-selected (camera/gallery cancel or blocked return) now sets clear status guidance: `No image selected. Choose Take Photo or Upload Photo.`
  - retained stale-response guard behavior via `visionSequenceCounter`
  - removed the artificial describe-delay timer used in milestone-2 preview simulation
- Expanded frontend unit coverage in `frontend-prototype/frontend/src/App.test.js`:
  - verifies multipart submit to `/api/vision` and response-text rendering
  - verifies error -> retry -> success flow while keeping image selection
  - verifies no-file-selected guidance text branch
- Expanded frontend e2e smoke coverage in `frontend-prototype/frontend/e2e/mobile-smoke.spec.js`:
  - visual describe flow now stubs `/api/vision` and asserts real response rendering
  - added transient-failure retry scenario
  - updated idle-cancel expectation for new no-file-selected guidance text
- Installed missing Playwright browser binaries for local e2e execution:
  - `cd frontend-prototype/frontend && npx playwright install chromium webkit`
- Verification run:
  - `cd frontend-prototype/frontend && npm test -- src/App.test.js -t "App visual milestone 3 end-to-end flow"` -> passed (`11` tests in scope)
  - `cd frontend-prototype/frontend && npm test` -> passed (`38` tests)
  - `cd frontend-prototype/frontend && npm run test:e2e -- --grep "mobile visual flow"` -> passed (`8` tests)
  - `cd frontend-prototype/frontend && npm run test:e2e` -> passed (`22` tests)
  - `cd frontend-prototype/frontend && npm run test:secrets` -> passed
  - `cd frontend-prototype/frontend && npm run build` -> passed

### Milestone 2 - frontend visual UI extension in existing app
- Extended `frontend-prototype/frontend/src/App.svelte` with additive visual controls and state handling:
  - `Take Photo` trigger wired to hidden capture input (`accept="image/*"`, `capture="environment"`)
  - `Upload Photo` trigger wired to hidden non-capture input (`accept="image/*"`)
  - explicit `Describe` action button
  - visual state machine (`idle`, `image_selected`, `describing`, `described`, `error`)
  - image preview panel and separate description output panel
  - dedicated `Describe image` status indicator and visual state pill
- Added client-side validation in `App.svelte` before any upload wiring:
  - MIME allowlist: `image/jpeg`, `image/png`, `image/webp`
  - max size: `10MB`
  - actionable validation errors rendered in visual panel
- Added milestone-2 describe lifecycle simulator (status transitions) without `/api/vision` request wiring yet.
- Added/extended frontend tests in `frontend-prototype/frontend/src/App.test.js`:
  - visual controls rendered + capture/non-capture input attributes
  - valid selection enables `Describe` and renders preview
  - invalid MIME and oversized file validation paths
  - status/state transitions through `image_selected -> describing -> described`
- Updated visual styling in `frontend-prototype/frontend/src/app.css` for mobile-first layout, touch targets, preview container, and visual state tokens.
- Verification run:
  - `cd frontend-prototype/frontend && npm test -- src/App.test.js -t "App visual milestone 2 UI extension"` -> passed
  - `cd frontend-prototype/frontend && npm test` -> passed (`32` tests)
  - `cd frontend-prototype/frontend && npm run test:e2e` -> passed (`14` tests)
  - `cd frontend-prototype/frontend && npm run test:secrets` -> passed
  - `cd frontend-prototype/frontend && npm run build` -> passed

### Milestone 2 - reviewer remediation pass
- Addressed review feedback in `frontend-prototype/frontend/src/App.svelte`:
  - improved hidden file input accessibility behavior with `aria-hidden="true"` + `tabindex="-1"` and added stable `data-testid` selectors
  - fixed cancel/empty-file handling to clear stale visual errors
  - normalized cancel behavior:
    - no prior valid image -> reset to `idle` with `No image selected`
    - prior valid image -> clear transient error and keep prior valid selection/state
  - preserved prior valid image on invalid replacement instead of clearing selection
  - made validation errors more actionable with explicit reselect guidance (`Choose Take Photo or Upload Photo and try again.`)
- Expanded frontend unit coverage in `frontend-prototype/frontend/src/App.test.js`:
  - `Take Photo` / `Upload Photo` click-to-hidden-input wiring
  - picker disabled state during `describing`
  - empty-file (cancel) branches for idle / prior-valid / prior-error paths
  - prior-valid preservation on invalid replacement
- Added visual e2e smoke coverage in `frontend-prototype/frontend/e2e/mobile-smoke.spec.js`:
  - upload + describe lifecycle + in-flight control disablement
  - invalid replacement preserves prior valid image
  - cancel after no-prior error resets to idle and clears stale error
- Verification run:
  - `cd frontend-prototype/frontend && npm test -- src/App.test.js -t "App visual milestone 2 UI extension"` -> passed
  - `cd frontend-prototype/frontend && npm run test:e2e -- --grep "mobile visual flow"` -> passed
  - `cd frontend-prototype/frontend && npm test` -> passed (`36` tests)
  - `cd frontend-prototype/frontend && npm run test:e2e` -> passed (`20` tests)
  - `cd frontend-prototype/frontend && npm run test:secrets` -> passed
  - `cd frontend-prototype/frontend && npm run build` -> passed

### Milestone 2 - accessibility and clarity follow-up
- Resolved duplicate live-announcement risk in `frontend-prototype/frontend/src/App.svelte`:
  - visual status region now uses `aria-live="off"` during visual error state
  - `role="alert"` error message remains the single detailed announcement channel
  - error status label normalized to `Describe image failed`
- Renamed stale-guard counter from `visionRequestCounter` to `visionSequenceCounter` with an inline comment clarifying it spans both selection and describe sequence changes.
- Added assertion coverage in `frontend-prototype/frontend/src/App.test.js` to verify error-state status behavior:
  - status message text in error state
  - `aria-live` switches to `off` in error state
- Verification run:
  - `cd frontend-prototype/frontend && npm test -- src/App.test.js -t "App visual milestone 2 UI extension"` -> passed
  - `cd frontend-prototype/frontend && npm test` -> passed (`36` tests)
  - `cd frontend-prototype/frontend && npm run test:e2e -- --grep "mobile visual flow|mobile UI renders and state preview transitions work"` -> passed (`8` tests)
  - `cd frontend-prototype/frontend && npm run test:secrets` -> passed
  - `cd frontend-prototype/frontend && npm run build` -> passed

### Milestone 1 - review hardening pass
- Addressed reviewer findings in `frontend-prototype/server/server/app.py`:
  - normalized `/api/vision` upstream error mapping to stable client-safe messages (no raw provider payload passthrough)
  - added guarded parsing for `VISION_MAX_UPLOAD_BYTES` with explicit JSON `500` detail on invalid values
  - reordered `/api/vision` validation flow so MIME/size payload checks run before API-key check
  - added inline maintainer note on `image_url` format compatibility (Mistral accepts both string data URI and object form)
- Expanded `frontend-prototype/server/tests/test_api.py` coverage:
  - empty image payload branch (`400`)
  - invalid `VISION_MAX_UPLOAD_BYTES` handling (`500` with detail)
  - MIME-before-size ordering regression (`415` precedence)
  - payload-validation-before-api-key ordering regression (`415` even when key is missing)
  - no raw-detail leakage assertions for upstream `4xx` and `5xx` failures
  - `describe_image` parser branches: invalid JSON, missing choices, malformed choice, malformed message
- Removed redundant env setup from missing-image test.
- Verification run:
  - `cd frontend-prototype/server && uv run pytest tests/test_api.py -q` -> `42 passed`
  - `cd frontend-prototype/server && uv run pytest tests/ -v` -> `42 passed`
- Follow-up: added dedicated test for the non-positive env guard branch (`VISION_MAX_UPLOAD_BYTES=0`) to ensure explicit JSON `500` detail is locked by automation.

### Milestone 1 - backend `/api/vision` implementation
- Added `POST /api/vision` in `frontend-prototype/server/server/app.py` using optional `image: UploadFile | None = File(None)` and explicit `400` for missing image.
- Added server-side MIME allowlist validation (`image/jpeg`, `image/png`, `image/webp`) before reading upload bytes.
- Added size-limit enforcement using `VISION_MAX_UPLOAD_BYTES` (default `10485760`) with explicit `413` on overflow.
- Added Mistral vision proxy helper (`describe_image`) targeting `POST /v1/chat/completions` with:
  - model: `mistral-large-latest`
  - fixed prompt: `Describe this image`
  - image data URI: `data:<mime>;base64,<bytes>`
  - timeout: `60s`
- Added normalization for structured `choices[0].message.content` arrays into plain output text.
- Added deterministic vision error mapping:
  - `429` passthrough for rate limit
  - `502` for auth/upstream/transport/empty-content failures
  - `500` when `MISTRAL_API_KEY` is missing

### Milestone 1 - backend test coverage
- Extended `frontend-prototype/server/tests/test_api.py` with `/api/vision` endpoint tests:
  - happy path contract
  - missing image (`400`)
  - unsupported MIME (`415`)
  - oversized payload (`413`)
  - missing `MISTRAL_API_KEY` (`500`)
  - upstream rate-limit mapping (`429`)
  - upstream auth/transport/empty-content mapping (`502`)
- Added helper-level tests for `describe_image`:
  - structured content-array normalization
  - empty content detection to upstream error
- Verification run:
  - `cd frontend-prototype/server && uv run pytest tests/test_api.py -q` -> `31 passed`
  - `cd frontend-prototype/server && uv run pytest tests/ -v` -> `31 passed`

### Visual prototype docs setup
- Added `docs/FRONTEND-PROTOTYPE-PLAN-VISUAL.md` for Android-first camera/gallery image description flow.
- Added `docs/FRONTEND-PROTOTYPE-IMPLEMENTATION-VISUAL.md` with milestone-based implementation and verification gates.
- Clarified visual implementation contract:
  - integrate into existing `App.svelte` and `server/server/app.py`
  - fixed model `mistral-large-latest`
  - fixed server-side prompt `Describe this image`
  - explicit `Describe` submit action
  - backend error/test coverage includes `500` missing-key case
