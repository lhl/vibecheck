# vibecheck — Project Instructions

## What This Is

vibecheck is a mobile PWA bridge for Mistral Vibe. It hooks into Vibe's Textual/Python event system (AgentLoop callbacks) and exposes them over WebSocket to a Svelte 5 mobile client. See README.md for the full product brief, docs/PLAN.md for the architecture, and docs/IMPLEMENTATION.md for the work unit punchlist.

## Architecture

```
Phone (PWA) → HTTPS/WSS → EC2 (Caddy → FastAPI bridge → Vibe AgentLoop)
```

- **Backend:** FastAPI + Starlette, in-process with AgentLoop
- **Frontend:** Svelte 5 + Vite PWA
- **Key hooks:** `set_approval_callback()`, `set_user_input_callback()`, `message_observer`
- **Events:** `BaseEvent` hierarchy (AssistantEvent, ToolCallEvent, ToolResultEvent, etc.)

## Tech Stack

- Python 3.12+ via uv (never bare `python` or `pip`)
- FastAPI + Starlette (async, WebSocket)
- Svelte 5 + Vite (frontend)
- Mistral SDK (`mistralai`) for Voxtral, Ministral, Small APIs
- pywebpush for VAPID push notifications

## Environment Variables

These are set globally on the development machine. Do not hardcode, auto-generate, or prompt for them.

| Variable | Purpose |
|----------|---------|
| `VIBECHECK_PSK` | Pre-shared key for API auth. Sent as `X-PSK` header. Already set in the environment. |
| `MISTRAL_API_KEY` | Mistral SDK key. Only needed for live voice/translation (L3+). Mock in tests. |

## Key Files

| File | Purpose |
|------|---------|
| `docs/IMPLEMENTATION.md` | **Work unit punchlist — start here for tasks** |
| `docs/PLAN.md` | Hackathon execution plan (layers L0-L9) |
| `README.md` | Full product brief |
| `docs/DEMO.md` | Presentation script and demo setup |
| `docs/ANALYSIS-vibe.md` | Vibe v2.2.1 internals (AgentLoop, events, callbacks) |
| `docs/REMOTING-UI.md` | Mobile-to-TUI bridge architecture research |
| `WORKLOG.md` | **Running log of all major actions** — installations, config changes, decisions, not just WU completions |
| `scripts/` | Smoke tests, event replay |
| `vibecheck/` | Python backend package |
| `vibecheck/frontend/` | Svelte 5 + Vite PWA |
| `vibecheck/tests/` | Backend pytest suite |
| `prototypes/` | Standalone browser-API test pages |
| `frontend-prototype/` | **Standalone STT+TTS voice loop** (Voxtral + ElevenLabs) — reuse for WU-17/18/29/30 |
| `tests/fixtures/` | Sample event sequences for replay/testing |
| `reference/mistral-vibe/` | **Vibe source checkout** — read this for AgentLoop, event types, callback signatures |

---

## Test-Driven Development

**Every change must be verifiable. Write tests first, implement second, verify third.**

### The Loop

1. **Write the test** — define expected behavior before implementation
2. **Run the test** — confirm it fails (proves test is meaningful)
3. **Implement** — minimal code to pass the test
4. **Run the test** — confirm it passes
5. **Run all related tests** — confirm nothing broke

### Backend Tests (Python)

```bash
# Run all backend tests
uv run pytest vibecheck/tests/ -v

# Run a specific test file
uv run pytest vibecheck/tests/test_api.py -v

# Run a single test
uv run pytest vibecheck/tests/test_api.py::test_health_endpoint -v

# Run with coverage
uv run pytest vibecheck/tests/ --cov=vibecheck --cov-report=term-missing
```

**Test requirements:**
- Every REST endpoint: happy path, auth failure (no PSK, bad PSK), error cases
- Every Pydantic model: serialization round-trip, validation errors
- WebSocket: connect/disconnect, auth, broadcast, backlog delivery
- Bridge: state transitions, approval/input Future resolution, event broadcasting
- API integrations (Voxtral, Ministral, translation): mock the Mistral SDK, test our proxy logic

**Mock the external world:**
- Use `MockBridge` (no real Vibe instance needed for API tests)
- Use `unittest.mock.patch` for Mistral SDK calls
- Use httpx `AsyncClient` for FastAPI test client
- Never require network access or running services in unit tests

### Frontend Tests

```bash
# Build must succeed (minimum bar)
cd vibecheck/frontend && npm run build

# Dev server must start
npm run dev  # verify port responds

# Component tests (if vitest configured)
npm test
```

### Frontend Deploy

Vite builds into `vibecheck/static/` which FastAPI serves directly. **After any frontend change, you must rebuild and restart the server** for the change to be live:

```bash
cd vibecheck/frontend && npm run build   # outputs to ../static/
# Then restart the server (kill and re-run):
uv run vibecheck-vibe                    # recommended: Vibe TUI + bridge
# or: uv run python -m vibecheck        # server-only bridge
```

Without the rebuild, the server continues serving stale cached bundles. The build produces hashed filenames (e.g. `index-BHv5LYMU.css`) so the old files won't match.

### Prototype Tests

Each prototype has a `test.sh`:
```bash
cd prototypes/websocket-reconnect && ./test.sh
```

### Smoke Tests (Integration)

```bash
# Against local or remote server
scripts/smoke_test.sh http://localhost:7870
scripts/smoke_test.sh https://vibecheck.shisa.ai
```

### Event Replay (FE dev without Vibe)

```bash
# Replay canned events over WebSocket for frontend testing
uv run python scripts/replay_events.py --port 7870
```

### Before Claiming Done

For every work unit, verify:
- [ ] Tests pass: `uv run pytest vibecheck/tests/ -v` (backend) or `npm run build` (frontend)
- [ ] No regressions: related test files still pass
- [ ] Server starts: `uv run python -m vibecheck` (if backend changes)
- [ ] Build succeeds: `cd vibecheck/frontend && npm run build` (if frontend changes)

---

## Coding Standards

### Python (Backend)

- Modern Python 3.12+: match-case, walrus operator, `list`/`dict` generics, `X | None` unions
- Type hints on all function signatures
- Pydantic v2 for data models and validation
- pathlib.Path for filesystem ops
- f-strings, comprehensions, context managers
- Flat code — early returns, guard clauses, avoid deep nesting
- Use `uv run`, `uv add`, never bare `python` or `pip`
- async/await for all I/O (FastAPI, WebSocket, httpx)

### JavaScript/Svelte (Frontend)

- Svelte 5 (runes syntax if available, otherwise stores)
- ES modules, no CommonJS
- `const` by default, `let` when needed, never `var`
- Template literals over string concatenation
- Destructuring for function params and imports

---

## Multi-Agent Collaboration

**Multiple agents may be working in the same worktree simultaneously.** Follow these rules to avoid conflicts:

### Stay in Your Lane

- **Only modify files relevant to your assigned work unit (WU-xx)**
- If you see changes to files outside your scope, **ignore them** — another agent is working on those
- Do not revert, restore, or "clean up" files you didn't modify
- Unrelated dirty/untracked files in the worktree are expected and non-blocking

### Single-File Contention

- If two agents need to touch the same file and edits may overlap, **stop and await instruction** before continuing in that file.
- Do not keep editing, staging, or committing contested-file changes until one agent is explicitly designated to proceed.
- The designated agent should do a careful selective stage (`git add -p`) and commit only their scoped hunks first to unblock others.
- The non-designated agent should leave that file untouched until the first commit lands and they can rebase/continue cleanly.
- Never resolve contention by force-staging the whole file or reverting another agent’s work.

### Git Hygiene

- **NEVER** use `git add .`, `git add -A`, or `git commit -a`
- **ALWAYS** add files explicitly: `git add <file1> <file2> ...`
- **ALWAYS** verify staged files before commit:
  ```bash
  git diff --staged --name-only   # verify only your files are staged
  git diff --staged               # review the actual diff
  ```
- Stage **only** files from your work unit — if another agent's files show up as modified, leave them unstaged
- If unrelated changes exist in the worktree, leave them untouched

### Commit Practices

**When you finish a logical piece of work, commit.** A "task" is any complete logical unit — not every individual file edit, but not only WU completions either. Config changes, doc updates, tool installations, dependency additions — all are committable units. Commits are cheap and make collaboration safer: easier to revert, less stepping on each other's toes, clearer history.

- **Commit immediately** after validation passes — do not wait to be asked
- Do not commit mid-task (while iterating, exploring, or debugging)
- This applies to all completed work — code, tests, docs, config — not just WU closures
- Use **conventional commits**: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- **No bylines** or co-author footers in commits
- **Atomic commits** — group related changes, separate unrelated ones
- Include the WU ID when relevant

**Commit message format:**
```
type: short summary (imperative mood)

WU-xx: brief context if helpful
```

Examples:
```
feat: add PSK auth middleware with timing-safe comparison

WU-01: backend scaffold
```
```
docs: add Vibe setup worklog and update USING-VIBE.md
```
```
test: add WebSocket reconnect prototype with test server

WU-03: proto websocket-reconnect
```

### Pull Before Push

- `git pull --rebase` before pushing to avoid merge conflicts
- If rebase conflicts with another agent's work, resolve only your files and leave theirs intact
- When in doubt about a conflict, ask rather than force

### What To Do If...

| Situation | Action |
|-----------|--------|
| You see uncommitted changes to files outside your WU | Ignore them — another agent is working |
| `git status` shows modified files you didn't touch | Normal — don't stage them |
| Your tests import a module another agent is building | Use the existing interface/stubs; if they don't exist yet, create a minimal mock |
| Two agents need to modify the same file | Stop and await instruction; one designated agent selectively stages and commits first |
| Merge conflict on pull | Resolve only your changes, keep theirs |

---

## Work Units

See `docs/IMPLEMENTATION.md` for the full punchlist with dependency graph, parallelism map, and verification steps for each work unit (WU-01 through WU-35).

**Before starting a WU:**
1. Read its entry in IMPLEMENTATION.md
2. Check its dependencies are done
3. Read any existing code in the affected files
4. Write tests first

**After completing a WU:**
1. Run verification steps from IMPLEMENTATION.md
2. Run `uv run pytest vibecheck/tests/ -v` (if backend) or `npm run build` (if frontend)
3. Commit your files only
4. Update WORKLOG.md with what you completed

### WORKLOG.md Guidelines

Log **all major actions**, not just WU completions. The worklog is our shared memory of what happened and why. Include:
- Tool/dependency installations and version info
- Config file changes and rationale
- Infrastructure/deployment actions
- Decisions made (e.g., "chose playwright-cli over playwright-mcp because more token-efficient")
- Blockers encountered and how they were resolved

Format: `### Section heading` under the current date, bullet points for details.

---

## Handling Blockers

- **Missing dependency:** Check if the WU you depend on is done. If not, work on something else or create a minimal stub/mock.
- **Test failures:** Fix before proceeding. Don't skip tests.
- **Import errors from Vibe:** Backend tests should mock Vibe internals. If you need real Vibe, coordinate with the team.
- **Unclear requirements:** Check docs/PLAN.md and README.md first. If still unclear, ask.
- **Build failures:** Fix immediately. Don't commit broken builds.
- **Another agent broke something:** If their change broke your tests, flag it. Don't silently fix their code.
