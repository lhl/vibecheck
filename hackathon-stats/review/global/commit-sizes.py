#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis_tools import load_config, write_commit_sizes


if __name__ == "__main__":
    write_commit_sizes(load_config(Path(__file__).resolve().parent))
