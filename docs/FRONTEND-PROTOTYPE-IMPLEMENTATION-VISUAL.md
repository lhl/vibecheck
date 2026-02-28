# Frontend Prototype Implementation Punchlist (Visual)

## Purpose

Build a minimal, working end-to-end visual loop in the existing frontend prototype for Android-first testing:

- Take photo (Android camera) or upload image (Android gallery/desktop)
- Send image to backend `/api/vision`
- Backend calls Mistral chat completions vision input with `mistral-large-latest`
- Use fixed server-side prompt `Describe this image`
- Render returned description text in the existing UI

This is a fast-iteration baseline extension, not a production UI.

## Scope

In scope:
- Extend existing UI in `frontend-prototype/frontend/src/App.svelte` (no new standalone app)
- Extend existing backend in `frontend-prototype/server/server/app.py` with `POST /api/vision`
- Add image preview, explicit `Describe` action, description output panel, and `Describe image` status indicator
- Enforce MIME and size validation (`jpeg/png/webp`, max `10MB`)
- Maintain mobile-first layout expectations (touch targets, responsive spacing, safe-area awareness)
- Android-focused manual verification plus desktop upload sanity check

Out of scope:
- iOS-specific behavior and QA (deferred)
- User-authored prompt input (prompt is fixed for v0)
- Persistence, auth, session history
- Advanced image processing pipelines (cropping/editing/multi-image)

## Assumptions

- Model is fixed for v0 to `mistral-large-latest`.
- Prompt is fixed server-side to `Describe this image`.
- Backend keeps `MISTRAL_API_KEY` private and proxy-only.
- Upstream API path is `POST https://api.mistral.ai/v1/chat/completions`.
- Image is sent upstream as `data:<mime>;base64,<encoded_image>` in an `image_url` content block.

## Milestones

Implementation ordering note:
- This punchlist is intentionally backend-first for integration safety and deterministic frontend mocking.
- It differs from plan phase ordering (UI-first) but keeps the same scope and acceptance criteria.

**Milestone 0: Integration Baseline**
- Confirm the visual feature is added to existing app surfaces only:
  - `frontend-prototype/frontend/src/App.svelte`
  - `frontend-prototype/server/server/app.py`
- Add/adjust test scaffolding files only where needed:
  - `frontend-prototype/server/tests/test_api.py`
  - `frontend-prototype/frontend/src/App.test.js`

Exit criteria:
- No new parallel frontend or backend app paths created.
- Existing frontend and backend still start normally.

**Milestone 1: Backend `/api/vision` Endpoint**
- Add `POST /api/vision` in `frontend-prototype/server/server/app.py`.
- Use `image: UploadFile | None = File(None)` and return explicit `400` when image is missing
  (to match contract and avoid FastAPI default `422` for required multipart fields).
- Validate request payload:
  - image present
  - MIME is validated from `UploadFile.content_type` before file bytes are read (fail fast)
  - MIME in allowlist (`image/jpeg`, `image/png`, `image/webp`)
  - size <= `VISION_MAX_UPLOAD_BYTES` (default `10485760`)
- Convert image bytes to base64 data URI.
- Call Mistral chat completions with:
  - `model: mistral-large-latest`
  - `messages[0].content`: `image_url` block + text block (`Describe this image`)
- Use upstream request timeout `60s`.
- Extract response text from `choices[0].message.content` (including array/text normalization).
- Map upstream/validation failures to explicit HTTP error contract.

Exit criteria:
- `/api/vision` returns `{"text": "...", "prompt": "Describe this image", "model": "mistral-large-latest"}` on success.
- Error mapping is deterministic for `400`, `413`, `415`, `429`, `500`, `502` with `{"detail":"..."}` response body.
- Backend tests for endpoint happy/error paths pass.

**Milestone 2: Frontend UI Extension (Existing App)**
- Extend `App.svelte` with visual controls:
  - `Take Photo` (capture input)
  - `Upload Photo` (non-capture input)
  - image preview
  - explicit `Describe` button
  - `Describe image` status indicator
  - description output panel
- Add visual mode state handling:
  - `idle`, `image_selected`, `describing`, `described`, `error`
- Keep visual flow additive to the existing audio flow; do not remove or regress record/transcribe/speak behavior.
- Add client-side MIME/size validation before upload.
- Keep mobile-first control sizing/spacing and safe-area behavior intact.

Exit criteria:
- User can select/capture image and see preview.
- `Describe` is disabled until a valid image is selected.
- Validation errors are visible and actionable.
- Status indicator accurately reflects describe lifecycle.

**Milestone 3: End-to-End Vision Flow**
- Wire frontend submit action to `/api/vision`.
- Render returned text on success.
- Keep selected image visible across failures.
- Add retry behavior that reuses current selected image.
- Handle no-file-selected after camera/gallery activation (cancel or camera access blocked) with clear guidance.

Exit criteria:
- Successful end-to-end describe flow works in browser.
- Backend response text is rendered reliably.
- Retry path works after transient failures.
- No-file-selected path is handled gracefully without broken state.

**Milestone 4: Hardening + Android QA**
- Add stale-response guard (request-id) so old responses do not overwrite new selections.
- Ensure controls are correctly disabled while requests are in flight.
- Confirm Android-first capture/upload behavior with real-device sanity pass.
- Confirm desktop upload path remains functional.

Exit criteria:
- Rapid retake/reupload while in-flight does not produce stale output.
- Android camera and gallery paths both function.
- No provider API key appears in frontend source or browser requests; no direct provider calls from browser.

## Test Requirements

### Backend Tests (`frontend-prototype/server/tests/test_api.py`)

Add tests for `POST /api/vision` at minimum:
- Happy path: valid image => 200 + expected JSON shape
- Missing file => 400 (not FastAPI default 422)
- Unsupported MIME => 415
- Too large payload => 413
- Missing `MISTRAL_API_KEY` => 500
- Upstream timeout/auth/transport failure => 502 mapping
- Upstream rate limit => 429 mapping
- Empty upstream content => 502
- Structured upstream content array is normalized to output text
- Error responses include `detail` message

Use mocked upstream HTTP calls (`httpx` patch/mocking). Do not require network.

### Frontend Tests (`frontend-prototype/frontend/src/App.test.js`)

Add tests at minimum:
- Select image -> preview appears -> `Describe` enabled
- Invalid MIME/oversize image blocked client-side
- `Describe` posts multipart to `/api/vision` and renders response text
- Error response surfaces message and allows retry
- Stale-response guard prevents outdated result overwrite
- Status indicator transitions across idle/processing/success/error states

### E2E / Smoke

Extend mobile smoke coverage where practical:
- Android-like flow: select image, describe, render output
- Failure/retry behavior
- No-file-selected behavior (cancel/blocked capture path) is handled without UI breakage

## Verification Checklist

- Backend tests: `cd frontend-prototype/server && uv run pytest tests/test_api.py -v`
- Frontend unit tests: `cd frontend-prototype/frontend && npm test`
- Frontend e2e smoke: `cd frontend-prototype/frontend && npm run test:e2e`
- Frontend secret scan: `cd frontend-prototype/frontend && npm run test:secrets`
- Frontend build: `cd frontend-prototype/frontend && npm run build`
- Manual Android check:
  - take photo -> describe success
  - gallery upload -> describe success
  - launch camera then cancel/return with no file -> UI remains usable and guidance is clear
  - force failure -> retry works

## Completion Criteria

- Visual feature is integrated into existing frontend/backend files (no parallel app)
- `/api/vision` is implemented with fixed prompt + fixed model contract
- Visual flow is additive and does not regress existing audio flow
- UI supports Android camera + gallery and desktop upload
- UI includes `Describe image` status indicator and mobile-first touch/safe-area behavior
- Selected image preview is shown before submit
- `Describe` is explicit user-triggered submit action
- Description text is rendered on successful response
- Validation/error/retry behavior is implemented and tested
- Stale request handling prevents outdated responses
- No API key is exposed in frontend source or browser network calls
- All verification commands pass
- Acceptance criteria in `docs/FRONTEND-PROTOTYPE-PLAN-VISUAL.md` are satisfied

## Worklog

- Update `docs/FRONTEND-WORKLOG-VISUAL.md` and `WORKLOG.md` with major implementation actions and decisions for visual prototype milestones.
