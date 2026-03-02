# Vibecheck Weekend Session Analysis

Analysis of AI coding assistant session data from the vibecheck hackathon weekend (Feb 28 - Mar 1, 2026), using both Claude Code and OpenAI Codex CLI.

Adapted from the [fsr4-rdna3-optimization session analysis methodology](../fsr4-rdna3-optimization/session-analysis/).

## Weekend Summary

| Metric | Value |
|---|---|
| **Time range** | Feb 28 09:21 -> Mar 1 16:14 JST (~31h span) |
| **Total sessions** | 69 (32 Claude Code, 37 Codex CLI) |
| **Saturday sessions** | 47 |
| **Sunday sessions** | 22 |
| **Total wall time** | 68h 56m (sum of all sessions, many overlapping) |
| **Total active time** | 27h 42m (40% of wall time) |
| **Grand total tokens** | **727.02M** (both tools combined) |

## Tool Breakdown

### Claude Code (32 sessions)

| Metric | Value |
|---|---|
| **Model** | claude-opus-4-6 |
| **User turns** | 2,183 |
| **Assistant turns** | 3,281 |
| **Input tokens** | 804.1K |
| **Cache-create tokens** | 25.93M |
| **Cache-read tokens** | 260.30M |
| **Output tokens** | 669.4K |
| **Total API tokens** | 287.71M |

Claude Code sessions were used as the primary interactive development environment. The token profile is dominated by cache reads (260M of 288M total), meaning most API cost was served from Anthropic's prompt cache at reduced rates. Actual fresh input was only ~804K tokens with ~669K output.

### Codex CLI (37 sessions)

| Metric | Value |
|---|---|
| **Models** | gpt-5.2, gpt-5.3-codex |
| **Turn contexts** | 4,567 |
| **Unique user messages** | 216 |
| **Tool calls** | 5,086 |
| **Input tokens** | 436.96M (422.82M cached) |
| **Output tokens** | 2.35M (1.66M reasoning) |
| **Total tokens** | 439.31M |

Codex sessions were used heavily for autonomous coding tasks (work units from the implementation plan) and multi-agent review workflows. Several sessions used a "Reviewer 1/2/3" pattern where Codex reviewed code changes after a primary coding agent completed work.

## Workflow Patterns Observed

### Multi-Agent Collaboration
Sessions show a clear pattern of Claude Code for orchestration/planning and Codex CLI for execution:
- Claude Code: project setup, architecture decisions, debugging, interactive Q&A
- Codex CLI: autonomous work unit execution, code review (multiple reviewer agents), feature implementation

### Saturday (47 sessions) - Build Day
The bulk of development happened Saturday, starting mid-morning JST:
- **09:21-11:02**: Project initialization, README setup, architecture planning (Claude Code)
- **11:00-19:00**: Core feature implementation (WebSocket bridge, PWA frontend, Mistral Vibe integration)
- **19:00-03:00**: Continued feature work (settings, session management, cost ticker)
- **03:00-08:59**: Advanced features (push notifications, YOLO mode), multi-reviewer code reviews

### Sunday (22 sessions) - Polish & Features
Sunday focused on polish and additional features:
- **10:00-14:00**: Cancel state, viewport fixes, settings refinements, camera/vision upload, YOLO mode
- **14:00-16:14**: Documentation, README generation, final cleanup

### Session Intensity
- Longest sessions: Several 1-2+ hour sessions with 100+ turn contexts
- Most concurrent: Peak activity around 07:00-08:00 JST Sunday with multiple overlapping Codex sessions (coder + reviewers)
- Shortest meaningful sessions: Quick 1-5 minute Codex review tasks

## Files in This Directory

| File | Description |
|---|---|
| `analyze_sessions.py` | Analysis script (adapted from fsr4 methodology, adds date filtering + aggregation) |
| `weekend-report.txt` | Full human-readable session-by-session report |
| `weekend-sessions.json` | Machine-readable JSON with all session data + aggregate stats |
| `README.md` | This writeup |

## Usage

```bash
# Default: vibecheck weekend sessions (Sat-Sun)
python3 analyze_sessions.py

# JSON output for downstream processing
python3 analyze_sessions.py --json

# All vibecheck sessions (no date filter)
python3 analyze_sessions.py --all-dates

# Custom date range
python3 analyze_sessions.py --date-from 2026-02-28 --date-to 2026-02-28  # Saturday only

# Pipe JSON to jq
python3 analyze_sessions.py --json | jq '.aggregate'
python3 analyze_sessions.py --json | jq '.sessions[] | {tool, session_id: .session_id[:12], wall: .wall_seconds, active: .active_seconds}'

# Get all user messages from Codex sessions
python3 analyze_sessions.py --json | jq '.sessions[] | select(.tool == "codex-cli") | .user_messages[]? | .text'
```

## Notes on Data Interpretation

- **Cache-dominated token counts**: Both tools show cache tokens as the majority of API usage. Claude Code's 260M cache-read tokens and Codex's 422M cached input tokens reflect prompt caching, not fresh computation. Actual "novel" token processing was much lower.

- **Overlapping sessions**: Wall time sums to 69h across a 31h span because multiple sessions ran concurrently (especially during multi-reviewer patterns). Active time (28h) is a better measure of actual compute engagement.

- **Codex cumulative tokens**: Codex reports running totals per session. The script takes the final value, so per-session token counts represent the session total, not incremental.

- **Turn counts**: Claude Code's 2,183 user turns includes interactive back-and-forth. Codex's 4,567 turn contexts includes internal model-to-tool cycles, which is why it's higher despite fewer unique user messages (216).
