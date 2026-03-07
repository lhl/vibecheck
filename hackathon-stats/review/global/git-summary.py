#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis_tools import load_config, write_git_summary


if __name__ == "__main__":
    write_git_summary(load_config(Path(__file__).resolve().parent))
