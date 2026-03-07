#!/usr/bin/env bash
# Run scc with COCOMO estimates on each project subdirectory
# Excludes vendored/generated directories

OUT="scc-summary.txt"
DIR="$(cd "$(dirname "$0")" && pwd)"

EXCLUDE_DIRS="node_modules,vendor,.venv,venv,__pycache__,dist,build,.next,.nuxt,.expo,.angular,.svelte-kit,bower_components,wandb,coverage,.tox,.eggs,site-packages,.mypy_cache,.pytest_cache,.ruff_cache"

> "$DIR/$OUT"

for project in "$DIR"/*/; do
    name="$(basename "$project")"
    echo "Processing: $name"
    {
        echo "================================================================================"
        echo "PROJECT: $name"
        echo "================================================================================"
        scc --exclude-dir "$EXCLUDE_DIRS" "$project"
        echo ""
    } >> "$DIR/$OUT"
done

echo "Done. Output written to $DIR/$OUT"
