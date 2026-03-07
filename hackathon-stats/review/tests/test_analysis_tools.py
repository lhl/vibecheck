from __future__ import annotations

import json
from pathlib import Path

from analysis_tools import analyze_project, iter_git_projects, load_config


def test_load_config_resolves_paths_and_hack_window(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    config_dir = tmp_path / "analysis"
    config_dir.mkdir()
    (config_dir / "analysis-config.json").write_text(
        json.dumps(
            {
                "title": "Example Summary",
                "projects_dir": "../projects",
                "hack_window": {
                    "start": "2026-02-28T09:00:00+09:00",
                    "end": "2026-03-01T16:00:00+09:00",
                    "label": "Sat Feb 28 09:00 JST to Sun Mar 1 16:00 JST",
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_dir)

    assert config.title == "Example Summary"
    assert config.projects_dir == projects_root.resolve()
    assert config.output_dir == config_dir.resolve()
    assert config.hack_window is not None
    assert config.hack_window.label == "Sat Feb 28 09:00 JST to Sun Mar 1 16:00 JST"


def test_iter_git_projects_filters_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "zeta" / ".git").mkdir(parents=True)
    (tmp_path / "Alpha" / ".git").mkdir(parents=True)
    (tmp_path / "notes").mkdir()
    (tmp_path / "README.md").write_text("skip me", encoding="utf-8")

    projects = [path.name for path in iter_git_projects(tmp_path)]

    assert projects == ["Alpha", "zeta"]


def test_analyze_project_flags_large_initial_commit() -> None:
    commits = [
        {
            "hash": "1",
            "author_name": "A",
            "author_email": "a@example.com",
            "date": "2026-02-28T09:00:00+09:00",
            "subject": "initial",
            "files_changed": 10,
            "insertions": 100,
            "deletions": 0,
            "net_lines": 100,
        },
        {
            "hash": "2",
            "author_name": "A",
            "author_email": "a@example.com",
            "date": "2026-02-28T10:00:00+09:00",
            "subject": "followup 1",
            "files_changed": 2,
            "insertions": 5,
            "deletions": 0,
            "net_lines": 5,
        },
        {
            "hash": "3",
            "author_name": "A",
            "author_email": "a@example.com",
            "date": "2026-02-28T11:00:00+09:00",
            "subject": "followup 2",
            "files_changed": 2,
            "insertions": 5,
            "deletions": 0,
            "net_lines": 5,
        },
        {
            "hash": "4",
            "author_name": "A",
            "author_email": "a@example.com",
            "date": "2026-02-28T12:00:00+09:00",
            "subject": "followup 3",
            "files_changed": 2,
            "insertions": 5,
            "deletions": 0,
            "net_lines": 5,
        },
        {
            "hash": "5",
            "author_name": "A",
            "author_email": "a@example.com",
            "date": "2026-02-28T13:00:00+09:00",
            "subject": "followup 4",
            "files_changed": 2,
            "insertions": 5,
            "deletions": 0,
            "net_lines": 5,
        },
        {
            "hash": "6",
            "author_name": "A",
            "author_email": "a@example.com",
            "date": "2026-02-28T14:00:00+09:00",
            "subject": "followup 5",
            "files_changed": 2,
            "insertions": 5,
            "deletions": 0,
            "net_lines": 5,
        },
    ]

    analysis = analyze_project("demo", commits)

    assert analysis is not None
    assert analysis["first_commit"]["pct_of_total"] == 80.0
    assert "large_initial_commit" in analysis["flags"]
    assert "possible_existing_codebase" in analysis["flags"]
