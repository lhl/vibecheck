# Phase 3.1 Manual Test HOWTO (WU-34)

This guide is the canonical runbook for validating live terminal + phone behavior.

## Purpose

Validate that Phase 3.1 acceptance criteria are satisfied against a real `vibecheck-vibe` run:

- Remote approval/question resolution returns terminal UI to input mode.
- First-response-wins race behaves correctly.
- Reconnect flow works during pending approval.
- Known limitations are documented and observed consistently.

## Prerequisites

- Running from repo root: `/home/ubuntu/vibecheck`
- `VIBECHECK_PSK` exported in shell
- `MISTRAL_API_KEY` exported in shell (if using Mistral provider)
- Caddy routing `https://<domain>` to local app (typically localhost:7870)
- Runtime deps installed once:

```bash
uv pip install -e reference/mistral-vibe
```

## Networking Note

You do **not** need to expose port `7870` publicly.

- Public access should be `22/80/443` only.
- Caddy should terminate TLS and proxy to local backend on `7870`.
- Phone uses `https://...` and `wss://...` via port `443`.

## Recommended Startup (Avoid Local llama.cpp Failure)

If your Vibe config has `active_model = "local"` and no local llama.cpp server is running,
force a cloud model for manual testing:

```bash
VIBE_ACTIVE_MODEL=devstral-2 scripts/manual-test/capture.sh --base-url https://<your-domain>
```

## Terminal Layout

- Terminal A: runtime + transcript capture
- Terminal B: guided checklist runner
- Phone: PWA open at `https://<your-domain>` on the live session

### Terminal A

```bash
cd /home/ubuntu/vibecheck
VIBE_ACTIVE_MODEL=devstral-2 scripts/manual-test/capture.sh --base-url https://<your-domain>
```

### Terminal B

```bash
cd /home/ubuntu/vibecheck
scripts/manual-test/run.sh --base-url https://<your-domain> --save-env
```

`run.sh` walks through all scenarios, checks API state transitions, and records pass/fail.
By default, `--save-env` stores only `BASE_URL` and `PSK`; it does not pin `SID`, so restarts
auto-select the current live session.

## Scenarios Covered by `run.sh`

- `S1_REMOTE_APPROVE`
- `S2_REMOTE_REJECT`
- `S3_REMOTE_QUESTION_ANSWER`
- `S4_FIRST_RESPONSE_WINS`
- `S5_RECONNECT_PENDING`
- `S6_GAP2_VISIBILITY` (known limitation allowed)
- `S7_GAP3_USABILITY`

## Output Artifacts

At completion:

- `artifacts/manual-test/wu34-<timestamp>/results.tsv`
- `artifacts/manual-test/wu34-<timestamp>/report.md`

Share `report.md` or its `Pasteback Summary` block for review/WORKLOG logging.

## Troubleshooting

### `ModuleNotFoundError: tomli_w` (or missing `vibe` deps)

Install runtime package/deps:

```bash
uv pip install -e reference/mistral-vibe
```

### `StylesheetError: ... /vibecheck/app.tcss`

Your branch is missing the launcher CSS path fix. Pull latest branch changes and retry.

### `All connection attempts failed ... http://127.0.0.1:8080`

Active model is `local` (llama.cpp provider) but local server is down.
Use `VIBE_ACTIVE_MODEL=devstral-2` when launching `capture.sh`, or change `~/.vibe/config.toml`.

### No events on phone while TUI appears active

- Confirm phone is on the same `session_id` shown by `run.sh`.
- Check API state from Terminal B:

```bash
scripts/manual-test/api.sh sessions
scripts/manual-test/api.sh selected-sid
scripts/manual-test/api.sh state
scripts/manual-test/api.sh ws-check
```

- Verify `attach_mode` is `live` and `controllable` is `true`.
