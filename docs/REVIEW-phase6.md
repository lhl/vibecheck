# Phase 6 Review (Reviewer 3)

Date: 2026-02-28

Scope:
- Phase 6A — Voice (WU-17/18): `POST /api/voice/transcribe` + FE hold-to-record + language setting
- Phase 6B — Push (WU-19/20): VAPID + subscriptions + triggers; FE SW handling + subscribe toggle UI
- Phase 6D — Translation (WU-21): `POST /api/translate`; FE per-message 🌐 toggle + cache + CJK-skip + global auto-translate
- Phase 6C — Smart notifications (WU-22): `IntensityManager` + Ministral copy/urgency helpers
- Watch item: emit `user_message` immediately on `inject_message()` w/ dedupe vs Vibe echoes

Commits reviewed:
- Voice: `0887272`
- Push backend: `3aebc2f`
- Push frontend: `3c15a5a`
- Translation: `9bea299`
- Smart notifications: `2f84b28`
- Watch item (user bubbles): `a029587`
- Worklog: `734d736`

## Verification (as-run)

- Backend: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` → **79 passed**
- Frontend: `cd vibecheck/frontend && npm test && npm run build` → **48 passed**, build **OK**

## Highlights

- Good unit coverage for each new backend route (`test_voice.py`, `test_push.py`, `test_translate.py`) and new FE modules/components.
- Push “smart copy”/urgency logic is structured defensively (timeout + fallback), and the `IntensityManager` behavior is covered by tests.
- Watch item dedupe approach avoids double user bubbles and is covered by tests.

## Findings / Follow-ups

### Voice (6A)

- **Add an explicit request-size guard** for raw audio bodies (today this will read the full body into memory). See `vibecheck/routes/voice.py` (`await request.body()`).
- **Mic UX edge case:** handle `touchcancel` (or migrate to pointer events) so interrupted touches don’t leave recording state stuck. See `vibecheck/frontend/src/components/MicButton.svelte`.
- Consider validating/normalizing the `language` query param to a small allowlist (`ja`/`en`) to avoid surprising upstream errors.

### Push + smart notifications (6B/6C)

- **Notification actions are not end-to-end yet.** Backend includes approve/deny actions in payload, but the SW/app don’t currently process them into API calls. See:
  - Payload actions in `vibecheck/push.py` (`approval_request` payload)
  - SW click behavior in `vibecheck/frontend/public/sw.js` (posts `notification_action`, opens `?action=...`)
  - App only reads `sid`/`session_id` query params in `vibecheck/frontend/src/App.svelte`
- **VAPID keys file corruption path:** `vapid_keys.json` load is not `JSONDecodeError`-guarded; a corrupt file will crash instead of regenerating. See `vibecheck/push.py` keypair load path.
- Consider locking down key file permissions on write and making the VAPID `sub` claim configurable (currently hardcoded to `mailto:vibecheck@localhost`).
- Packaging note: `py_vapid` / `cryptography` are relied on via `pywebpush`; consider pinning explicitly if you want to avoid dependency drift surprises.

### Translation (6D)

- Add a **max length** constraint for `TranslateRequest.text` (and optionally validate `target_lang`) to cap cost/memory and avoid accidental huge requests. See `vibecheck/routes/translate.py`.
- FE error UX could be improved by reading JSON `{detail}` when present (similar to the voice UI).

### Watch item (user bubbles)

- Dedupe by `(content, time-window)` is reasonable for now; note it can still double-bubble if Vibe echoes arrive outside the window. See `vibecheck/bridge.py` local echo queue.

## Coverage nudge (low effort)

- Add `/api/push/*`, `/api/translate`, and `/api/voice/transcribe` to the “PSK required” parametrized test so auth regressions are harder to introduce. See `vibecheck/tests/test_api.py`.

