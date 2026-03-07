from __future__ import annotations

import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

EXCLUDE_DIRS = (
    "node_modules,vendor,.venv,venv,__pycache__,dist,build,.next,.nuxt,"
    ".expo,.angular,.svelte-kit,bower_components,wandb,coverage,.tox,"
    ".eggs,site-packages,.mypy_cache,.pytest_cache,.ruff_cache"
)

EXCLUDE_PATHS = {
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".expo",
    ".angular",
    ".svelte-kit",
    "bower_components",
    "wandb",
    "coverage",
    ".tox",
    ".eggs",
    "site-packages",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

NON_CODE_LANGS = {
    "Markdown",
    "JSON",
    "YAML",
    "TOML",
    "SVG",
    "XML",
    "gitignore",
    "Dockerfile",
    "Docker ignore",
    "Plain Text",
    "License",
    ".env",
    "Properties File",
    "INI",
    "CSV",
    "JSONL",
    "Batch",
}


@dataclass(frozen=True)
class HackWindow:
    start: datetime
    end: datetime
    start_label: str
    end_label: str
    label: str


@dataclass(frozen=True)
class AnalysisConfig:
    config_dir: Path
    projects_dir: Path
    output_dir: Path
    title: str
    hack_window: HackWindow | None = None


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _format_window_datetime(value: datetime) -> str:
    return value.strftime("%a %b %d %H:%M %Z")


def load_config(config_dir: Path) -> AnalysisConfig:
    config_dir = config_dir.resolve()
    raw = json.loads((config_dir / "analysis-config.json").read_text(encoding="utf-8"))

    hack_window = None
    if "hack_window" in raw:
        hack = raw["hack_window"]
        start = datetime.fromisoformat(hack["start"])
        end = datetime.fromisoformat(hack["end"])
        start_label = hack.get("start_label", _format_window_datetime(start))
        end_label = hack.get("end_label", _format_window_datetime(end))
        label = hack.get("label", f"{start_label} to {end_label}")
        hack_window = HackWindow(
            start=start,
            end=end,
            start_label=start_label,
            end_label=end_label,
            label=label,
        )

    return AnalysisConfig(
        config_dir=config_dir,
        projects_dir=_resolve_path(config_dir, raw["projects_dir"]),
        output_dir=config_dir,
        title=raw["title"],
        hack_window=hack_window,
    )


def run(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        check=False,
    )
    return result.stdout.strip()


def iter_git_projects(projects_dir: Path) -> list[Path]:
    return sorted(
        [
            entry
            for entry in projects_dir.iterdir()
            if entry.is_dir() and (entry / ".git").exists()
        ],
        key=lambda path: path.name.lower(),
    )


def get_commits(project_dir: Path) -> list[dict[str, object]]:
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
        if len(parts) < 5:
            continue
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


def get_committers(project_dir: Path) -> list[dict[str, str]]:
    raw = run(["git", "log", "--format=%an%x00%ae"], cwd=project_dir)
    if not raw:
        return []

    committers = []
    seen: set[str] = set()
    for line in raw.splitlines():
        parts = line.split("\x00")
        if len(parts) != 2 or parts[1] in seen:
            continue
        seen.add(parts[1])
        committers.append({"name": parts[0], "email": parts[1]})
    return committers


def get_languages(project_dir: Path) -> list[dict[str, int | str]]:
    raw = run(
        [
            "scc",
            "--no-cocomo",
            "--no-complexity",
            "--exclude-dir",
            EXCLUDE_DIRS,
            "-f",
            "json",
            str(project_dir),
        ]
    )
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    languages = []
    for entry in data:
        if entry.get("Name") == "Total":
            continue
        try:
            languages.append(
                {
                    "language": entry["Name"],
                    "files": entry["Count"],
                    "lines": entry["Lines"],
                    "code": entry["Code"],
                    "blanks": entry["Blank"],
                    "comments": entry["Comment"],
                }
            )
        except KeyError:
            continue
    return languages


def _is_vendored(path: str) -> bool:
    return any(part in EXCLUDE_PATHS for part in path.split("/"))


def get_commit_stats(project_dir: Path) -> list[dict[str, object]]:
    raw = run(
        [
            "git",
            "log",
            "--reverse",
            "--numstat",
            "--format=%x01%H%x00%an%x00%ae%x00%aI%x00%s",
        ],
        cwd=project_dir,
    )
    if not raw:
        return []

    commits = []
    for block in raw.split("\x01"):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        parts = lines[0].split("\x00")
        if len(parts) < 5:
            continue

        insertions = 0
        deletions = 0
        files_changed = 0
        for line in lines[1:]:
            fields = line.split("\t")
            if len(fields) < 3 or _is_vendored(fields[2]):
                continue
            added = 0 if fields[0] == "-" else int(fields[0])
            removed = 0 if fields[1] == "-" else int(fields[1])
            insertions += added
            deletions += removed
            files_changed += 1

        commits.append(
            {
                "hash": parts[0],
                "author_name": parts[1],
                "author_email": parts[2],
                "date": parts[3],
                "subject": parts[4],
                "files_changed": files_changed,
                "insertions": insertions,
                "deletions": deletions,
                "net_lines": insertions - deletions,
            }
        )
    return commits


def analyze_project(name: str, commits: list[dict[str, object]]) -> dict[str, object] | None:
    if not commits:
        return None

    total_insertions = sum(int(commit["insertions"]) for commit in commits)
    sizes = [int(commit["insertions"]) for commit in commits]
    median_size = sorted(sizes)[len(sizes) // 2] if sizes else 0

    first = commits[0]
    last = commits[-1] if len(commits) > 1 else None
    first_pct = (int(first["insertions"]) / total_insertions * 100) if total_insertions else 0
    last_pct = (
        int(last["insertions"]) / total_insertions * 100 if last and total_insertions else 0
    )

    largest = max(commits, key=lambda commit: int(commit["insertions"]))
    largest_idx = commits.index(largest)
    largest_pct = (
        int(largest["insertions"]) / total_insertions * 100 if total_insertions else 0
    )

    flags = []
    if first_pct > 40 and len(commits) > 3:
        flags.append("large_initial_commit")
    if last and last_pct > 40 and len(commits) > 3:
        flags.append("large_final_commit")
    if 0 < largest_idx < len(commits) - 1 and largest_pct > 40:
        flags.append("large_mid_commit")
    if first_pct > 40 and len(commits) > 5:
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
            "insertions": int(first["insertions"]),
            "pct_of_total": round(first_pct, 1),
            "subject": first["subject"],
        },
        "last_commit": {
            "date": last["date"],
            "insertions": int(last["insertions"]),
            "pct_of_total": round(last_pct, 1),
            "subject": last["subject"],
        }
        if last
        else None,
        "largest_commit": {
            "index": largest_idx,
            "of_total": len(commits),
            "date": largest["date"],
            "insertions": int(largest["insertions"]),
            "pct_of_total": round(largest_pct, 1),
            "subject": largest["subject"],
        },
        "flags": flags,
        "commits": commits,
    }


def write_git_summary(config: AnalysisConfig) -> Path:
    out_path = config.output_dir / "git-summary.jsonl"
    with out_path.open("w", encoding="utf-8") as handle:
        for project_dir in iter_git_projects(config.projects_dir):
            print(f"Processing: {project_dir.name}", flush=True)
            commits = get_commits(project_dir)
            committers = get_committers(project_dir)
            record = {
                "project": project_dir.name,
                "num_commits": len(commits),
                "num_committers": len(committers),
                "first_commit": commits[-1]["date"] if commits else None,
                "last_commit": commits[0]["date"] if commits else None,
                "has_agents_md": (project_dir / "AGENTS.md").is_file(),
                "has_claude_md": (project_dir / "CLAUDE.md").is_file(),
                "languages": get_languages(project_dir),
                "committers": committers,
                "commits": commits,
            }
            handle.write(json.dumps(record) + "\n")
    print(f"Done. Output written to {out_path}")
    return out_path


def write_commit_sizes(config: AnalysisConfig) -> Path:
    out_path = config.output_dir / "commit-sizes.jsonl"
    analyses = []
    for project_dir in iter_git_projects(config.projects_dir):
        print(f"Processing: {project_dir.name}", flush=True)
        analysis = analyze_project(project_dir.name, get_commit_stats(project_dir))
        if analysis:
            analyses.append(analysis)

    with out_path.open("w", encoding="utf-8") as handle:
        for analysis in analyses:
            handle.write(json.dumps(analysis) + "\n")

    print(f"Done. Output written to {out_path}")
    return out_path


def write_scc_summary(config: AnalysisConfig) -> Path:
    out_path = config.output_dir / "scc-summary.txt"
    with out_path.open("w", encoding="utf-8") as handle:
        for project_dir in iter_git_projects(config.projects_dir):
            print(f"Processing: {project_dir.name}", flush=True)
            handle.write("=" * 80 + "\n")
            handle.write(f"PROJECT: {project_dir.name}\n")
            handle.write("=" * 80 + "\n")
            scc_output = run(
                ["scc", "--exclude-dir", EXCLUDE_DIRS, str(project_dir)],
            )
            handle.write(scc_output)
            handle.write("\n\n")
    print(f"Done. Output written to {out_path}")
    return out_path


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def code_lines(project: dict[str, object], *, exclude_non_code: bool = True) -> int:
    return sum(
        int(language["code"])
        for language in project["languages"]
        if not exclude_non_code or language["language"] not in NON_CODE_LANGS
    )


def code_files(project: dict[str, object], *, exclude_non_code: bool = True) -> int:
    return sum(
        int(language["files"])
        for language in project["languages"]
        if not exclude_non_code or language["language"] not in NON_CODE_LANGS
    )


def primary_lang(project: dict[str, object]) -> str:
    code_langs = [
        language for language in project["languages"] if language["language"] not in NON_CODE_LANGS
    ]
    if not code_langs:
        return "N/A"
    return max(code_langs, key=lambda language: int(language["code"]))["language"]


def detect_ai_tools(project_dir: Path, project: dict[str, object]) -> tuple[list[str], list[str]]:
    tools: set[str] = set()
    evidence: list[str] = []

    if (project_dir / ".claude").is_dir():
        tools.add("Claude Code")
        evidence.append("`.claude/` dir")
    if project["has_claude_md"]:
        tools.add("Claude Code")
        evidence.append("`CLAUDE.md`")
    if project["has_agents_md"]:
        evidence.append("`AGENTS.md`")
    if (project_dir / ".cursor").is_dir():
        tools.add("Cursor")
        evidence.append("`.cursor/` dir")
    if (project_dir / ".cursorrules").is_file():
        tools.add("Cursor")
        evidence.append("`.cursorrules`")

    branches = run(["git", "branch", "-a"], cwd=project_dir)
    if "copilot/" in branches:
        tools.add("GitHub Copilot")
        evidence.append("`copilot/*` branches")
    if "cursor/" in branches:
        tools.add("Cursor")
        evidence.append("`cursor/*` branches")
    if "codex/" in branches:
        tools.add("OpenAI Codex")
        evidence.append("`codex/*` branches")
    if "gemini/" in branches:
        tools.add("Gemini")
        evidence.append("`gemini/*` branches")
    if "claude/" in branches:
        tools.add("Claude Code")
        evidence.append("`claude/*` branches")

    messages = run(["git", "log", "--all", "--oneline"], cwd=project_dir).lower()
    if "claude" in messages and (
        "claude code" in messages or "claude.md" in messages or ".claude" in messages
    ):
        tools.add("Claude Code")
    if "codex" in messages:
        tools.add("OpenAI Codex")

    deduped_evidence = []
    seen = set()
    for item in evidence:
        if item in seen:
            continue
        seen.add(item)
        deduped_evidence.append(item)

    return sorted(tools), deduped_evidence


def build_readme(config: AnalysisConfig) -> Path:
    projects = _load_jsonl(config.output_dir / "git-summary.jsonl")
    commit_data = {
        item["project"]: item for item in _load_jsonl(config.output_dir / "commit-sizes.jsonl")
    }
    projects.sort(key=lambda project: project["project"].lower())

    lines = [f"# {config.title}\n", f"**{len(projects)} projects** analyzed\n"]

    agents = [project["project"] for project in projects if project["has_agents_md"]]
    claude = [project["project"] for project in projects if project["has_claude_md"]]
    both = [
        project["project"]
        for project in projects
        if project["has_agents_md"] and project["has_claude_md"]
    ]

    lines.append("## AI Coding Agent Files\n")
    lines.append(f"**AGENTS.md**: {len(agents)} projects")
    lines.extend(f"- {name}" for name in agents)
    lines.append(f"\n**CLAUDE.md**: {len(claude)} projects")
    lines.extend(f"- {name}" for name in claude)
    if both:
        lines.append(f"\n**Both**: {', '.join(both)}")
    lines.append("")

    ai_tools_per_project: dict[str, tuple[list[str], list[str]]] = {}
    for project in projects:
        tools, evidence = detect_ai_tools(config.projects_dir / project["project"], project)
        if tools:
            ai_tools_per_project[project["project"]] = (tools, evidence)

    tool_counts: Counter[str] = Counter()
    for tools, _ in ai_tools_per_project.values():
        tool_counts.update(tools)

    lines.append("## AI Coding Tools Detected\n")
    lines.append(
        "Evidence gathered from committed config directories, branch names, commit messages, and agent files.\n"
    )
    lines.append("### Tool usage summary\n")
    lines.append("| Tool | Projects |")
    lines.append("|------|----------|")
    for tool, count in tool_counts.most_common():
        lines.append(f"| {tool} | {count} |")
    lines.append("")

    lines.append("### Per-project AI tool evidence\n")
    lines.append("| Project | Tools Detected | Evidence |")
    lines.append("|---------|---------------|----------|")
    for name in sorted(ai_tools_per_project, key=str.lower):
        tools, evidence = ai_tools_per_project[name]
        lines.append(f"| {name} | {', '.join(tools)} | {', '.join(evidence)} |")
    lines.append("")

    lang_project_count: Counter[str] = Counter()
    lang_total_code: Counter[str] = Counter()
    for project in projects:
        seen = set()
        for language in project["languages"]:
            name = language["language"]
            if name in NON_CODE_LANGS:
                continue
            if name not in seen:
                lang_project_count[name] += 1
                seen.add(name)
            lang_total_code[name] += int(language["code"])

    lines.append("## Language Summary\n")
    lines.append("### Languages by number of projects using them\n")
    lines.append("| Language | Projects | Total Code Lines |")
    lines.append("|----------|----------|-----------------|")
    for language, count in lang_project_count.most_common():
        lines.append(f"| {language} | {count} | {lang_total_code[language]:,} |")
    lines.append("")

    lines.append("### Primary language per project\n")
    lines.append("| Project | Primary Language | Code Lines | Files | Commits | Committers |")
    lines.append("|---------|-----------------|-----------|-------|---------|------------|")
    for project in projects:
        lines.append(
            f"| {project['project']} | {primary_lang(project)} | {code_lines(project):,} | {code_files(project)} "
            f"| {project['num_commits']} | {project['num_committers']} |"
        )
    lines.append("")

    lines.append("## Largest / Most Complex Codebases\n")
    lines.append("### By code lines (excluding JSON/Markdown/config, top 20)\n")
    lines.append("| Project | Code Lines | Files | Primary Lang | Commits | Committers |")
    lines.append("|---------|-----------|-------|-------------|---------|------------|")
    for project in sorted(projects, key=code_lines, reverse=True)[:20]:
        lines.append(
            f"| {project['project']} | {code_lines(project):,} | {code_files(project)} | {primary_lang(project)} "
            f"| {project['num_commits']} | {project['num_committers']} |"
        )
    lines.append("")

    lines.append("### Most active projects (by commits)\n")
    lines.append("| Project | Commits | Committers | Code Lines | Primary Lang |")
    lines.append("|---------|---------|------------|-----------|--------------|")
    for project in sorted(projects, key=lambda item: item["num_commits"], reverse=True)[:15]:
        lines.append(
            f"| {project['project']} | {project['num_commits']} | {project['num_committers']} | {code_lines(project):,} | {primary_lang(project)} |"
        )
    lines.append("")

    lines.append("## Commit Size Patterns\n")
    lines.append("### Large initial commits (first commit > 40% of total insertions, 3+ commits)\n")
    lines.append(
        "These projects dumped a large amount of code in their first commit, suggesting they may have started from an existing codebase or framework scaffold.\n"
    )
    lines.append("| Project | 1st Commit % | 1st Lines | Total Inserted | Commits | First Commit Subject |")
    lines.append("|---------|-------------|----------|---------------|---------|---------------------|")
    large_first = [
        commit
        for commit in commit_data.values()
        if commit["first_commit"]["pct_of_total"] > 40 and commit["num_commits"] > 3
    ]
    for commit in sorted(
        large_first,
        key=lambda item: item["first_commit"]["pct_of_total"],
        reverse=True,
    ):
        first = commit["first_commit"]
        lines.append(
            f"| {commit['project']} | {first['pct_of_total']:.1f}% | {first['insertions']:,} | {commit['total_insertions']:,} "
            f"| {commit['num_commits']} | {first['subject'][:60]} |"
        )
    lines.append("")

    lines.append("### Large mid-project commits (biggest commit not first or last, > 40% of total)\n")
    lines.append("| Project | Largest % | Lines | Position | Subject |")
    lines.append("|---------|----------|-------|----------|---------|")
    large_mid = [
        commit
        for commit in commit_data.values()
        if 0 < commit["largest_commit"]["index"] < commit["num_commits"] - 1
        and commit["largest_commit"]["pct_of_total"] > 40
    ]
    for commit in sorted(large_mid, key=lambda item: item["largest_commit"]["insertions"], reverse=True):
        largest = commit["largest_commit"]
        lines.append(
            f"| {commit['project']} | {largest['pct_of_total']:.1f}% | {largest['insertions']:,} "
            f"| {largest['index'] + 1}/{largest['of_total']} | {largest['subject'][:60]} |"
        )
    lines.append("")

    lines.append("### Flags summary\n")
    flags_map: dict[str, list[str]] = {}
    for commit in commit_data.values():
        for flag in commit.get("flags", []):
            flags_map.setdefault(flag, []).append(commit["project"])
    flag_labels = {
        "possible_existing_codebase": "Possible existing codebase (large 1st commit + 5+ follow-ups)",
        "large_initial_commit": "Large initial commit (>40% of total)",
        "large_mid_commit": "Large mid-project commit (>40% of total)",
        "large_final_commit": "Large final commit (>40% of total)",
        "poor_version_control": "Poor version control (large final commit, <=5 total commits)",
    }
    lines.append("| Flag | Projects |")
    lines.append("|------|----------|")
    for flag, label in flag_labels.items():
        if flag not in flags_map:
            continue
        lines.append(f"| {label} | {', '.join(sorted(flags_map[flag], key=str.lower))} |")
    lines.append("")

    lines.append("### All projects commit pattern overview\n")
    lines.append("| Project | 1st% | Last% | Largest% | Median Ins. | Commits |")
    lines.append("|---------|------|-------|----------|-------------|---------|")
    for commit in sorted(
        commit_data.values(),
        key=lambda item: item["first_commit"]["pct_of_total"],
        reverse=True,
    ):
        last_pct = commit["last_commit"]["pct_of_total"] if commit["last_commit"] else 0
        lines.append(
            f"| {commit['project']} | {commit['first_commit']['pct_of_total']:.0f}% | {last_pct:.0f}% | {commit['largest_commit']['pct_of_total']:.0f}% "
            f"| {commit['median_commit_size']:,} | {commit['num_commits']} |"
        )
    lines.append("")

    if config.hack_window is not None:
        window = config.hack_window
        early_projects = []
        late_projects = []
        for project in projects:
            early_commits = []
            late_commits = []
            for commit in commit_data.get(project["project"], {}).get("commits", []):
                when = datetime.fromisoformat(commit["date"])
                if when < window.start:
                    early_commits.append(commit)
                if when > window.end:
                    late_commits.append(commit)
            if early_commits:
                early_projects.append((project["project"], early_commits))
            if late_commits:
                late_projects.append((project["project"], late_commits))

        lines.append("## Commit Timing Analysis\n")
        lines.append(f"Hackathon window: **{window.label}**\n")
        lines.append(
            f"### Projects with commits BEFORE {window.start_label} ({len(early_projects)} projects)\n"
        )
        if early_projects:
            lines.append("| Project | Early Commits | Earliest |")
            lines.append("|---------|--------------|----------|")
            for name, commits in sorted(early_projects, key=lambda item: item[0].lower()):
                earliest = min(datetime.fromisoformat(commit["date"]) for commit in commits)
                lines.append(f"| {name} | {len(commits)} | {earliest.strftime('%Y-%m-%d %H:%M %Z')} |")
        else:
            lines.append("(none)")
        lines.append("")

        lines.append(
            f"### Projects with commits AFTER {window.end_label} ({len(late_projects)} projects)\n"
        )
        if late_projects:
            lines.append("| Project | Late Commits | Latest |")
            lines.append("|---------|-------------|--------|")
            for name, commits in sorted(late_projects, key=lambda item: item[0].lower()):
                latest = max(datetime.fromisoformat(commit["date"]) for commit in commits)
                lines.append(f"| {name} | {len(commits)} | {latest.strftime('%Y-%m-%d %H:%M %Z')} |")
        else:
            lines.append("(none)")
        lines.append("")

    total_commits = sum(int(project["num_commits"]) for project in projects)
    all_committers = {
        committer["email"]
        for project in projects
        for committer in project.get("committers", [])
    }
    total_code = sum(code_lines(project) for project in projects)

    lines.append("## Quick Stats\n")
    lines.append(f"- **Total commits**: {total_commits:,}")
    lines.append(f"- **Unique committers**: {len(all_committers)}")
    lines.append(f"- **Total code lines** (excl. config/data): {total_code:,}")
    lines.append(f"- **Avg commits/project**: {total_commits / len(projects):.1f}")
    lines.append(
        f"- **Avg committers/project**: {sum(int(project['num_committers']) for project in projects) / len(projects):.1f}"
    )
    lines.append("")

    out_path = config.output_dir / "README.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")
    return out_path
