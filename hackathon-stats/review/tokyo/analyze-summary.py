#!/usr/bin/env python3
"""Analyze git-summary.jsonl and produce a README.md summary."""

import json
from collections import Counter
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
# Hackathon window: Sat 9AM JST to Sun 4PM JST
HACK_START = datetime(2026, 2, 28, 9, 0, 0, tzinfo=JST)
HACK_END = datetime(2026, 3, 1, 16, 0, 0, tzinfo=JST)

projects = []
with open("git-summary.jsonl") as f:
    for line in f:
        projects.append(json.loads(line))

projects.sort(key=lambda p: p["project"].lower())

lines = []
lines.append("# Mistral Hackathon 2026 - Project Summary")
lines.append("")
lines.append(f"**{len(projects)} projects** analyzed")
lines.append("")

# === AGENTS.md / CLAUDE.md ===
lines.append("## AI Coding Agent Files")
lines.append("")
agents = [p["project"] for p in projects if p["has_agents_md"]]
claude = [p["project"] for p in projects if p["has_claude_md"]]
lines.append(f"**AGENTS.md**: {len(agents)} projects")
if agents:
    for a in agents:
        lines.append(f"- {a}")
lines.append("")
lines.append(f"**CLAUDE.md**: {len(claude)} projects")
if claude:
    for c in claude:
        lines.append(f"- {c}")
else:
    lines.append("- (none)")
lines.append("")

# === Language Summary ===
lines.append("## Language Summary")
lines.append("")

# Count how many projects use each language (by primary code lines)
lang_project_count = Counter()
lang_total_code = Counter()
project_primary_lang = {}

for p in projects:
    langs = p.get("languages", [])
    seen = set()
    best_lang = None
    best_code = 0
    for lang in langs:
        name = lang["language"]
        if name in ("Markdown", "JSON", "YAML", "TOML", "Plain Text", "License",
                     "SVG", "XML", "gitignore", "Dockerfile", "Docker ignore",
                     "Shell", "Batch", "Makefile", "CSS", "HTML", "BASH",
                     ".env", "Properties File", "INI"):
            continue
        if name not in seen:
            lang_project_count[name] += 1
            seen.add(name)
        lang_total_code[name] += lang["code"]
        if lang["code"] > best_code:
            best_code = lang["code"]
            best_lang = name
    project_primary_lang[p["project"]] = best_lang or "N/A"

lines.append("### Languages by number of projects using them")
lines.append("")
lines.append("| Language | Projects | Total Code Lines |")
lines.append("|----------|----------|-----------------|")
for lang, count in lang_project_count.most_common():
    lines.append(f"| {lang} | {count} | {lang_total_code[lang]:,} |")
lines.append("")

lines.append("### Primary language per project")
lines.append("")
lines.append("| Project | Primary Language | Commits | Committers |")
lines.append("|---------|-----------------|---------|------------|")
for p in projects:
    lines.append(
        f"| {p['project']} | {project_primary_lang[p['project']]} "
        f"| {p['num_commits']} | {p['num_committers']} |"
    )
lines.append("")

# === Timing Analysis ===
lines.append("## Commit Timing Analysis")
lines.append("")
lines.append(f"Hackathon window: **Sat Feb 28 09:00 JST** to **Sun Mar 1 16:00 JST**")
lines.append("")

early_projects = []  # commits before Sat 9AM JST
late_projects = []   # commits after Sun 4PM JST
for p in projects:
    has_early = False
    has_late = False
    early_commits = []
    late_commits = []
    for c in p.get("commits", []):
        dt = datetime.fromisoformat(c["date"])
        if dt < HACK_START:
            has_early = True
            early_commits.append(c)
        if dt > HACK_END:
            has_late = True
            late_commits.append(c)
    if has_early:
        early_projects.append((p["project"], len(early_commits), early_commits))
    if has_late:
        late_projects.append((p["project"], len(late_commits), late_commits))

lines.append(f"### Projects with commits BEFORE Sat 9AM JST ({len(early_projects)} projects)")
lines.append("")
if early_projects:
    lines.append("| Project | Early Commits | Earliest |")
    lines.append("|---------|--------------|----------|")
    for name, count, commits in sorted(early_projects):
        earliest = min(c["date"] for c in commits)
        dt = datetime.fromisoformat(earliest).astimezone(JST)
        lines.append(f"| {name} | {count} | {dt.strftime('%Y-%m-%d %H:%M JST')} |")
else:
    lines.append("(none)")
lines.append("")

lines.append(f"### Projects with commits AFTER Sun 4PM JST ({len(late_projects)} projects)")
lines.append("")
if late_projects:
    lines.append("| Project | Late Commits | Latest |")
    lines.append("|---------|-------------|--------|")
    for name, count, commits in sorted(late_projects):
        latest = max(c["date"] for c in commits)
        dt = datetime.fromisoformat(latest).astimezone(JST)
        lines.append(f"| {name} | {count} | {dt.strftime('%Y-%m-%d %H:%M JST')} |")
else:
    lines.append("(none)")
lines.append("")

# === Quick Stats ===
lines.append("## Quick Stats")
lines.append("")
total_commits = sum(p["num_commits"] for p in projects)
all_committers = set()
for p in projects:
    for c in p.get("committers", []):
        all_committers.add(c["email"])
total_code = sum(
    sum(l["code"] for l in p.get("languages", []))
    for p in projects
)
lines.append(f"- **Total commits**: {total_commits:,}")
lines.append(f"- **Unique committers**: {len(all_committers)}")
lines.append(f"- **Total code lines**: {total_code:,}")
lines.append(f"- **Avg commits/project**: {total_commits / len(projects):.1f}")
lines.append(f"- **Avg committers/project**: {sum(p['num_committers'] for p in projects) / len(projects):.1f}")
lines.append("")

with open("README.md", "w") as f:
    f.write("\n".join(lines))

print("Wrote README.md")
