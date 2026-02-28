# TODO

- [ ] Add `HACKING.md` quickstart (commands to run backend/frontend, expected URLs).
- [ ] Document env vars/secrets (MISTRAL_API_KEY, VIBECHECK_PSK, VIBECHECK_VAPID_SUB, VIBECHECK_MAX_AUDIO_BYTES, host settings) and add `.env.example`.
- [ ] Define the API contract with endpoint list and sample payloads.
- [ ] Document approval/input callback flow and waiting-state logic.
- [ ] Add deployment runbook details (systemd unit, logs, restart, health checks).
- [ ] Add troubleshooting guide (WSS handshake, push delivery, Voxtral errors).
- [ ] Add smoke-test scripts: HTTP endpoints, WS events, push notification.
- [ ] Add event replay fixtures + `scripts/replay_events.py` for UI development.
- [ ] Add Devstral 2 context pack (short architecture + file map for Vibe).
- [x] Review `PLAN.md` and create `IMPLEMENTATION.md`.
- [ ] Add rate limiting / spend caps for Mistral-backed endpoints (`/api/voice/transcribe`, `/api/translate`, `/api/push/*`).
- [ ] Add UI/API to configure push intensity level + snooze.
