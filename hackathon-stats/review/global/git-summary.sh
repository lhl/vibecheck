#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec uv run python "$DIR/../analysis_runner.py" git-summary "$DIR"
