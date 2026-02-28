# Frontend Prototype Plan (Visual)

## Goal

Build a very simple visual flow in the existing frontend prototype:

1. Take a photo on Android (camera) or upload an image (gallery/desktop)
2. Send image to backend proxy
3. Backend calls Mistral chat completions with vision input (`mistral-large-latest`) and fixed prompt `Describe this image`
4. Show returned description text on screen

This is a base scaffold extension, not a new app.

Android is the only required mobile target for this iteration. iOS support is out of scope for now.

## Scope (v0)

- Extend the existing single-page app with:
  - `Take Photo` action (Android camera capture path)
  - `Upload Photo` action (Android gallery and desktop file picker path)
  - Selected image preview area
  - `Describe` button (explicit submission trigger)
  - Description output area
  - `Describe image` status indicator
- One backend proxy service to keep `MISTRAL_API_KEY` server-side
- Fixed prompt for v0: `Describe this image` (server-side constant, not client-overridable)
- Model fixed for v0: `mistral-large-latest`
- Allowed image MIME types: `image/jpeg`, `image/png`, `image/webp`
- Max upload size: `10MB` (`VISION_MAX_UPLOAD_BYTES` default `10485760`)
- No persistence, auth, session history, or advanced UX yet
- Mobile-first interaction and layout (touch targets, responsive spacing, safe-area awareness)

## Integration Target (Existing App)

This work extends the existing prototype and does not create a new frontend or backend app.

- Frontend integration point: `frontend-prototype/frontend/src/App.svelte`
- Backend integration point: `frontend-prototype/server/server/app.py`
- Backend tests: extend `frontend-prototype/server/tests/test_api.py`
- Frontend tests: extend `frontend-prototype/frontend/src/App.test.js` and e2e smoke coverage where appropriate

## High-Level Architecture

```text
Existing Browser App (App.svelte)
  -> POST /api/vision (image file)
      -> Backend validates size/type, base64-encodes image
      -> POST https://api.mistral.ai/v1/chat/completions
      -> model: mistral-large-latest
      -> messages[0].content = [image_url(data URI), text("Describe this image")]
      <- description text
Existing Browser App renders returned description
```

## Why Proxy Through Backend

- Prevent exposing `MISTRAL_API_KEY` in browser code
- Centralize image validation and request shaping
- Keep frontend simple and replaceable later

## API Contract (Prototype)

### `POST /api/vision`

Proxies to Mistral chat completions vision input via backend HTTP call. Uses `MISTRAL_API_KEY`.

- Request: multipart form-data
  - `image`: uploaded/captured file (`image/jpeg`, `image/png`, `image/webp`)
- Response:

```json
{
  "text": "description of the image",
  "prompt": "Describe this image",
  "model": "mistral-large-latest"
}
```

### Upstream Mapping (Backend -> Mistral)

- Endpoint: `POST https://api.mistral.ai/v1/chat/completions`
- Headers:
  - `Authorization: Bearer <MISTRAL_API_KEY>`
  - `Content-Type: application/json`
- Payload shape:

```json
{
  "model": "mistral-large-latest",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": "data:<mime>;base64,<encoded_image>"
        },
        {
          "type": "text",
          "text": "Describe this image"
        }
      ]
    }
  ]
}
```

- Response extraction path:
  - Primary: `choices[0].message.content`
  - If provider returns structured content array, extract text segments and join them
- Upstream timeout: `60s`

### Error Contract (Backend Response)

- `400` -> invalid/missing image payload
- `413` -> image exceeds `VISION_MAX_UPLOAD_BYTES`
- `415` -> unsupported image MIME type
- `429` -> upstream rate-limited
- `502` -> upstream/auth/transport failure or empty model response

Error response body:

```json
{
  "detail": "human-readable error message"
}
```

## Frontend Flow

1. User taps `Take Photo` (Android camera) or `Upload Photo` (gallery/desktop picker)
2. Browser receives selected image file
3. UI validates size/type and renders local preview
4. User taps `Describe`
5. Frontend uploads file to `/api/vision`
6. Backend applies fixed prompt `Describe this image`
7. UI shows `describing` state while waiting
8. UI renders returned text description
9. User can retake or upload another image and describe again

Android capture behavior for v0:
- Keep two separate controls:
  - `Take Photo`: file input with `accept="image/*"` and `capture="environment"`
  - `Upload Photo`: file input with `accept="image/*"` and no `capture`

Stale request handling:
- If user selects a new image while a describe request is in flight, track a request ID and ignore stale responses.

## Error Handling (v0)

- Camera permission denied -> clear message and retry option
- Unsupported file type -> validation message before upload
- File too large -> validation message before upload
- Vision API failure -> show error and keep selected image visible for retry
- Empty model response -> show fallback error and allow retry

## Minimal UI State

- `idle`
- `image_selected`
- `describing`
- `described`
- `error`

## Suggested File Layout

```text
frontend-prototype/
  frontend/
    src/
      App.svelte               # extend existing root component with visual mode
      App.test.js              # extend existing unit tests
  server/
    server/
      app.py                   # extend existing app with /api/vision
    tests/
      test_api.py              # add /api/vision tests
```

## Implementation Phases

### Phase 1: UI Extension
- Extend existing `App.svelte` with take/upload controls, preview area, describe action, and response panel
- Add visual state rendering (`idle`, `image_selected`, `describing`, `described`, `error`)

### Phase 2: Image Input Path
- Implement Android camera capture path
- Implement gallery/desktop upload path
- Validate type and size client-side

### Phase 3: Vision Path
- Implement backend `POST /api/vision` in existing `server/server/app.py`
- Call Mistral chat completions with model `mistral-large-latest`
- Send fixed prompt `Describe this image` from backend
- Display returned description

### Phase 4: Hardening
- Add user-facing error messages and retry behavior
- Add stale-response guard for rapid retake/reupload while request is in flight
- Confirm Android mobile browser behavior as primary acceptance path
- Confirm desktop file upload behavior as secondary acceptance path

## Verification Checklist

- Backend tests: `cd frontend-prototype/server && uv run pytest tests/test_api.py -v`
- Frontend unit tests: `cd frontend-prototype/frontend && npm test`
- Frontend e2e smoke tests: `cd frontend-prototype/frontend && npm run test:e2e`
- Frontend build: `cd frontend-prototype/frontend && npm run build`
- Manual Android check: take photo + upload from gallery + successful description + retry on failure

## Acceptance Criteria (Prototype Complete)

- Existing frontend app includes visual mode in `App.svelte` (no new standalone app)
- Existing backend app includes `POST /api/vision` in `server/server/app.py`
- User can take a photo on Android phone and upload an image from Android gallery/desktop
- Selected image preview is shown before request
- User explicitly taps `Describe` to submit
- Backend sends image to Mistral chat completions (`mistral-large-latest`) with prompt `Describe this image`
- Description text appears in UI on success
- Type/size limits are enforced consistently on frontend and backend
- No API key (`MISTRAL_API_KEY`) appears in frontend source or browser network calls
- `/api/vision` backend tests and frontend test/build gates pass
- Prototype is usable on Android browsers with mobile-first layout and touch-friendly controls
