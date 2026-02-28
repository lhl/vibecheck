# WU-34 Manual Validation Harness

This folder provides a guided, repeatable manual test run for Phase 3.1 acceptance.

For the full operator runbook (prereqs, exact commands, troubleshooting), see:
`scripts/manual-test/manual-test.howto.md`

## Files

- `capture.sh`: Starts `vibecheck-vibe` with terminal transcript capture (`script`).
- `run.sh`: Interactive checklist runner for WU-34 scenarios with pass/fail capture.
- `api.sh`: Session API helper commands (`state`, `wait-pending-approval`, `approve`, etc.).
  - Includes `ws-check` to validate live session WebSocket delivery before running scenarios.
- `tui_prompts.sh`: Canonical prompt text to paste into the TUI for each scenario.

## Recommended Terminal Layout

- **Terminal A**: TUI runtime + transcript capture  
  `scripts/manual-test/capture.sh --base-url https://<your-domain>`
- **Terminal B**: Interactive checklist runner  
  `scripts/manual-test/run.sh --base-url https://<your-domain>`
- **Phone**: Open the same `https://<your-domain>` PWA and connect to the live session.

## One-Time Runtime Preflight

If `capture.sh` reports missing Vibe runtime dependencies, run:

```bash
uv pip install -e reference/mistral-vibe
```

This installs the reference Vibe package and required runtime dependencies into the current `uv` environment.

## Optional Pre-Configuration

You can persist local defaults (ignored by git):

```bash
cat > scripts/manual-test/.env.local <<'EOF'
BASE_URL=https://<your-domain>
PSK=<your-psk>
EOF
```

`run.sh` loads this automatically if present.
`SID` is intentionally optional. `run.sh` and `api.sh` auto-select the current live controllable
session on each run when `SID` is unset or stale.

## Output Artifacts

Each `run.sh` execution writes:

- `artifacts/manual-test/wu34-<timestamp>/report.md`
- `artifacts/manual-test/wu34-<timestamp>/results.tsv`

Share `report.md` back for review/WORKLOG entry.
