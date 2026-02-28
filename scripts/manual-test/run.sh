#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$ROOT_DIR/scripts/manual-test"
API_SH="$SCRIPT_DIR/api.sh"
TUI_SH="$SCRIPT_DIR/tui_prompts.sh"
ENV_FILE="$SCRIPT_DIR/.env.local"

BASE_URL="${BASE_URL:-}"
PSK="${PSK:-}"
SID="${SID:-${SESSION_ID:-}}"
RUN_DIR="${RUN_DIR:-}"

ARTIFACTS_ROOT="$ROOT_DIR/artifacts/manual-test"
timestamp="$(date +%Y%m%d-%H%M%S)"
if [[ -z "$RUN_DIR" ]]; then
  RUN_DIR="$ARTIFACTS_ROOT/wu34-$timestamp"
fi
RESULTS_TSV="$RUN_DIR/results.tsv"
REPORT_MD="$RUN_DIR/report.md"

usage() {
  cat <<'EOF'
Usage: run.sh [options]

Options:
  --base-url URL        Base URL (e.g. https://vibecheck.example.com)
  --psk VALUE           PSK value for X-PSK
  --sid SESSION_ID      Session ID to validate
  --run-dir PATH        Output directory for artifacts
  --save-env            Save entered BASE_URL/PSK (and SID only with --save-sid) to scripts/manual-test/.env.local
  --save-sid            Persist SID when used with --save-env
  --help, -h            Show help

Default behavior:
  Interactive WU-34 checklist runner:
  - guides TUI/phone actions
  - polls API state transitions
  - asks explicit acceptance checks
  - writes report.md + results.tsv
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing dependency: $1" >&2
    exit 1
  }
}

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1091
  source "$ENV_FILE"
fi

save_env=false
save_sid=false
sid_explicit=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --psk)
      PSK="${2:-}"
      shift 2
      ;;
    --sid)
      SID="${2:-}"
      sid_explicit=true
      shift 2
      ;;
    --run-dir)
      RUN_DIR="${2:-}"
      RESULTS_TSV="$RUN_DIR/results.tsv"
      REPORT_MD="$RUN_DIR/report.md"
      shift 2
      ;;
    --save-env)
      save_env=true
      shift
      ;;
    --save-sid)
      save_sid=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmd jq
require_cmd curl
require_cmd uv

api() {
  BASE_URL="$BASE_URL" PSK="$PSK" SID="$SID" "$API_SH" "$@"
}

prompt_if_empty() {
  local var_name="$1"
  local prompt="$2"
  local hidden="${3:-false}"
  local current_value="${!var_name}"
  if [[ -n "$current_value" ]]; then
    return
  fi

  if [[ "$hidden" == "true" ]]; then
    local value
    read -r -s -p "$prompt" value
    echo
    printf -v "$var_name" '%s' "$value"
  else
    local value
    read -r -p "$prompt" value
    printf -v "$var_name" '%s' "$value"
  fi
}

ask_yes_no() {
  local prompt="$1"
  local default="${2:-y}"
  local answer

  while true; do
    if [[ "$default" == "y" ]]; then
      read -r -p "$prompt [Y/n]: " answer
      answer="${answer:-y}"
    else
      read -r -p "$prompt [y/N]: " answer
      answer="${answer:-n}"
    fi
    case "$answer" in
      y|Y|yes|YES)
        return 0
        ;;
      n|N|no|NO)
        return 1
        ;;
      *)
        echo "Please answer y or n."
        ;;
    esac
  done
}

wait_for_enter() {
  local message="$1"
  local response
  echo
  read -r -p "$message (Enter=continue, q=abort) " response
  case "$response" in
    q|Q|quit|QUIT|exit|EXIT)
      echo
      echo "Manual run aborted by operator."
      append_result "RUN_ABORTED" "ABORT" "operator_exit"
      build_report || true
      echo "Partial report: $REPORT_MD"
      exit 130
      ;;
    *)
      ;;
  esac
}

wait_for_pending_clear() {
  local kind="$1"
  local timeout="${2:-180}"
  local interval=1
  local elapsed=0
  local pending_id=""
  local key=""

  while (( elapsed < timeout )); do
    if [[ "$kind" == "approval" ]]; then
      pending_id="$(api call-id 2>/dev/null || true)"
    else
      pending_id="$(api request-id 2>/dev/null || true)"
    fi

    if [[ -z "$pending_id" ]]; then
      echo "Pending $kind cleared (${elapsed}s)."
      return 0
    fi

    if (( elapsed == 0 || elapsed % 5 == 0 )); then
      echo "Waiting for pending $kind to clear... ${elapsed}s (id=$pending_id)"
      echo "Press q then Enter to abort wait."
    fi

    if read -r -t "$interval" key; then
      case "$key" in
        q|Q|quit|QUIT|exit|EXIT)
          echo "Aborted while waiting for pending $kind clear."
          append_result "RUN_ABORTED" "ABORT" "operator_exit_during_wait"
          build_report || true
          echo "Partial report: $REPORT_MD"
          exit 130
          ;;
        *)
          ;;
      esac
    fi

    ((elapsed += interval))
  done

  echo "Timed out waiting for pending $kind to clear after ${timeout}s."
  return 1
}

append_result() {
  local key="$1"
  local status="$2"
  local notes="$3"
  printf "%s\t%s\t%s\n" "$key" "$status" "$notes" >>"$RESULTS_TSV"
}

check_health() {
  curl -fsS "$BASE_URL/api/health" >/dev/null
}

discover_sid() {
  local discovered
  discovered="$(BASE_URL="$BASE_URL" PSK="$PSK" "$API_SH" selected-sid 2>/dev/null || true)"
  if [[ -n "$discovered" ]]; then
    SID="$discovered"
  fi
}

is_sid_live_controllable() {
  local sid="$1"
  local payload
  payload="$(BASE_URL="$BASE_URL" PSK="$PSK" SID="$sid" "$API_SH" state 2>/dev/null || true)"
  if [[ -z "$payload" ]]; then
    return 1
  fi
  [[ "$(jq -r '.attach_mode // empty' <<<"$payload")" == "live" ]] && \
    [[ "$(jq -r '.controllable // false' <<<"$payload")" == "true" ]]
}

scenario_remote_approve() {
  local key="S1_REMOTE_APPROVE"
  local notes=()
  local call_id=""

  echo
  echo "=== Scenario 1: Remote Approve ==="
  "$TUI_SH" approve
  echo
  echo "Expected:"
  echo "- Pending approval appears on phone."
  echo "- After phone approve, terminal returns to input mode."
  wait_for_enter "Submit the prompt in TUI now"

  if ! call_id="$(api wait-pending-approval 180 2>/dev/null)"; then
    append_result "$key" "FAIL" "No pending approval detected within timeout"
    return
  fi
  notes+=("call_id=$call_id")
  echo "Detected pending approval: $call_id"

  wait_for_enter "Approve this request from phone"
  if ! wait_for_pending_clear approval 180; then
    append_result "$key" "FAIL" "Approval did not clear after phone action; ${notes[*]}"
    return
  fi

  if ask_yes_no "Did agent continue after approval?" y && \
     ask_yes_no "Did terminal bottom app return to input (approval/question widget gone)?" y; then
    append_result "$key" "PASS" "${notes[*]}"
  else
    append_result "$key" "FAIL" "Agent/UI behavior mismatch; ${notes[*]}"
  fi
}

scenario_remote_reject() {
  local key="S2_REMOTE_REJECT"
  local notes=()
  local call_id=""

  echo
  echo "=== Scenario 2: Remote Reject ==="
  "$TUI_SH" reject
  echo
  echo "Expected:"
  echo "- Pending approval appears on phone."
  echo "- After phone reject, terminal returns to input mode."
  wait_for_enter "Submit the prompt in TUI now"

  if ! call_id="$(api wait-pending-approval 180 2>/dev/null)"; then
    append_result "$key" "FAIL" "No pending approval detected within timeout"
    return
  fi
  notes+=("call_id=$call_id")
  echo "Detected pending approval: $call_id"

  wait_for_enter "Reject this request from phone"
  if ! wait_for_pending_clear approval 180; then
    append_result "$key" "FAIL" "Approval did not clear after phone reject; ${notes[*]}"
    return
  fi

  if ask_yes_no "Did terminal bottom app return to input mode?" y; then
    append_result "$key" "PASS" "${notes[*]}"
  else
    append_result "$key" "FAIL" "UI did not return to input mode; ${notes[*]}"
  fi
}

scenario_remote_question_answer() {
  local key="S3_REMOTE_QUESTION_ANSWER"
  local notes=()
  local request_id=""

  echo
  echo "=== Scenario 3: Remote Question Answer ==="
  "$TUI_SH" question
  echo
  echo "Expected:"
  echo "- Pending input appears on phone."
  echo "- After phone answer, terminal returns to input mode."
  wait_for_enter "Submit the prompt in TUI now"

  if ! request_id="$(api wait-pending-input 180 2>/dev/null)"; then
    append_result "$key" "FAIL" "No pending input detected within timeout"
    return
  fi
  notes+=("request_id=$request_id")
  echo "Detected pending input: $request_id"

  wait_for_enter "Answer this question from phone"
  if ! wait_for_pending_clear input 180; then
    append_result "$key" "FAIL" "Pending input did not clear after phone answer; ${notes[*]}"
    return
  fi

  if ask_yes_no "Did terminal bottom app return to input mode?" y; then
    append_result "$key" "PASS" "${notes[*]}"
  else
    append_result "$key" "FAIL" "UI did not return to input mode; ${notes[*]}"
  fi
}

scenario_first_wins_race() {
  local key="S4_FIRST_RESPONSE_WINS"
  local notes=()
  local call_id=""

  echo
  echo "=== Scenario 4: First-Response-Wins Race ==="
  "$TUI_SH" race
  echo
  echo "Expected:"
  echo "- Phone and keyboard resolve nearly simultaneously."
  echo "- Exactly one decision wins."
  echo "- Terminal returns to input mode."
  wait_for_enter "Submit the prompt in TUI now"

  if ! call_id="$(api wait-pending-approval 180 2>/dev/null)"; then
    append_result "$key" "FAIL" "No pending approval detected within timeout"
    return
  fi
  notes+=("call_id=$call_id")
  echo "Detected pending approval: $call_id"

  wait_for_enter "Resolve simultaneously on keyboard + phone now"
  if ! wait_for_pending_clear approval 180; then
    append_result "$key" "FAIL" "Approval did not clear after race action; ${notes[*]}"
    return
  fi

  if ask_yes_no "Did exactly one decision win (no double-resolve behavior)?" y && \
     ask_yes_no "Did terminal return to input mode?" y; then
    append_result "$key" "PASS" "${notes[*]}"
  else
    append_result "$key" "FAIL" "Race behavior/UI did not meet criteria; ${notes[*]}"
  fi
}

scenario_reconnect_pending() {
  local key="S5_RECONNECT_PENDING"
  local notes=()
  local call_id=""

  echo
  echo "=== Scenario 5: Coffee-Walk Reconnect ==="
  "$TUI_SH" reconnect
  echo
  echo "Expected:"
  echo "- Approval pending survives phone disconnect/reconnect."
  echo "- Resolve after reconnect succeeds."
  wait_for_enter "Submit the prompt in TUI now"

  if ! call_id="$(api wait-pending-approval 180 2>/dev/null)"; then
    append_result "$key" "FAIL" "No pending approval detected within timeout"
    return
  fi
  notes+=("call_id=$call_id")
  echo "Detected pending approval: $call_id"

  wait_for_enter "Disconnect/close phone PWA now"
  wait_for_enter "Reconnect phone PWA and reopen same session"

  if ask_yes_no "After reconnect, was pending approval visible on phone?" y; then
    notes+=("pending_visible_on_reconnect=yes")
  else
    notes+=("pending_visible_on_reconnect=no")
  fi

  wait_for_enter "Resolve approval from phone now"
  if ! wait_for_pending_clear approval 180; then
    append_result "$key" "FAIL" "Approval did not clear after reconnect resolve; ${notes[*]}"
    return
  fi

  if [[ "${notes[*]}" == *"pending_visible_on_reconnect=yes"* ]] && \
     ask_yes_no "Did terminal return to input mode?" y; then
    append_result "$key" "PASS" "${notes[*]}"
  else
    append_result "$key" "FAIL" "Reconnect criteria failed; ${notes[*]}"
  fi
}

scenario_gap2_visibility() {
  local key="S6_GAP2_VISIBILITY"
  local notes=()

  echo
  echo "=== Scenario 6: Gap 2 (Phone Prompt Visibility) ==="
  echo "Action:"
  echo "- Send a new message from phone input only."
  echo "- Observe phone + terminal."
  echo
  echo "Expected:"
  echo "- Phone always shows full thread."
  echo "- Terminal shows the phone-originated user bubble."

  wait_for_enter "Send a phone-originated message now"

  if ask_yes_no "Did phone show the message and subsequent agent activity?" y; then
    notes+=("phone_thread_ok=yes")
  else
    notes+=("phone_thread_ok=no")
  fi

  if ask_yes_no "Was the phone-originated user bubble visible in terminal?" y; then
    notes+=("terminal_user_bubble=yes")
  else
    notes+=("terminal_user_bubble=no")
  fi

  if [[ "${notes[*]}" == *"phone_thread_ok=yes"* && "${notes[*]}" == *"terminal_user_bubble=yes"* ]]; then
    append_result "$key" "PASS" "${notes[*]}"
  else
    append_result "$key" "FAIL" "${notes[*]}"
  fi
}

scenario_gap3_usability() {
  local key="S7_GAP3_USABILITY"
  local notes=()

  echo
  echo "=== Scenario 7: Gap 3 (Lifecycle Usability) ==="
  "$TUI_SH" running
  echo
  echo "Expected:"
  echo "- Agent appears visibly running somehow (events/tool output streaming)."
  echo "- Terminal input/interrupt actions do not wedge the loop."
  wait_for_enter "Run the prompt in TUI now"

  if ask_yes_no "Was there a clear visible running signal (streaming output/progress)?" y; then
    notes+=("running_signal=yes")
  else
    notes+=("running_signal=no")
  fi

  if ask_yes_no "Did local typing/interrupt attempts avoid wedging the loop?" y; then
    notes+=("no_wedge=yes")
  else
    notes+=("no_wedge=no")
  fi

  if [[ "${notes[*]}" == *"running_signal=yes"* && "${notes[*]}" == *"no_wedge=yes"* ]]; then
    append_result "$key" "PASS" "${notes[*]}"
  else
    append_result "$key" "FAIL" "${notes[*]}"
  fi
}

build_report() {
  local commit_hash vibe_version overall required_failed version_raw
  commit_hash="$(cd "$ROOT_DIR" && git rev-parse --short HEAD 2>/dev/null)"
  if [[ -z "$commit_hash" ]]; then
    commit_hash="unknown"
  fi

  vibe_version="unknown"
  if version_raw="$(cd "$ROOT_DIR" && uv run python -c 'import importlib.metadata as md
items=[]
for name in ("'"'"'vibe'"'"'","'"'"'mistral-vibe'"'"'"):
    try:
        items.append(f"{name}={md.version(name)}")
    except Exception:
        pass
print(", ".join(items) if items else "unknown")' 2>/dev/null)"; then
    if [[ -n "$version_raw" ]]; then
      vibe_version="$version_raw"
    fi
  fi
  if [[ -z "$vibe_version" ]]; then
    vibe_version="unknown"
  fi

  required_failed=0
  while IFS=$'\t' read -r key status _notes; do
    case "$key" in
      S1_REMOTE_APPROVE|S2_REMOTE_REJECT|S3_REMOTE_QUESTION_ANSWER|S4_FIRST_RESPONSE_WINS|S5_RECONNECT_PENDING|S7_GAP3_USABILITY)
        if [[ "$status" != "PASS" ]]; then
          required_failed=1
        fi
        ;;
      *)
        ;;
    esac
  done <"$RESULTS_TSV"

  if [[ "$required_failed" -eq 0 ]]; then
    overall="PASS"
  else
    overall="FAIL"
  fi

  {
    echo "# WU-34 Manual Validation Report"
    echo
    echo "- Timestamp: $(date -u +"%Y-%m-%d %H:%M:%SZ")"
    echo "- Base URL: $BASE_URL"
    echo "- Session ID: $SID"
    echo "- Commit: $commit_hash"
    echo "- Vibe version: $vibe_version"
    echo "- Overall: $overall"
    echo
    echo "| Scenario | Status | Notes |"
    echo "|---|---|---|"
    while IFS=$'\t' read -r key status notes; do
      printf "| %s | %s | %s |\n" "$key" "$status" "${notes//|/\\/}"
    done <"$RESULTS_TSV"
    echo
    echo "## Pasteback Summary"
    echo
    echo '```'
    echo "overall=$overall"
    while IFS=$'\t' read -r key status notes; do
      echo "$key=$status ; $notes"
    done <"$RESULTS_TSV"
    echo '```'
  } >"$REPORT_MD"
}

mkdir -p "$RUN_DIR"
: >"$RESULTS_TSV"

prompt_if_empty BASE_URL "Base URL (e.g. https://vibecheck.example.com): "
prompt_if_empty PSK "PSK (hidden input): " true

sid_live=false
if [[ -z "$SID" ]]; then
  echo "Discovering live session ID..."
  discover_sid
else
  if ! is_sid_live_controllable "$SID"; then
    if [[ "$sid_explicit" == "true" ]]; then
      echo "Provided --sid is not currently live/controllable: $SID" >&2
    else
      echo "Saved SID is stale/non-live: $SID"
      echo "Discovering active live session ID..."
      discover_sid
    fi
  fi
fi

if [[ -n "$SID" ]] && is_sid_live_controllable "$SID"; then
  sid_live=true
fi

if [[ -z "$SID" || "$sid_live" != "true" ]]; then
  echo "Could not auto-select a live controllable session."
  BASE_URL="$BASE_URL" PSK="$PSK" "$API_SH" sessions || true
  prompt_if_empty SID "Session ID (SID) to test: "
  if ! is_sid_live_controllable "$SID"; then
    echo "Selected SID is not live/controllable: $SID" >&2
    exit 1
  fi
fi

if [[ "$save_env" == "true" ]]; then
  {
    echo "BASE_URL=$BASE_URL"
    echo "PSK=$PSK"
    if [[ "$save_sid" == "true" ]]; then
      echo "SID=$SID"
    fi
  } >"$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Saved defaults to $ENV_FILE"
fi

echo
echo "== Preflight =="
echo "Base URL: $BASE_URL"
echo "Session:  $SID"
echo "Run dir:  $RUN_DIR"
sid_encoded="$(printf '%s' "$SID" | jq -sRr @uri)"
psk_encoded="$(printf '%s' "$PSK" | jq -sRr @uri)"
echo "Phone debug URL: ${BASE_URL%/}/?debug=1&sid=$sid_encoded"
echo "Phone connect URL: ${BASE_URL%/}/?debug=1&sid=$sid_encoded&psk=$psk_encoded"
echo
echo "Phone session target: $SID"
echo "If your phone UI has a session switcher, select this exact session ID."
echo "If your phone UI has no switcher, refresh it now and verify pending prompts appear during Scenario 1."
echo
echo "Session snapshot:"
BASE_URL="$BASE_URL" PSK="$PSK" "$API_SH" sessions | jq -r '.[] | "- id=\(.id) mode=\(.attach_mode // "unknown") controllable=\(.controllable // false) status=\(.status // "unknown")"' || true

if ! check_health; then
  echo "Health check failed at $BASE_URL/api/health" >&2
  exit 1
fi
echo "Health check: ok"

if ! api state >/dev/null 2>&1; then
  echo "Could not read session state for SID=$SID. Check session and auth." >&2
  BASE_URL="$BASE_URL" PSK="$PSK" "$API_SH" sessions || true
  exit 1
fi
echo "Session state lookup: ok"

echo "WebSocket probe (session-scoped):"
if ! ws_probe_json="$(api ws-check 8 2>&1)"; then
  echo "WebSocket probe failed for SID=$SID." >&2
  echo "$ws_probe_json" >&2
  echo "Check Caddy WS proxy + SID alignment, then retry." >&2
  exit 1
fi
echo "$ws_probe_json" | jq -r '"WS ok: sid=\(.session_id) state=\(.state) mode=\(.attach_mode // "unknown") controllable=\(.controllable // false)"'

wait_for_enter "Confirm TUI is running in Terminal A and phone PWA is connected"

scenario_remote_approve
scenario_remote_reject
scenario_remote_question_answer
scenario_first_wins_race
scenario_reconnect_pending
scenario_gap2_visibility
scenario_gap3_usability

build_report

echo
echo "Manual validation run complete."
echo "Results TSV: $RESULTS_TSV"
echo "Report MD:   $REPORT_MD"
echo
echo "Send me the report path or paste the 'Pasteback Summary' block."
