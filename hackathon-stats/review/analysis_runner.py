#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from analysis_tools import build_readme, load_config, write_commit_sizes, write_git_summary, write_scc_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run hackathon analysis tasks")
    parser.add_argument(
        "command",
        choices=["git-summary", "commit-sizes", "build-readme", "scc-summary", "all"],
    )
    parser.add_argument("config_dir", help="Analysis directory containing analysis-config.json")
    args = parser.parse_args()

    config = load_config(Path(args.config_dir))

    if args.command in {"git-summary", "all"}:
        write_git_summary(config)
    if args.command in {"commit-sizes", "all"}:
        write_commit_sizes(config)
    if args.command in {"scc-summary", "all"}:
        write_scc_summary(config)
    if args.command in {"build-readme", "all"}:
        build_readme(config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
