#!/usr/bin/env python3
"""Generate JSONL git summary for each project subdirectory."""

import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(BASE_DIR, "git-summary.jsonl")

EXCLUDE_DIRS = (
    "node_modules,vendor,.venv,venv,__pycache__,dist,build,.next,.nuxt,"
    ".expo,.angular,.svelte-kit,bower_components,wandb,coverage,.tox,"
    ".eggs,site-packages,.mypy_cache,.pytest_cache,.ruff_cache"
)


def run(cmd, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


def get_commits(project_dir):
    # Use %x00 as field separator, %x01 as record separator
    raw = run(
        ["git", "log", "--format=%H%x00%an%x00%ae%x00%aI%x00%s%x01"],
        cwd=project_dir,
    )
    if not raw:
        return []
    commits = []
    for record in raw.split("\x01"):
        record = record.strip()
        if not record:
            continue
        parts = record.split("\x00")
        if len(parts) >= 5:
            commits.append(
                {
                    "hash": parts[0],
                    "author_name": parts[1],
                    "author_email": parts[2],
                    "date": parts[3],
                    "subject": parts[4],
                }
            )
    return commits


def get_committers(project_dir):
    raw = run(
        ["git", "log", "--format=%an%x00%ae"],
        cwd=project_dir,
    )
    if not raw:
        return []
    seen = set()
    committers = []
    for line in raw.splitlines():
        parts = line.split("\x00")
        if len(parts) == 2 and parts[1] not in seen:
            seen.add(parts[1])
            committers.append({"name": parts[0], "email": parts[1]})
    return committers


def get_languages(project_dir):
    raw = run(["scc", "--no-cocomo", "--no-complexity", "--exclude-dir", EXCLUDE_DIRS, "-f", "json", project_dir])
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [
            {
                "language": d["Name"],
                "files": d["Count"],
                "lines": d["Lines"],
                "code": d["Code"],
                "blanks": d["Blank"],
                "comments": d["Comment"],
            }
            for d in data
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def main():
    with open(OUT_FILE, "w") as out:
        for entry in sorted(os.listdir(BASE_DIR)):
            project_dir = os.path.join(BASE_DIR, entry)
            if not os.path.isdir(project_dir):
                continue
            git_dir = os.path.join(project_dir, ".git")
            if not os.path.exists(git_dir):
                print(f"Skipping (no git): {entry}", file=sys.stderr)
                continue

            print(f"Processing: {entry}", file=sys.stderr)

            commits = get_commits(project_dir)
            committers = get_committers(project_dir)

            first_commit = commits[-1]["date"] if commits else None
            last_commit = commits[0]["date"] if commits else None

            record = {
                "project": entry,
                "num_commits": len(commits),
                "num_committers": len(committers),
                "first_commit": first_commit,
                "last_commit": last_commit,
                "has_agents_md": os.path.isfile(
                    os.path.join(project_dir, "AGENTS.md")
                ),
                "has_claude_md": os.path.isfile(
                    os.path.join(project_dir, "CLAUDE.md")
                ),
                "languages": get_languages(project_dir),
                "committers": committers,
                "commits": commits,
            }
            out.write(json.dumps(record) + "\n")

    print(f"Done. Output written to {OUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
