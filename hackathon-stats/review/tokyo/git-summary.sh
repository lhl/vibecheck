#!/usr/bin/env bash
# Generate JSONL git summary for each project
# Each line: one project with commits, committers, stats

DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$DIR/git-summary.jsonl"

> "$OUT"

for project in "$DIR"/*/; do
    name="$(basename "$project")"

    # Skip non-git directories
    if [ ! -d "$project/.git" ]; then
        echo "Skipping (no git): $name" >&2
        continue
    fi

    echo "Processing: $name" >&2

    # Get commits as JSON array
    commits_json=$(git -C "$project" log --format='{"hash":"%H","author_name":"%an","author_email":"%ae","date":"%aI","subject":"%s"}' 2>/dev/null | \
        python3 -c "
import sys, json
commits = []
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    # Parse the git log output - subject may contain quotes
    # Split on known delimiters
    parts = line.split('\"subject\":\"', 1)
    if len(parts) == 2:
        prefix = parts[0] + '\"subject\":'
        subject = parts[1].rstrip('}').rstrip('\"')
        # Escape any unescaped quotes in subject
        subject = subject.replace('\\\\', '\\\\\\\\').replace('\"', '\\\\\"')
        line = prefix + '\"' + subject + '\"}'
    try:
        commits.append(json.loads(line))
    except json.JSONDecodeError:
        pass
print(json.dumps(commits))
")

    # Get unique committers
    committers_json=$(git -C "$project" log --format='%an <%ae>' 2>/dev/null | sort -u | \
        python3 -c "
import sys, json
committers = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(committers))
")

    num_commits=$(git -C "$project" rev-list --count HEAD 2>/dev/null || echo 0)
    num_committers=$(git -C "$project" log --format='%ae' 2>/dev/null | sort -u | wc -l | tr -d ' ')

    # First and last commit dates
    first_commit=$(git -C "$project" log --reverse --format='%aI' 2>/dev/null | head -1)
    last_commit=$(git -C "$project" log -1 --format='%aI' 2>/dev/null)

    # Check for AGENTS.md / CLAUDE.md
    has_agents_md=$([ -f "$project/AGENTS.md" ] && echo true || echo false)
    has_claude_md=$([ -f "$project/CLAUDE.md" ] && echo true || echo false)

    # Top-level languages from scc (compact)
    languages_json=$(scc --no-cocomo --no-complexity -f json "$project" 2>/dev/null | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    langs = [{'language': d['Name'], 'files': d['Count'], 'lines': d['Lines'], 'code': d['Code']} for d in data]
    print(json.dumps(langs))
except:
    print('[]')
")

    # Build the JSONL record
    python3 -c "
import json
record = {
    'project': '$name',
    'num_commits': $num_commits,
    'num_committers': $num_committers,
    'first_commit': '$first_commit',
    'last_commit': '$last_commit',
    'has_agents_md': $has_agents_md,
    'has_claude_md': $has_claude_md,
    'languages': $languages_json,
    'committers': $committers_json,
    'commits': $commits_json
}
print(json.dumps(record))
" >> "$OUT"

done

echo "Done. Output written to $OUT" >&2
