#!/usr/bin/env python3
"""
Analyze Claude Code and Codex CLI session JSONL files for the vibecheck project.

Adapted from fsr4-rdna3-optimization/session-analysis methodology.
Adds date-range filtering and aggregate weekend summary statistics.

Usage:
    python3 analyze_sessions.py                          # weekend sessions, human-readable
    python3 analyze_sessions.py --json                   # machine-readable JSON
    python3 analyze_sessions.py --all-dates              # don't filter by date
    python3 analyze_sessions.py --date-from 2026-02-27   # custom date range
"""
import argparse
import json
import os
import sys
from datetime import datetime, date, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_duration(seconds):
    """Human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"


def format_tokens(n):
    """Human-readable token count."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def parse_ts(ts_str):
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def load_jsonl(filepath):
    """Load a JSONL file, skipping malformed lines."""
    entries = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


# ---------------------------------------------------------------------------
# Active / idle time analysis
# ---------------------------------------------------------------------------

def compute_activity(timestamps, idle_threshold=300):
    """
    Given a sorted list of datetimes, split wall time into active vs idle.

    A gap between consecutive events larger than idle_threshold seconds is
    considered idle time.  Returns a dict with active_seconds, idle_seconds,
    and a list of idle_gaps (start, end, gap_seconds).
    """
    if len(timestamps) < 2:
        return {"active_seconds": 0, "idle_seconds": 0, "idle_gaps": []}

    active = 0.0
    idle = 0.0
    gaps = []

    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if gap < idle_threshold:
            active += gap
        else:
            idle += gap
            gaps.append({
                "start": timestamps[i - 1].isoformat(),
                "end": timestamps[i].isoformat(),
                "seconds": gap,
            })

    return {"active_seconds": active, "idle_seconds": idle, "idle_gaps": gaps}


def compute_hourly_histogram(timestamps):
    """Return a dict of {hour_label: event_count}."""
    hist = {}
    for ts in timestamps:
        key = ts.strftime("%Y-%m-%d %H:00 UTC")
        hist[key] = hist.get(key, 0) + 1
    return dict(sorted(hist.items()))


# ---------------------------------------------------------------------------
# Date filtering
# ---------------------------------------------------------------------------

def session_in_date_range(result, date_from, date_to):
    """Check if a session's time span overlaps with the date range."""
    try:
        session_start = datetime.fromisoformat(result["start"]).date()
        session_end = datetime.fromisoformat(result["end"]).date()
    except (ValueError, KeyError):
        return False
    # Session overlaps if it starts before range ends AND ends after range starts
    return session_start <= date_to and session_end >= date_from


# ---------------------------------------------------------------------------
# Claude Code session parser
# ---------------------------------------------------------------------------

def analyze_claude_session(filepath, idle_threshold=300):
    """
    Parse a Claude Code JSONL session file.

    Entry types:
      - type: "user"      -> user turn, message.content has text
      - type: "assistant"  -> assistant turn, message.usage has token counts
      - type: "progress"   -> tool progress events
      - type: "system"     -> system events (hooks, etc.)
    """
    entries = load_jsonl(filepath)
    if not entries:
        return None

    user_turns = 0
    assistant_turns = 0
    total_input = 0
    total_output = 0
    total_cache_create = 0
    total_cache_read = 0
    first_user_msg = ""
    model = ""
    timestamps = []

    for entry in entries:
        ts_str = entry.get("timestamp")
        if ts_str:
            try:
                timestamps.append(parse_ts(ts_str))
            except (ValueError, TypeError):
                pass

        etype = entry.get("type", "")

        if etype == "user":
            user_turns += 1
            if not first_user_msg:
                msg = entry.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            first_user_msg = c["text"][:300]
                            break
                elif isinstance(content, str):
                    first_user_msg = content[:300]

        elif etype == "assistant":
            assistant_turns += 1
            msg = entry.get("message", {})
            if not model:
                model = msg.get("model", "")
            usage = msg.get("usage", {})
            if usage:
                total_input += usage.get("input_tokens", 0)
                total_output += usage.get("output_tokens", 0)
                total_cache_create += usage.get("cache_creation_input_tokens", 0)
                total_cache_read += usage.get("cache_read_input_tokens", 0)

    if not timestamps:
        return None

    timestamps.sort()
    start = timestamps[0]
    end = timestamps[-1]
    duration = (end - start).total_seconds()
    activity = compute_activity(timestamps, idle_threshold)

    return {
        "tool": "claude-code",
        "session_id": Path(filepath).stem,
        "file": os.path.basename(filepath),
        "project_dir": Path(filepath).parent.name,
        "model": model,
        "first_user_msg": first_user_msg,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "wall_seconds": duration,
        "active_seconds": activity["active_seconds"],
        "idle_seconds": activity["idle_seconds"],
        "idle_gaps": activity["idle_gaps"],
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "tokens": {
            "input": total_input,
            "output": total_output,
            "cache_create": total_cache_create,
            "cache_read": total_cache_read,
            "total_api": total_input + total_output + total_cache_create + total_cache_read,
        },
    }


# ---------------------------------------------------------------------------
# Codex CLI session parser
# ---------------------------------------------------------------------------

def analyze_codex_session(filepath, idle_threshold=300):
    """
    Parse a Codex CLI JSONL session file.

    Entry types:
      - type: "session_meta"   -> session metadata (cwd, model, cli_version)
      - type: "turn_context"   -> per-turn context (model, cwd, approval_policy)
      - type: "event_msg"      -> events (task_started/completed, token_count, etc.)
      - type: "response_item"  -> messages and function calls
      - type: "compacted"      -> compacted history with replacement_history array
    """
    entries = load_jsonl(filepath)
    if not entries:
        return None

    meta = {}
    timestamps = []
    last_token_usage = None
    turn_count = 0
    tool_calls = 0
    model = ""
    user_messages = []  # list of (timestamp, text)

    for entry in entries:
        ts_str = entry.get("timestamp")
        ts = None
        if ts_str:
            try:
                ts = parse_ts(ts_str)
                timestamps.append(ts)
            except (ValueError, TypeError):
                pass

        etype = entry.get("type", "")
        payload = entry.get("payload", {})

        if etype == "session_meta":
            meta = payload

        elif etype == "turn_context":
            turn_count += 1
            if not model:
                model = payload.get("model", "")

        elif etype == "event_msg":
            pt = payload.get("type", "")
            if pt == "token_count":
                info = payload.get("info")
                if info and "total_token_usage" in info:
                    last_token_usage = info["total_token_usage"]

        elif etype == "response_item":
            role = payload.get("role", "")
            item_type = payload.get("type", "")
            if role == "user":
                content = payload.get("content", [])
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "input_text":
                            text = c["text"]
                            # Skip system/developer instructions
                            if not text.startswith("#") and not text.startswith("<"):
                                user_messages.append((ts, text[:300]))
                            break
            elif item_type == "function_call":
                tool_calls += 1

        elif etype == "compacted":
            replacement = payload.get("replacement_history", [])
            for item in replacement:
                if isinstance(item, dict) and item.get("role") == "user":
                    content = item.get("content", [])
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "input_text":
                                text = c["text"]
                                if not text.startswith("#") and not text.startswith("<"):
                                    user_messages.append((ts, text[:300]))
                                break

    if not timestamps:
        return None

    timestamps.sort()
    start = timestamps[0]
    end = timestamps[-1]
    duration = (end - start).total_seconds()
    activity = compute_activity(timestamps, idle_threshold)
    hourly = compute_hourly_histogram(timestamps)

    cwd = meta.get("cwd", "")
    tokens = last_token_usage or {}

    # Deduplicate user messages (compacted replays produce duplicates)
    seen_texts = set()
    unique_messages = []
    for ts_val, text in user_messages:
        key = text[:80]
        if key not in seen_texts:
            seen_texts.add(key)
            unique_messages.append({
                "timestamp": ts_val.isoformat() if ts_val else None,
                "text": text,
            })

    return {
        "tool": "codex-cli",
        "session_id": meta.get("id", Path(filepath).stem),
        "file": os.path.basename(filepath),
        "cwd": cwd,
        "model": model,
        "cli_version": meta.get("cli_version", ""),
        "first_user_msg": unique_messages[0]["text"] if unique_messages else "",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "wall_seconds": duration,
        "active_seconds": activity["active_seconds"],
        "idle_seconds": activity["idle_seconds"],
        "idle_gaps": activity["idle_gaps"],
        "turns": turn_count,
        "unique_user_messages": len(unique_messages),
        "user_messages": unique_messages,
        "tool_calls": tool_calls,
        "hourly_events": hourly,
        "tokens": {
            "input": tokens.get("input_tokens", 0),
            "cached_input": tokens.get("cached_input_tokens", 0),
            "output": tokens.get("output_tokens", 0),
            "reasoning": tokens.get("reasoning_output_tokens", 0),
            "total": tokens.get("total_tokens", 0),
        },
        "total_events": len(entries),
    }


# ---------------------------------------------------------------------------
# Aggregate summary
# ---------------------------------------------------------------------------

def compute_aggregate(results):
    """Compute aggregate statistics across all sessions."""
    if not results:
        return None

    claude_sessions = [r for r in results if r["tool"] == "claude-code"]
    codex_sessions = [r for r in results if r["tool"] == "codex-cli"]

    # Time range
    all_starts = [datetime.fromisoformat(r["start"]) for r in results]
    all_ends = [datetime.fromisoformat(r["end"]) for r in results]
    earliest = min(all_starts)
    latest = max(all_ends)

    # Claude Code token totals
    cc_input = sum(r["tokens"]["input"] for r in claude_sessions)
    cc_output = sum(r["tokens"]["output"] for r in claude_sessions)
    cc_cache_create = sum(r["tokens"]["cache_create"] for r in claude_sessions)
    cc_cache_read = sum(r["tokens"]["cache_read"] for r in claude_sessions)
    cc_total = sum(r["tokens"]["total_api"] for r in claude_sessions)

    # Codex token totals
    cx_input = sum(r["tokens"]["input"] for r in codex_sessions)
    cx_cached = sum(r["tokens"]["cached_input"] for r in codex_sessions)
    cx_output = sum(r["tokens"]["output"] for r in codex_sessions)
    cx_reasoning = sum(r["tokens"]["reasoning"] for r in codex_sessions)
    cx_total = sum(r["tokens"]["total"] for r in codex_sessions)

    # Time totals
    total_wall = sum(r["wall_seconds"] for r in results)
    total_active = sum(r["active_seconds"] for r in results)

    # Turn/interaction totals
    cc_user_turns = sum(r["user_turns"] for r in claude_sessions)
    cc_assistant_turns = sum(r["assistant_turns"] for r in claude_sessions)
    cx_turns = sum(r["turns"] for r in codex_sessions)
    cx_tool_calls = sum(r["tool_calls"] for r in codex_sessions)
    cx_user_msgs = sum(r["unique_user_messages"] for r in codex_sessions)

    return {
        "time_range": {
            "earliest": earliest.isoformat(),
            "latest": latest.isoformat(),
        },
        "session_counts": {
            "total": len(results),
            "claude_code": len(claude_sessions),
            "codex_cli": len(codex_sessions),
        },
        "time": {
            "total_wall_seconds": total_wall,
            "total_active_seconds": total_active,
            "total_idle_seconds": total_wall - total_active,
        },
        "claude_code": {
            "user_turns": cc_user_turns,
            "assistant_turns": cc_assistant_turns,
            "tokens": {
                "input": cc_input,
                "output": cc_output,
                "cache_create": cc_cache_create,
                "cache_read": cc_cache_read,
                "total_api": cc_total,
            },
        },
        "codex_cli": {
            "turns": cx_turns,
            "unique_user_messages": cx_user_msgs,
            "tool_calls": cx_tool_calls,
            "tokens": {
                "input": cx_input,
                "cached_input": cx_cached,
                "output": cx_output,
                "reasoning": cx_reasoning,
                "total": cx_total,
            },
        },
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_claude_session(r):
    """Print a Claude Code session summary."""
    print(f"\n  Session:    {r['session_id'][:36]}")
    print(f"  Model:      {r['model']}")
    print(f"  First msg:  {r['first_user_msg'][:100]}...")
    print(f"  Time span:  {r['start'][:16]} -> {r['end'][11:16]} UTC")
    print(f"  Wall time:  {format_duration(r['wall_seconds'])}")
    print(f"  Active:     {format_duration(r['active_seconds'])} ({r['active_seconds'] / max(r['wall_seconds'], 1) * 100:.0f}%)")
    print(f"  Turns:      {r['user_turns']} user / {r['assistant_turns']} assistant")
    t = r["tokens"]
    print(f"  Tokens:     {format_tokens(t['input'])} input + {format_tokens(t['cache_create'])} cache-create + {format_tokens(t['cache_read'])} cache-read + {format_tokens(t['output'])} output")
    print(f"              = {format_tokens(t['total_api'])} total API tokens")
    if r["idle_gaps"]:
        print(f"  Idle gaps:  {len(r['idle_gaps'])}")
        for g in r["idle_gaps"]:
            print(f"              {g['start'][11:16]} -> {g['end'][11:16]} UTC ({format_duration(g['seconds'])})")


def print_codex_session(r):
    """Print a Codex CLI session summary."""
    print(f"\n  Session:    {r['session_id'][:36]}")
    print(f"  Model:      {r['model']} (CLI {r.get('cli_version', '?')})")
    print(f"  CWD:        {r['cwd']}")
    print(f"  First msg:  {r['first_user_msg'][:100]}...")
    print(f"  Time span:  {r['start'][:16]} -> {r['end'][:16]} UTC")
    print(f"  Wall time:  {format_duration(r['wall_seconds'])}")
    print(f"  Active:     {format_duration(r['active_seconds'])} ({r['active_seconds'] / max(r['wall_seconds'], 1) * 100:.0f}%)")
    print(f"  Turns:      {r['turns']} (turn contexts)")
    print(f"  User msgs:  {r['unique_user_messages']} unique")
    print(f"  Tool calls: {r['tool_calls']}")
    t = r["tokens"]
    if t["total"]:
        print(f"  Tokens:     {format_tokens(t['input'])} input ({format_tokens(t['cached_input'])} cached) + {format_tokens(t['output'])} output ({format_tokens(t['reasoning'])} reasoning)")
        print(f"              = {format_tokens(t['total'])} total")
    else:
        print(f"  Tokens:     (no token_count events)")
    print(f"  Events:     {r['total_events']}")

    if r["idle_gaps"]:
        print(f"  Idle gaps:  {len(r['idle_gaps'])}")
        for g in r["idle_gaps"]:
            print(f"              {g['start'][11:16]} -> {g['end'][11:16]} UTC ({format_duration(g['seconds'])})")

    if r["hourly_events"]:
        print(f"  Hourly events:")
        for hour, count in r["hourly_events"].items():
            bar = "#" * min(count // 20, 50)
            print(f"    {hour}: {bar} ({count})")


def print_aggregate(agg):
    """Print aggregate summary across all sessions."""
    print()
    print("=" * 80)
    print("AGGREGATE WEEKEND SUMMARY")
    print("=" * 80)

    tr = agg["time_range"]
    print(f"\n  Time range:     {tr['earliest'][:16]} -> {tr['latest'][:16]} UTC")

    sc = agg["session_counts"]
    print(f"  Sessions:       {sc['total']} total ({sc['claude_code']} Claude Code, {sc['codex_cli']} Codex)")

    t = agg["time"]
    print(f"\n  Total wall:     {format_duration(t['total_wall_seconds'])}")
    print(f"  Total active:   {format_duration(t['total_active_seconds'])} ({t['total_active_seconds'] / max(t['total_wall_seconds'], 1) * 100:.0f}%)")
    print(f"  Total idle:     {format_duration(t['total_idle_seconds'])}")

    if agg["session_counts"]["claude_code"] > 0:
        cc = agg["claude_code"]
        ct = cc["tokens"]
        print(f"\n  Claude Code:")
        print(f"    Turns:        {cc['user_turns']} user / {cc['assistant_turns']} assistant")
        print(f"    Tokens:       {format_tokens(ct['input'])} input + {format_tokens(ct['cache_create'])} cache-create + {format_tokens(ct['cache_read'])} cache-read + {format_tokens(ct['output'])} output")
        print(f"                  = {format_tokens(ct['total_api'])} total API tokens")

    if agg["session_counts"]["codex_cli"] > 0:
        cx = agg["codex_cli"]
        xt = cx["tokens"]
        print(f"\n  Codex CLI:")
        print(f"    Turns:        {cx['turns']} turn contexts, {cx['unique_user_messages']} user messages")
        print(f"    Tool calls:   {cx['tool_calls']}")
        print(f"    Tokens:       {format_tokens(xt['input'])} input ({format_tokens(xt['cached_input'])} cached) + {format_tokens(xt['output'])} output ({format_tokens(xt['reasoning'])} reasoning)")
        print(f"                  = {format_tokens(xt['total'])} total")

    # Combined totals
    cc_total = agg["claude_code"]["tokens"]["total_api"]
    cx_total = agg["codex_cli"]["tokens"]["total"]
    grand_total = cc_total + cx_total
    print(f"\n  Grand total tokens (both tools): {format_tokens(grand_total)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze Claude Code and Codex CLI session data for vibecheck weekend work."
    )
    parser.add_argument(
        "--claude-dir",
        default=os.path.expanduser("~/.claude/projects"),
        help="Claude Code projects directory (default: ~/.claude/projects)",
    )
    parser.add_argument(
        "--codex-dir",
        default=os.path.expanduser("~/.codex"),
        help="Codex CLI base directory (default: ~/.codex)",
    )
    parser.add_argument(
        "--project-filter",
        default="vibecheck",
        help="Only show sessions whose path/cwd contains this substring (default: vibecheck)",
    )
    parser.add_argument(
        "--date-from",
        default="2026-02-28",
        help="Start date for filtering sessions (default: 2026-02-28, Saturday)",
    )
    parser.add_argument(
        "--date-to",
        default="2026-03-01",
        help="End date for filtering sessions (default: 2026-03-01, Sunday)",
    )
    parser.add_argument(
        "--all-dates",
        action="store_true",
        help="Disable date filtering, show all matching sessions",
    )
    parser.add_argument(
        "--idle-threshold",
        type=int,
        default=300,
        help="Seconds of inactivity before a gap is considered idle (default: 300)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output machine-readable JSON instead of human-readable text",
    )
    parser.add_argument(
        "--no-aggregate",
        action="store_true",
        help="Skip aggregate summary (only show per-session details)",
    )
    args = parser.parse_args()

    # Parse date range
    date_from = date.fromisoformat(args.date_from)
    date_to = date.fromisoformat(args.date_to)

    all_results = []

    # --- Claude Code sessions ---
    claude_base = Path(args.claude_dir)
    if claude_base.exists():
        for project_dir in sorted(claude_base.iterdir()):
            if not project_dir.is_dir():
                continue
            if args.project_filter and args.project_filter not in str(project_dir):
                continue
            for f in sorted(project_dir.glob("*.jsonl")):
                r = analyze_claude_session(f, args.idle_threshold)
                if r and r["user_turns"] > 0:
                    if not args.all_dates and not session_in_date_range(r, date_from, date_to):
                        continue
                    all_results.append(r)

    # --- Codex CLI sessions ---
    codex_sessions_dir = Path(args.codex_dir) / "sessions"
    if codex_sessions_dir.exists():
        for f in sorted(codex_sessions_dir.rglob("rollout-*.jsonl")):
            r = analyze_codex_session(f, args.idle_threshold)
            if not r:
                continue
            if r["wall_seconds"] < 10 and r["tokens"]["total"] == 0:
                continue  # skip trivial/empty
            if args.project_filter and args.project_filter not in r.get("cwd", ""):
                continue
            if not args.all_dates and not session_in_date_range(r, date_from, date_to):
                continue
            all_results.append(r)

    # Sort all results by start time
    all_results.sort(key=lambda r: r["start"])

    # --- Output ---
    if args.json_output:
        output = {
            "sessions": all_results,
            "aggregate": compute_aggregate(all_results),
            "filters": {
                "project": args.project_filter,
                "date_from": args.date_from if not args.all_dates else None,
                "date_to": args.date_to if not args.all_dates else None,
            },
        }
        print(json.dumps(output, indent=2, default=str))
        return

    # Header
    print("=" * 80)
    if args.all_dates:
        print(f"VIBECHECK SESSION ANALYSIS (all dates)")
    else:
        print(f"VIBECHECK WEEKEND SESSION ANALYSIS ({args.date_from} to {args.date_to})")
    print(f"Project filter: '{args.project_filter}'")
    print("=" * 80)

    claude_sessions = [r for r in all_results if r["tool"] == "claude-code"]
    codex_sessions_list = [r for r in all_results if r["tool"] == "codex-cli"]

    if claude_sessions:
        print()
        print("-" * 80)
        print(f"CLAUDE CODE SESSIONS ({len(claude_sessions)})")
        print("-" * 80)
        for r in claude_sessions:
            print_claude_session(r)

    if codex_sessions_list:
        print()
        print("-" * 80)
        print(f"CODEX CLI SESSIONS ({len(codex_sessions_list)})")
        print("-" * 80)
        for r in codex_sessions_list:
            print_codex_session(r)

    if not all_results:
        print("\nNo sessions found.")
        if args.project_filter:
            print(f"  Project filter: '{args.project_filter}'")
        if not args.all_dates:
            print(f"  Date range: {args.date_from} to {args.date_to}")
        print("\nTry --all-dates to see all sessions, or adjust --project-filter.")
        return

    # Aggregate summary
    if not args.no_aggregate:
        agg = compute_aggregate(all_results)
        if agg:
            print_aggregate(agg)


if __name__ == "__main__":
    main()
