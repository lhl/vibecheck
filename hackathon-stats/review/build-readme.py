#!/usr/bin/env python3
"""Build the full README.md from git-summary.jsonl and commit-sizes.jsonl."""

import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
HACK_START = datetime(2026, 2, 28, 9, 0, 0, tzinfo=JST)
HACK_END = datetime(2026, 3, 1, 16, 0, 0, tzinfo=JST)

NON_CODE_LANGS = {
    "Markdown", "JSON", "YAML", "TOML", "SVG", "XML", "gitignore",
    "Dockerfile", "Docker ignore", "Plain Text", "License", ".env",
    "Properties File", "INI", "CSV", "JSONL", "Batch",
}

projects = []
with open("git-summary.jsonl") as f:
    for line in f:
        projects.append(json.loads(line))

commit_data = {}
with open("commit-sizes.jsonl") as f:
    for line in f:
        d = json.loads(line)
        commit_data[d["project"]] = d

projects.sort(key=lambda p: p["project"].lower())


def code_lines(p, exclude_non_code=True):
    return sum(
        l["code"]
        for l in p["languages"]
        if not exclude_non_code or l["language"] not in NON_CODE_LANGS
    )


def code_files(p, exclude_non_code=True):
    return sum(
        l["files"]
        for l in p["languages"]
        if not exclude_non_code or l["language"] not in NON_CODE_LANGS
    )


def primary_lang(p):
    code_langs = [l for l in p["languages"] if l["language"] not in NON_CODE_LANGS]
    if not code_langs:
        return "N/A"
    return max(code_langs, key=lambda l: l["code"])["language"]


L = []  # output lines
L.append("# Mistral Hackathon 2026 - Project Summary\n")
L.append(f"**{len(projects)} projects** analyzed\n")

# === AI Agent Files ===
L.append("## AI Coding Agent Files\n")
agents = [p["project"] for p in projects if p["has_agents_md"]]
claude = [p["project"] for p in projects if p["has_claude_md"]]
both = [p["project"] for p in projects if p["has_agents_md"] and p["has_claude_md"]]

L.append(f"**AGENTS.md**: {len(agents)} projects")
for a in agents:
    L.append(f"- {a}")
L.append(f"\n**CLAUDE.md**: {len(claude)} projects")
for c in claude:
    L.append(f"- {c}")
if both:
    L.append(f"\n**Both**: {', '.join(both)}")
L.append("")

# === AI Tools Detection ===
L.append("## AI Coding Tools Detected\n")
L.append("Evidence gathered from committed config directories, branch names, commit messages, and agent files.\n")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run(cmd, cwd=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.stdout.strip()


ai_tools_per_project = {}
for p in projects:
    name = p["project"]
    project_dir = os.path.join(BASE_DIR, name)
    tools = set()

    # Config directories/files
    if os.path.isdir(os.path.join(project_dir, ".claude")):
        tools.add("Claude Code")
    if p["has_claude_md"]:
        tools.add("Claude Code")
    if os.path.isdir(os.path.join(project_dir, ".cursor")):
        tools.add("Cursor")
    if os.path.isfile(os.path.join(project_dir, ".cursorrules")):
        tools.add("Cursor")

    # Branch names
    if os.path.isdir(os.path.join(project_dir, ".git")):
        branches = run(["git", "branch", "-a"], cwd=project_dir)
        if "copilot/" in branches:
            tools.add("GitHub Copilot")
        if "cursor/" in branches:
            tools.add("Cursor")
        if "codex/" in branches:
            tools.add("OpenAI Codex")
        if "gemini/" in branches:
            tools.add("Gemini")
        if "claude/" in branches:
            tools.add("Claude Code")

        # Commit messages (lightweight check)
        msgs = run(["git", "log", "--all", "--oneline"], cwd=project_dir)
        if "claude" in msgs.lower() and ("claude code" in msgs.lower() or "CLAUDE.md" in msgs or ".claude" in msgs):
            tools.add("Claude Code")
        if "copilot/" in msgs:
            tools.add("GitHub Copilot")
        if "cursor/" in msgs:
            tools.add("Cursor")
        # Check for Codex references (but not just the word "code")
        if "codex" in msgs.lower():
            tools.add("OpenAI Codex")

    if tools:
        ai_tools_per_project[name] = sorted(tools)

# Tool usage summary
tool_counts = Counter()
for tools in ai_tools_per_project.values():
    for t in tools:
        tool_counts[t] += 1

L.append("### Tool usage summary\n")
L.append("| Tool | Projects |")
L.append("|------|----------|")
for tool, count in tool_counts.most_common():
    L.append(f"| {tool} | {count} |")
L.append("")

L.append("### Per-project AI tool evidence\n")
L.append("| Project | Tools Detected | Evidence |")
L.append("|---------|---------------|----------|")
for name in sorted(ai_tools_per_project, key=str.lower):
    tools = ai_tools_per_project[name]
    evidence = []
    project_dir = os.path.join(BASE_DIR, name)
    if os.path.isdir(os.path.join(project_dir, ".claude")):
        evidence.append("`.claude/` dir")
    for p in projects:
        if p["project"] == name:
            if p["has_claude_md"]:
                evidence.append("`CLAUDE.md`")
            if p["has_agents_md"]:
                evidence.append("`AGENTS.md`")
            break
    if os.path.isdir(os.path.join(project_dir, ".cursor")):
        evidence.append("`.cursor/` dir")
    branches = run(["git", "branch", "-a"], cwd=project_dir) if os.path.isdir(os.path.join(project_dir, ".git")) else ""
    for prefix, tool in [("copilot/", "Copilot"), ("cursor/", "Cursor"), ("codex/", "Codex")]:
        if prefix in branches:
            evidence.append(f"`{prefix}*` branches")
    L.append(f"| {name} | {', '.join(tools)} | {', '.join(evidence)} |")
L.append("")

# === Language Summary ===
L.append("## Language Summary\n")
L.append("### Languages by number of projects using them\n")

lang_project_count = Counter()
lang_total_code = Counter()

for p in projects:
    seen = set()
    for lang in p["languages"]:
        name = lang["language"]
        if name in NON_CODE_LANGS:
            continue
        if name not in seen:
            lang_project_count[name] += 1
            seen.add(name)
        lang_total_code[name] += lang["code"]

L.append("| Language | Projects | Total Code Lines |")
L.append("|----------|----------|-----------------|")
for lang, count in lang_project_count.most_common():
    L.append(f"| {lang} | {count} | {lang_total_code[lang]:,} |")
L.append("")

# === Primary language per project ===
L.append("### Primary language per project\n")
L.append("| Project | Primary Language | Code Lines | Files | Commits | Committers |")
L.append("|---------|-----------------|-----------|-------|---------|------------|")
for p in projects:
    L.append(
        f"| {p['project']} | {primary_lang(p)} "
        f"| {code_lines(p):,} | {code_files(p)} "
        f"| {p['num_commits']} | {p['num_committers']} |"
    )
L.append("")

# === Largest Codebases ===
L.append("## Largest / Most Complex Codebases\n")
L.append("### By code lines (excluding JSON/Markdown/config, top 20)\n")
L.append("| Project | Code Lines | Files | Primary Lang | Commits | Committers |")
L.append("|---------|-----------|-------|-------------|---------|------------|")
for p in sorted(projects, key=lambda p: code_lines(p), reverse=True)[:20]:
    L.append(
        f"| {p['project']} | {code_lines(p):,} | {code_files(p)} "
        f"| {primary_lang(p)} | {p['num_commits']} | {p['num_committers']} |"
    )
L.append("")

# === Most Active ===
L.append("### Most active projects (by commits)\n")
L.append("| Project | Commits | Committers | Code Lines | Primary Lang |")
L.append("|---------|---------|------------|-----------|--------------|")
for p in sorted(projects, key=lambda p: p["num_commits"], reverse=True)[:15]:
    L.append(
        f"| {p['project']} | {p['num_commits']} | {p['num_committers']} "
        f"| {code_lines(p):,} | {primary_lang(p)} |"
    )
L.append("")

# === Commit Size Patterns ===
L.append("## Commit Size Patterns\n")

L.append("### Large initial commits (first commit > 40% of total insertions, 3+ commits)\n")
L.append("These projects dumped a large amount of code in their first commit, suggesting they may have started from an existing codebase or framework scaffold.\n")
L.append("| Project | 1st Commit % | 1st Lines | Total Inserted | Commits | First Commit Subject |")
L.append("|---------|-------------|----------|---------------|---------|---------------------|")
large_first = []
for name, cd in commit_data.items():
    fc = cd["first_commit"]
    if fc["pct_of_total"] > 40 and cd["num_commits"] > 3:
        large_first.append(cd)
for cd in sorted(large_first, key=lambda c: c["first_commit"]["pct_of_total"], reverse=True):
    fc = cd["first_commit"]
    L.append(
        f"| {cd['project']} | {fc['pct_of_total']:.1f}% | {fc['insertions']:,} "
        f"| {cd['total_insertions']:,} | {cd['num_commits']} | {fc['subject'][:60]} |"
    )
L.append("")

L.append("### Large mid-project commits (biggest commit not first or last, > 40% of total)\n")
L.append("| Project | Largest % | Lines | Position | Subject |")
L.append("|---------|----------|-------|----------|---------|")
large_mid = []
for name, cd in commit_data.items():
    lc = cd["largest_commit"]
    if lc["index"] > 0 and lc["index"] < cd["num_commits"] - 1 and lc["pct_of_total"] > 40:
        large_mid.append(cd)
for cd in sorted(large_mid, key=lambda c: c["largest_commit"]["insertions"], reverse=True):
    lc = cd["largest_commit"]
    L.append(
        f"| {cd['project']} | {lc['pct_of_total']:.1f}% | {lc['insertions']:,} "
        f"| {lc['index']+1}/{lc['of_total']} | {lc['subject'][:60]} |"
    )
L.append("")

L.append("### Flags summary\n")
flags_map = {}
for name, cd in commit_data.items():
    for flag in cd.get("flags", []):
        flags_map.setdefault(flag, []).append(name)

L.append("| Flag | Projects |")
L.append("|------|----------|")
flag_labels = {
    "possible_existing_codebase": "Possible existing codebase (large 1st commit + 5+ follow-ups)",
    "large_initial_commit": "Large initial commit (>40% of total)",
    "large_mid_commit": "Large mid-project commit (>40% of total)",
    "large_final_commit": "Large final commit (>40% of total)",
    "poor_version_control": "Poor version control (large final commit, <=5 total commits)",
}
for flag, label in flag_labels.items():
    if flag in flags_map:
        names = sorted(flags_map[flag], key=str.lower)
        L.append(f"| {label} | {', '.join(names)} |")
L.append("")

# === All projects overview ===
L.append("### All projects commit pattern overview\n")
L.append("| Project | 1st% | Last% | Largest% | Median Ins. | Commits |")
L.append("|---------|------|-------|----------|-------------|---------|")
for cd in sorted(commit_data.values(), key=lambda c: c["first_commit"]["pct_of_total"], reverse=True):
    lc_pct = cd["last_commit"]["pct_of_total"] if cd["last_commit"] else 0
    L.append(
        f"| {cd['project']} | {cd['first_commit']['pct_of_total']:.0f}% | {lc_pct:.0f}% "
        f"| {cd['largest_commit']['pct_of_total']:.0f}% | {cd['median_commit_size']:,} | {cd['num_commits']} |"
    )
L.append("")

# === Timing Analysis ===
L.append("## Commit Timing Analysis\n")
L.append(f"Hackathon window: **Sat Feb 28 09:00 JST** to **Sun Mar 1 16:00 JST**\n")

early_projects = []
late_projects = []
for p in projects:
    early_commits = []
    late_commits = []
    cd = commit_data.get(p["project"])
    if not cd:
        continue
    for c in cd.get("commits", []):
        dt = datetime.fromisoformat(c["date"])
        if dt < HACK_START:
            early_commits.append(c)
        if dt > HACK_END:
            late_commits.append(c)
    if early_commits:
        early_projects.append((p["project"], len(early_commits), early_commits))
    if late_commits:
        late_projects.append((p["project"], len(late_commits), late_commits))

L.append(f"### Projects with commits BEFORE Sat 9AM JST ({len(early_projects)} projects)\n")
if early_projects:
    L.append("| Project | Early Commits | Earliest |")
    L.append("|---------|--------------|----------|")
    for name, count, commits in sorted(early_projects):
        earliest = min(c["date"] for c in commits)
        dt = datetime.fromisoformat(earliest).astimezone(JST)
        L.append(f"| {name} | {count} | {dt.strftime('%Y-%m-%d %H:%M JST')} |")
else:
    L.append("(none)")
L.append("")

L.append(f"### Projects with commits AFTER Sun 4PM JST ({len(late_projects)} projects)\n")
if late_projects:
    L.append("| Project | Late Commits | Latest |")
    L.append("|---------|-------------|--------|")
    for name, count, commits in sorted(late_projects):
        latest = max(c["date"] for c in commits)
        dt = datetime.fromisoformat(latest).astimezone(JST)
        L.append(f"| {name} | {count} | {dt.strftime('%Y-%m-%d %H:%M JST')} |")
else:
    L.append("(none)")
L.append("")

# === Quick Stats ===
L.append("## Quick Stats\n")
total_commits = sum(p["num_commits"] for p in projects)
all_committers = set()
for p in projects:
    for c in p.get("committers", []):
        all_committers.add(c["email"])
total_code = sum(code_lines(p) for p in projects)
L.append(f"- **Total commits**: {total_commits:,}")
L.append(f"- **Unique committers**: {len(all_committers)}")
L.append(f"- **Total code lines** (excl. config/data): {total_code:,}")
L.append(f"- **Avg commits/project**: {total_commits / len(projects):.1f}")
L.append(f"- **Avg committers/project**: {sum(p['num_committers'] for p in projects) / len(projects):.1f}")
L.append("")

with open("README.md", "w") as f:
    f.write("\n".join(L))

print("Wrote README.md")
