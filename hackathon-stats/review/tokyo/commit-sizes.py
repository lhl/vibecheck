#!/usr/bin/env python3
"""Collect per-commit diff stats and analyze commit size patterns."""

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Vendored/generated directories to exclude from diff stats
EXCLUDE_PATHS = {
    "node_modules", "vendor", ".venv", "venv", "__pycache__", "dist",
    "build", ".next", ".nuxt", ".expo", ".angular", ".svelte-kit",
    "bower_components", "wandb", "coverage", ".tox", ".eggs",
    "site-packages", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


def run(cmd, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def _is_vendored(path):
    """Check if a file path is in a vendored/generated directory."""
    parts = path.split("/")
    return any(p in EXCLUDE_PATHS for p in parts)


def get_commit_stats(project_dir):
    """Get per-commit diff stats in chronological order (oldest first).

    Uses --numstat so we can filter out vendored paths per-file.
    """
    raw = run(
        ["git", "log", "--reverse", "--numstat",
         "--format=%x01%H%x00%an%x00%ae%x00%aI%x00%s"],
        cwd=project_dir,
    )
    if not raw:
        return []

    commits = []
    for block in raw.split("\x01"):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        header = lines[0]
        parts = header.split("\x00")
        if len(parts) < 5:
            continue

        insertions = 0
        deletions = 0
        files_changed = 0
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) < 3:
                continue
            filepath = fields[2]
            if _is_vendored(filepath):
                continue
            # Binary files show as "-"
            added = int(fields[0]) if fields[0] != "-" else 0
            removed = int(fields[1]) if fields[1] != "-" else 0
            insertions += added
            deletions += removed
            files_changed += 1

        commits.append({
            "hash": parts[0],
            "author_name": parts[1],
            "author_email": parts[2],
            "date": parts[3],
            "subject": parts[4],
            "files_changed": files_changed,
            "insertions": insertions,
            "deletions": deletions,
            "net_lines": insertions - deletions,
        })

    return commits


def analyze_project(name, commits):
    """Analyze commit patterns for a single project."""
    if not commits:
        return None

    total_insertions = sum(c["insertions"] for c in commits)
    sizes = [c["insertions"] for c in commits]
    median_size = sorted(sizes)[len(sizes) // 2] if sizes else 0

    first = commits[0]
    last = commits[-1] if len(commits) > 1 else None

    # What fraction of total code was in the first commit?
    first_pct = (first["insertions"] / total_insertions * 100) if total_insertions else 0

    # What fraction was in the last commit?
    last_pct = (last["insertions"] / total_insertions * 100) if last and total_insertions else 0

    # Largest commit
    largest = max(commits, key=lambda c: c["insertions"])
    largest_idx = commits.index(largest)
    largest_pct = (largest["insertions"] / total_insertions * 100) if total_insertions else 0

    # Classify the pattern
    flags = []
    if first_pct > 40 and len(commits) > 3:
        flags.append("large_initial_commit")
    if last and last_pct > 40 and len(commits) > 3:
        flags.append("large_final_commit")
    if largest_idx > 0 and largest_idx < len(commits) - 1 and largest_pct > 40:
        flags.append("large_mid_commit")
    if first_pct > 40 and len(commits) > 5:
        # Large initial + many follow-ups = likely started from existing code
        flags.append("possible_existing_codebase")
    if last and last_pct > 40 and len(commits) <= 5:
        flags.append("poor_version_control")

    return {
        "project": name,
        "num_commits": len(commits),
        "total_insertions": total_insertions,
        "median_commit_size": median_size,
        "first_commit": {
            "date": first["date"],
            "insertions": first["insertions"],
            "pct_of_total": round(first_pct, 1),
            "subject": first["subject"],
        },
        "last_commit": {
            "date": last["date"],
            "insertions": last["insertions"],
            "pct_of_total": round(last_pct, 1),
            "subject": last["subject"],
        } if last else None,
        "largest_commit": {
            "index": largest_idx,
            "of_total": len(commits),
            "date": largest["date"],
            "insertions": largest["insertions"],
            "pct_of_total": round(largest_pct, 1),
            "subject": largest["subject"],
        },
        "flags": flags,
        "commits": commits,
    }


def main():
    results = []

    for entry in sorted(os.listdir(BASE_DIR)):
        project_dir = os.path.join(BASE_DIR, entry)
        if not os.path.isdir(project_dir) or not os.path.exists(
            os.path.join(project_dir, ".git")
        ):
            continue

        print(f"Processing: {entry}", flush=True)
        commits = get_commit_stats(project_dir)
        analysis = analyze_project(entry, commits)
        if analysis:
            results.append(analysis)

    # Write JSONL with full commit-level diff data
    with open(os.path.join(BASE_DIR, "commit-sizes.jsonl"), "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    # Print readable summary
    print("\n" + "=" * 100)
    print("COMMIT SIZE ANALYSIS")
    print("=" * 100)

    # Sort by first commit % descending
    by_first = sorted(results, key=lambda r: r["first_commit"]["pct_of_total"], reverse=True)

    print(f"\n### LARGE INITIAL COMMITS (first commit > 40% of total insertions, 3+ commits)")
    print(f"{'Project':<40} {'1st Commit %':>12} {'1st Lines':>10} {'Total':>10} {'Commits':>8}  First Commit Subject")
    print("-" * 130)
    for r in by_first:
        fc = r["first_commit"]
        if fc["pct_of_total"] > 40 and r["num_commits"] > 3:
            print(f"{r['project']:<40} {fc['pct_of_total']:>11.1f}% {fc['insertions']:>10,} {r['total_insertions']:>10,} {r['num_commits']:>8}  {fc['subject'][:50]}")

    print(f"\n### LARGE FINAL COMMITS (last commit > 40% of total insertions, 3+ commits)")
    by_last = [r for r in results if r["last_commit"]]
    by_last.sort(key=lambda r: r["last_commit"]["pct_of_total"], reverse=True)
    print(f"{'Project':<40} {'Last Commit %':>13} {'Last Lines':>11} {'Total':>10} {'Commits':>8}  Last Commit Subject")
    print("-" * 130)
    for r in by_last:
        lc = r["last_commit"]
        if lc["pct_of_total"] > 40 and r["num_commits"] > 3:
            print(f"{r['project']:<40} {lc['pct_of_total']:>12.1f}% {lc['insertions']:>11,} {r['total_insertions']:>10,} {r['num_commits']:>8}  {lc['subject'][:50]}")

    print(f"\n### LARGEST SINGLE COMMIT PER PROJECT")
    by_largest = sorted(results, key=lambda r: r["largest_commit"]["insertions"], reverse=True)
    print(f"{'Project':<40} {'Largest %':>10} {'Lines':>10} {'Commit #':>9} {'Date (JST)':<18}  Subject")
    print("-" * 130)
    for r in by_largest:
        lc = r["largest_commit"]
        dt = datetime.fromisoformat(lc["date"]).astimezone(JST)
        pos = f"{lc['index']+1}/{lc['of_total']}"
        print(f"{r['project']:<40} {lc['pct_of_total']:>9.1f}% {lc['insertions']:>10,} {pos:>9} {dt.strftime('%m-%d %H:%M'):>18}  {lc['subject'][:50]}")

    print(f"\n### FLAGS SUMMARY")
    flagged = [r for r in results if r["flags"]]
    for r in sorted(flagged, key=lambda r: r["project"].lower()):
        print(f"  {r['project']:<40} {', '.join(r['flags'])}")

    if not flagged:
        print("  (no projects flagged)")

    print(f"\n### ALL PROJECTS BY FIRST-COMMIT % (overview)")
    print(f"{'Project':<40} {'1st%':>5} {'Last%':>6} {'Largest%':>9} {'Median':>7} {'Commits':>8}")
    print("-" * 80)
    for r in by_first:
        lc_pct = r["last_commit"]["pct_of_total"] if r["last_commit"] else 0
        print(f"{r['project']:<40} {r['first_commit']['pct_of_total']:>4.0f}% {lc_pct:>5.0f}% {r['largest_commit']['pct_of_total']:>8.0f}% {r['median_commit_size']:>7,} {r['num_commits']:>8}")


if __name__ == "__main__":
    main()
