# Phase 6 Review (Reviewer 3) — Resolutions

Date: 2026-02-28

Scope:
- Phase 6A — Voice (WU-17/18): `POST /api/voice/transcribe` + FE hold-to-record + language setting
- Phase 6B — Push (WU-19/20): VAPID + subscriptions + triggers; FE SW handling + subscribe toggle UI
- Phase 6D — Translation (WU-21): `POST /api/translate`; FE per-message 🌐 toggle + cache + CJK-skip + global auto-translate
- Phase 6C — Smart notifications (WU-22): `IntensityManager` + Ministral copy/urgency helpers
- Watch item: emit `user_message` immediately on `inject_message()` w/ dedupe vs Vibe echoes

This file captures the initial Phase 6 review notes and tracks the follow-up fixes that landed after review.

## Status (post-follow-up fixes)

Verification (current):
- Backend: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest vibecheck/tests/ -v` → **116 passed**
- Frontend: `cd vibecheck/frontend && npm test && npm run build` → **59 passed**, build **OK**

### Fix status

#### Voice (6A)

- ✅ Request-size guard + streaming reads + audio content-type validation: `87cf90b`, `99b623f`
- ✅ Language allowlist (`ja`/`en`) enforced server-side: `99b623f`
- ✅ Mic press/release race fix (no stuck recordings on quick release): `e2904c1`
- ✅ Handle `touchcancel` to avoid stuck recording state: `d4ad387`
- ✅ Recorder error clears active state (no permanent lockout after `recorder.onerror`): `faecd36`
- ✅ Max recording duration (defaults to 60s): `9ab249a`
- ✅ MicButton teardown now stops active recording (releases mic/tracks): `22f4423`
- ✅ Upstream timeout (30s) on STT SDK call — returns 504 on hang: `22f4423`

#### Push + smart notifications (6B/6C)

- ✅ Approve/Deny notification actions wired end-to-end (SW → app → REST approve): `7ac7f63`
- ✅ VAPID key file corruption guard + restrictive permissions + configurable `sub` claim (`VIBECHECK_VAPID_SUB`): `e6bd9c4`
- ✅ Dead subscription cleanup on `404/410`: `e6bd9c4`
- ✅ Unsubscribe ordering fixed (backend first, then local unsubscribe): `ae72a8d`
- ✅ Subscribe reuses existing subscription (avoids `InvalidStateError`): `9bb919a`
- ✅ Idle escalation worker wired (requires intensity `level >= 3`; no UI/API yet): `f07df48`
- ✅ Push payload includes `call_id` — notification actions are now call-bound (stale notifications can't approve wrong call): `22f4423`
- ✅ Idle escalation tracks all waiting sessions (set, not single slot): `22f4423`

#### Translation (6D)

- ✅ `target_lang` strip-before-validate + lang-code pattern + max request size: `22dbd29`
- ✅ Reject whitespace-only translate text: `0079363`
- ✅ Cap translation cache size (200): `9b6589c`
- ✅ Expanded backend test coverage for auth/error paths: `7f44290`, `7e4c98a`
- ✅ Upstream timeout (15s) on translate SDK call — returns 504 on hang: `22f4423`

#### Watch item (user bubbles)

- ✅ Immediate local `user_message` emit on `inject_message()`: `a029587`
- ✅ Dedupe narrowed to the active injected message + shorter window (10s): `e2904c1`

### Remaining (non-blocking)

- Rate limiting / usage caps on `/api/voice/transcribe`, `/api/translate`, `/api/push/*`.
- ~~Decide PSK-in-query-param policy for REST.~~ **Decision (2026-02-28):** intentionally kept for dev convenience; documented in `docs/PLAN.md`.
- No user-facing API/UI to configure push intensity level or snooze.
- ~~Translation FE error UX doesn’t parse JSON `{detail}` (uses `status/statusText` only).~~ Fixed in `b6f50d1` (ChatMessage + ApprovalPanel now extract `detail`).

---

## Initial review snapshot

Note: the sections below are preserved from the initial review; the follow-ups are now resolved (see “Fix status” above) and some file/behavior notes may be stale.

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
