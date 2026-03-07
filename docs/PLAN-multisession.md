# Multi-Session Plan (vibecheck.shisa.ai as a Hub)

> **Status:** Proposed (design doc)
> **Last updated:** 2026-03-01
>
> **Goal:** Open `https://vibecheck.shisa.ai/` and see + connect to **all** running Vibe sessions. Spin up new sessions and tear them down from the PWA. Optionally attach a terminal TUI to any session later.

This document synthesizes the architecture options for multi-session when **each live session requires in-process access to its own `AgentLoop`** (live approvals/input), but we still want **one** public origin and **one** WebSocket API surface for the PWA.

Related docs:
- `docs/PLAN.md` (current roadmap and single-process multi-session design)
- `docs/ANALYSIS-session-attachment.md` (why cross-process live attach is impossible without IPC)

---

## Terminology

- **Hub:** the one public FastAPI server behind Caddy (the only origin the PWA talks to).
- **Worker:** a per-session process that owns a live `AgentLoop` (usually started via `uv run vibecheck-vibe`).
- **Session:** a Vibe conversation identified by `session_id` (and optionally namespaced by worker).
- **Managed session:** an `AgentLoop` created programmatically by the bridge (`_ensure_agent_loop()`) rather than by the CLI launcher.
- **TUI attach:** connecting a Textual terminal UI to an already-running session, either at launch or after the fact.

---

## Problem Statement

Today, `uv run vibecheck-vibe` starts:
- A Textual TUI (Vibe UI)
- A FastAPI/uvicorn server (REST + WebSocket) on a TCP port (default `7870`)
- A `SessionBridge` live-attached to the in-process `AgentLoop`

Running *multiple* `vibecheck-vibe` processes currently means:
- You must use different ports (`--ws-port`) to avoid binding conflicts.
- The PWA is *not* a multi-origin client. It assumes the same origin for:
  - `GET /api/sessions`
  - `WS /ws/events/{session_id}`
- Therefore, sessions hosted on different ports are not visible at one `vibecheck.shisa.ai` endpoint.

---

## Constraints (Non-Negotiable)

1. **Live attach requires same process**
   - Tool approvals and user-input callbacks are in-process `asyncio.Future` resolution.
   - A separate process cannot resolve another process's pending Futures without a purpose-built IPC/control channel.

2. **One TCP port = one server process**
   - Only one process can bind `:7870`.
   - If we want `vibecheck.shisa.ai` to represent the whole fleet, we need a single "front door" service on the public port.

3. **Multiple Textual TUIs implies multiple OS processes**
   - Each session with a terminal UI needs a real TTY (or a PTY via tmux/script/etc.).
   - We should assume "one live TUI session per worker process."

---

## Target UX / Requirements

Must-have:
- From `vibecheck.shisa.ai`:
  - list all active sessions ("fleet")
  - connect to a chosen session and see live events
  - send a message, approve/deny tool calls, answer questions
- Sessions started in terminals (`vibecheck-vibe`) should appear automatically.

Nice-to-have:
- Start (spawn) new sessions from the PWA.
- Stop (tear down) sessions from the PWA.
- Attach a TUI to a PWA-spawned session after the fact (SSH + tmux, web terminal, etc.).

Non-goals (for now):
- Perfect load balancing across machines.
- Multi-tenant auth (PSK remains the security boundary).

---

## What Already Exists (Audit)

The codebase has more multi-session infrastructure than might be obvious:

| Component | Location | Multi-session ready? |
|-----------|----------|---------------------|
| `SessionManager` | `bridge.py:1292` | **Yes** — dict of `SessionBridge` instances keyed by `session_id` |
| `ConnectionManager` | `ws.py:14` | **Yes** — room-based routing: `rooms[session_id] → set[WebSocket]` |
| REST API | `routes/api.py` | **Yes** — all endpoints scoped to `/api/sessions/{session_id}/...` |
| Frontend `SessionPicker` | `frontend/src/components/SessionPicker.svelte` | **Yes** — lists sessions, switch between them |
| `SessionBridge._ensure_agent_loop()` | `bridge.py:1070` | **Yes** — lazily creates an `AgentLoop` for a "managed" bridge |
| `SessionManager.start_session()` | `bridge.py:1400` | **Yes** — creates managed bridge + starts agent turn |
| `SessionBridge.inject_message()` | `bridge.py:1189` | **Yes** — queues messages into an existing session's loop |

**Key insight:** A managed `SessionBridge` can already create its own `AgentLoop` without a TUI and process messages entirely from the PWA. The main missing piece is a REST endpoint to trigger session creation.

---

## Options

### Option 0: Status Quo (One `vibecheck-vibe` per host)

How it works:
- Run exactly one `vibecheck-vibe` on `:7870`.

Pros:
- No new code.
- Matches current demo path.

Cons:
- Does not satisfy "run as many sessions as we want."

---

### Option 1: In-Process Managed Sessions (Quickest Win)

How it works:
- Run one `vibecheck-vibe` on `:7870` as today (this is the "primary" session with TUI).
- Add a `POST /api/sessions` endpoint that creates additional `SessionBridge` instances **in the same process**.
- Each new bridge lazily creates its own `AgentLoop` via `_ensure_agent_loop()`.
- All sessions share the same `SessionManager`, `ConnectionManager`, and FastAPI server.
- PWA talks to the same origin for everything — no proxy, no IPC.

What already works:
- `SessionManager.start_session(session_id, message)` does exactly this.
- `_ensure_agent_loop()` creates a managed `AgentLoop` with config from `~/.vibe/config.toml`.
- The connection manager already has room-based routing.
- The frontend session picker already lists and switches sessions.

What's missing:
- `POST /api/sessions` REST endpoint (~20 lines).
- `DELETE /api/sessions/{session_id}` REST endpoint for teardown (~15 lines).
- Frontend "New Session" button in `SessionPicker.svelte`.
- Optional: ability to specify `working_dir`, agent name, initial prompt.

Spawn from PWA: **Yes** — direct, immediate.
Teardown from PWA: **Yes** — `session_manager.detach(session_id)` + bridge cleanup.
TUI attach later: **No** — the `AgentLoop` lives in the hub process; you cannot attach a Textual app to another process's loop without IPC.

Pros:
- Smallest code change (~50-100 lines total).
- Single process, single port, Caddy config unchanged.
- All sessions immediately visible to all clients.
- `asyncio.Future` resolution is in-process (no serialization needed).

Cons:
- All `AgentLoop`s share one Python process (GIL, memory, crash domain).
- A bad tool call or OOM in one session can take down the whole server.
- No TUI for managed sessions (PWA-only control).
- `working_dir` isolation is tricky — all loops share `os.getcwd()`.

Effort: **Small** — 1-2 hours of implementation + tests.

---

### Option 2: Multiple Ports + User Chooses Port (No Hub)

How it works:
- Run N `vibecheck-vibe` processes on `:7870`, `:7871`, `:7872`, ...
- Operator manually navigates to different origins/ports.

Pros:
- Very low engineering cost.

Cons:
- Fails the primary goal: one `vibecheck.shisa.ai` surface aggregating all sessions.
- Push notifications and "session picker" become fragmented per origin.

Spawn from PWA: **No.**
Teardown from PWA: **No.**
TUI attach later: **N/A** — each process already has its own TUI.

---

### Option 3: Reverse Proxy Fan-Out (Path/Subdomain per Session)

How it works:
- Run multiple backends on different ports.
- Configure Caddy/Nginx to route:
  - `/ws/events/{session_id}` to the right backend
  - `/api/sessions/...` to the right backend

Pros:
- Keep workers unchanged.

Cons:
- Needs a dynamic routing table keyed by `session_id`.
- Caddy config is static by default; dynamic per-session routing is non-trivial (Caddy API or template reload).
- Still needs an aggregator for `/api/sessions` (each backend only knows itself).
- WebSocket upgrade routing adds complexity.

Spawn from PWA: **No** — cannot create a new backend process from a Caddy config.
Teardown from PWA: **No.**
TUI attach later: **N/A** — each process already has its own TUI.

Verdict: Not recommended as the primary plan. It punts the hard part (dynamic registry) to the proxy layer.

---

### Option 4: Hub + Worker Servers (Hub Proxies to Workers)

How it works:
- Run a **hub** server on `:7870` (public, behind Caddy).
- Run N **workers** (each `vibecheck-vibe`) on internal ports (`127.0.0.1:7871+`).
- Each worker registers itself with the hub:
  - `session_id`
  - worker base URL (control plane)
  - capabilities (live controllable, has TUI, etc.)
- The hub:
  - serves PWA static files
  - exposes `/api/sessions` aggregated across workers
  - terminates client WebSockets at `/ws/events/{session_id}`
  - proxies streaming events from the correct worker to the client
  - proxies REST actions (`approve`, `input`, `message`, `auto-approve`) to the worker

Pros:
- Minimal conceptual change to existing worker: it keeps its REST + WS stack.
- Hub is a "single origin" for the PWA, satisfying the main requirement.

Cons:
- Hub must implement a reliable WS proxy/bridge per active session (two-hop WebSocket).
- Two sources of truth for session state/backlog (worker vs hub) unless the hub stays stateless.
- Requires internal networking (hub must reach worker ports).

Spawn from PWA: **Yes, with work** — hub spawns a subprocess + assigns a port.
Teardown from PWA: **Yes** — hub sends shutdown to worker or kills PID.
TUI attach later: **Yes** — worker is a real process with a potential PTY (see Spawn section).

---

### Option 5: Hub Authoritative; Workers Forward Events (Recommended for Multi-Process)

How it works:
- Run **one** public hub (`:7870`) that is the only server the PWA ever talks to.
- Each live session runs in a **worker** process that owns the `AgentLoop`.
- Workers do NOT need to expose a public WS endpoint for clients.
- Instead:
  - Worker forwards every `Event` to hub (push model).
  - Hub stores per-session backlog and broadcasts to connected PWA clients at `/ws/events/{session_id}`.
  - For control actions, hub forwards commands to the owning worker.

Two sub-variants:
- **5A: Worker -> Hub via HTTP POST**
  - simplest implementation
  - noisier (many requests) and easier to overload
- **5B: Worker -> Hub via persistent WebSocket (preferred)**
  - efficient, backpressure-friendly
  - hub can detect disconnects quickly (marks session offline)

Pros:
- Hub becomes the single source of truth for what the PWA sees (backlog, state, push notifications).
- No WS proxying complexity (hub is the WS server; workers are event publishers).
- Extends naturally to multi-host in the future (workers connect out to the hub).

Cons:
- Requires new "worker protocol" (registration + event stream + control channel).
- Requires some refactor so `vibecheck-vibe` can run as a worker (suppress its own HTTP server, forward events instead of broadcasting locally).

Spawn from PWA: **Yes, with work** — hub spawns worker subprocess.
Teardown from PWA: **Yes** — hub sends shutdown command or kills PID.
TUI attach later: **Yes** — worker is a real process with a potential PTY.

---

### Option 6: Full Worker Control Channel (No Worker Ports)

How it works:
- Workers connect to hub over a single outbound WebSocket:
  - send events upstream
  - receive control commands downstream (inject message, resolve approval, etc.)
- Workers do not need to bind any TCP ports at all.

Pros:
- Simplifies networking and firewalling.
- Best for distributed workers (multiple machines).

Cons:
- More protocol work up front (command routing, acks, retries, idempotency).

Spawn from PWA: **Yes.**
Teardown from PWA: **Yes.**
TUI attach later: **Yes.**

Verdict: Good "v2" of Option 5B once the hub/worker split is proven.

---

### Option 7: tmux/PTY Sidecar (Terminal Scraping Fallback)

How it works:
- Run normal `vibe` sessions in tmux panes.
- Sidecar scrapes terminal output + injects keystrokes for approvals.

Pros:
- Works even if Vibe internals change, as long as the UI is scriptable.

Cons:
- Not typed events, fragile parsing, hard to keep state correct.
- Worst UX and highest maintenance.

Verdict: Fallback only.

---

### Option 8: Upstream ACP / Native IPC (Wait for Vibe Support)

How it works:
- Use (or contribute) an upstream control protocol that supports attaching to an already-running session from another process.

Pros:
- Most robust long-term if upstream commits to stable APIs.

Cons:
- Out of our direct control and schedule.
- Not available in Vibe today.

Verdict: Keep an eye on it, but plan as if it won't land in time.

---

## Comparison Matrix

| Capability | Opt 0 (Status Quo) | Opt 1 (In-Process) | Opt 2 (Multi-Port) | Opt 3 (Rev. Proxy) | Opt 4 (Hub Proxy) | Opt 5 (Hub Auth.) | Opt 6 (Full Chan.) |
|---|---|---|---|---|---|---|---|
| Single origin for PWA | Yes (1 session) | **Yes** | No | Partial | **Yes** | **Yes** | **Yes** |
| Multiple concurrent sessions | No | **Yes** | Yes (manual) | Yes (manual) | **Yes** | **Yes** | **Yes** |
| Spawn from PWA | No | **Yes** | No | No | Yes | Yes | Yes |
| Teardown from PWA | No | **Yes** | No | No | Yes | Yes | Yes |
| Crash isolation | N/A | **No** | Yes | Yes | **Yes** | **Yes** | **Yes** |
| TUI per session | Yes | **No** | Yes | Yes | **Yes** | **Yes** | **Yes** |
| TUI attach later (to spawned) | N/A | **No** | N/A | N/A | **Yes** | **Yes** | **Yes** |
| CLI-started sessions visible | Yes | **Yes** | No | Partial | **Yes** | **Yes** | **Yes** |
| Multi-host ready | No | No | No | No | No | Partial | **Yes** |
| New code required | None | ~100 lines | ~0 | ~200 lines | ~500 lines | ~800 lines | ~1200 lines |
| Caddy changes | None | None | Per-session | Per-session | None | None | None |

---

## Hybrid Strategy: Start with 1, Evolve to 5

Options 1 and 5 are not mutually exclusive. They compose naturally:

**Option 1 gives us immediate multi-session** with zero infrastructure overhead: add a REST endpoint, create in-process `AgentLoop`s, done. The PWA can spawn/teardown sessions immediately.

**Option 5 gives us process isolation + TUI attach** later, by extracting session lifecycle into worker processes that report to the hub.

The key insight: **the hub in Option 5 is just the existing server from Option 1, plus a worker registration protocol.** We don't need to rewrite the hub — we grow it.

```
Phase 1 (Option 1):  Hub IS the server, sessions are in-process managed AgentLoops
Phase 2 (Option 5):  Hub ALSO accepts remote workers that forward events
Phase 3 (Option 6):  Workers don't need ports; bidirectional control channel
```

---

## Phase 1: In-Process Managed Sessions (Option 1)

### What to build

**Backend (~100 lines):**

```python
# routes/api.py — new endpoints

@router.post("/api/sessions")
async def create_session(body: CreateSessionRequest):
    """Spawn a new headless managed session."""
    session_id = body.session_id or f"managed-{uuid.uuid4().hex[:8]}"
    if session_manager.has_known_session(session_id):
        raise HTTPException(409, f"Session {session_id} already exists")
    bridge = session_manager.attach(session_id, attach_mode="managed")
    # If an initial message is provided, kick off the first agent turn
    if body.message:
        bridge._ensure_agent_loop()
        bridge.inject_message(body.message)
    return {"session_id": session_id, "status": bridge.state}

@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Tear down a managed session."""
    bridge = _session_or_404(session_id)
    if bridge.attach_mode == "live":
        raise HTTPException(409, "Cannot delete a live (CLI-started) session")
    session_manager.detach(session_id)
    return {"deleted": session_id}
```

```python
# models (Pydantic)

class CreateSessionRequest(BaseModel):
    session_id: str | None = None
    message: str | None = None
    agent_name: str = "default"
```

**Frontend (~50 lines):**
- "New Session" button in `SessionPicker.svelte`.
- Calls `POST /api/sessions`, then switches to the new session.
- "Delete" button on managed sessions (not on live/CLI sessions).

### What this gets us

- Open `vibecheck.shisa.ai` → see all sessions (CLI-started + PWA-spawned).
- Tap "New Session" → new managed `AgentLoop` created in-process.
- Send messages, approve tools, answer questions — all from PWA.
- Tap "Delete" → session torn down, resources freed.
- CLI-started session still has its TUI and is also visible in PWA.

### Limitations to accept

- No TUI for PWA-spawned sessions (PWA-only control surface).
- No crash isolation — a managed session that hangs blocks the event loop.
- `working_dir` is shared (all sessions run in the server's `cwd`).
- Memory grows with each session (~100-500MB per active AgentLoop + context).

### Verification

```bash
# Start the server
uv run vibecheck-vibe

# From another terminal, create a session
curl -H "X-PSK: $VIBECHECK_PSK" -X POST \
  http://localhost:7870/api/sessions \
  -d '{"message": "what is 2+2?"}'

# List sessions — should show both CLI + managed
curl -H "X-PSK: $VIBECHECK_PSK" http://localhost:7870/api/sessions

# Open PWA — both sessions should appear in session picker
```

---

## Recommendation: Claude Opus 4.6

> *Collected as part of multi-model feedback on this design doc. This section represents one model's independent analysis of the options and tradeoffs.*

**Recommendation: Phase 1 (in-process managed sessions) first. Build Phase 2 only when you hit a concrete wall.**

### The gap is smaller than it looks

The codebase already has the multi-session primitives: `_ensure_agent_loop()` lazily creates an `AgentLoop` for any managed bridge, `SessionManager.start_session()` wires it up, `ConnectionManager` does room-based WebSocket routing, and every REST endpoint is already scoped to `/api/sessions/{session_id}`. The frontend session picker lists and switches between sessions. The literal missing piece is a POST endpoint and a button. This is an afternoon, not a project.

### Phase 2 solves a problem you probably won't hit soon

The hub+worker architecture (Option 5B) is ~800 lines of new protocol code: worker registration, event forwarding, a bidirectional control channel, heartbeats, disconnect semantics. It buys two things: crash isolation and TUI-per-session. Neither is urgent:

- **Crash isolation** — `AgentLoop.act()` is async I/O-bound (waiting on LLM API calls). Tool execution runs in subprocesses that Vibe manages. The Python host process itself almost never crashes. At 5-10 concurrent sessions, this is a theoretical risk, not a practical one. You'll hit memory limits before you hit crash risk.

- **TUI per spawned session** — genuinely useful, but requires Phase 2 (worker process) + Phase 3 (tmux spawn + attach workflow). That's two phases of infrastructure before the TUI-attach payoff lands. Meanwhile, the PWA already provides the full control surface: messages, approvals, input, auto-approve, event stream. The TUI is a debugging convenience, not a control necessity.

### The real workflow question

The original ask was "run multiple `uv run vibecheck-vibe` sessions." But once you can spawn sessions from the phone, ask: how often do you actually need a second CLI-started session? The typical workflow becomes: one `vibecheck-vibe` for terminal debugging + N headless sessions from the PWA for parallel work. That's exactly what Phase 1 provides.

The case where Phase 1 falls short: multiple operators who each want their own terminal, or sessions that need truly isolated working directories (different repos, different `cwd`). If that's the day-one requirement, go straight to Phase 2. But if the primary consumer is the PWA, Phase 1 covers it.

### Forward compatibility is the key design insight

`POST /api/sessions` is the same endpoint in Phase 1 and Phase 2. In Phase 1 it creates an in-process managed `AgentLoop`. In Phase 2 it gains an optional `"spawn": "worker"` parameter that forks a subprocess instead. The PWA never changes. The REST and WebSocket contract is identical whether the session is in-process or remote — the `SessionManager.list()` merges both sources transparently.

This means Phase 1 isn't throwaway work or tech debt — it's the foundation that Phase 2 extends. The API surface, the frontend UX, and the test coverage all carry forward.

### What I'd build, concretely

1. `POST /api/sessions` — ~20 lines, creates managed in-process session
2. `DELETE /api/sessions/{session_id}` — ~15 lines, tears down managed sessions (guards against deleting live CLI sessions)
3. "New Session" button in `SessionPicker.svelte` + "Delete" affordance on managed sessions — ~50 lines frontend
4. Test coverage for the create → message → approve → delete lifecycle
5. Ship it, use it, and let real usage tell you whether Phase 2 is needed

### When to escalate to Phase 2

Build the hub+worker split when any of these become true:
- A managed session crash actually takes down the server (not hypothetical — it happened)
- You need >10 concurrent sessions and memory pressure is real
- Multiple operators need independent terminals for their sessions
- You need per-session working directory isolation for different repositories
- You want to distribute sessions across multiple machines

Until then, the in-process approach is simpler to operate, simpler to debug, and simpler to reason about. The best architecture is the one with the fewest moving parts that still meets the requirements.

---

## Recommendation: GPT-5.3-Codex (xhigh)

> *Collected as part of multi-model feedback on this design doc. This section represents one model's independent analysis of the options and tradeoffs.*

**Recommendation: choose the hybrid explicitly as policy, not just as a possibility:**
- **Ship Option 1 now** (single-origin, in-process multi-session spawn/teardown).
- **Design Option 5B seams now** (session ownership metadata + worker registration contract stubs).
- **Move to Option 5B when objective trigger conditions are met.**

### Why this is the best fit for your current requirements

Your immediate product requirement is clear: one URL (`vibecheck.shisa.ai`) where users can see and control all sessions. Option 1 already satisfies that with the smallest delta and no topology change:
- keeps existing REST + WS contract,
- keeps existing frontend assumptions,
- adds only create/delete lifecycle endpoints and UI affordances.

That means you get user-visible value quickly while avoiding protocol and ops complexity that users do not yet experience.

### Why not jump directly to full hub/worker now

Going straight to Option 5B/6 is technically clean but front-loads hard distributed-systems work:
- worker lifecycle + registration,
- control channel reliability (acks/idempotency/retry semantics),
- heartbeat/offline handling,
- two-plane auth model and internal networking policy.

Those are worthwhile investments, but they are not the shortest path to proving the multi-session UX at one URL.

### Where I differ slightly from a pure “stay in-process” view

I would avoid treating Option 1 as an end state. Implement it as **Phase-1 architecture with migration hooks**:
- add `session_origin` (`in_process` vs `worker`) in session payloads,
- add optional `owner_id`/`worker_id` fields now (nullable for in-process),
- keep `/api/sessions` and `/ws/events/{id}` as the permanent public contract.

This keeps frontend and API stable when worker routing is introduced later.

### Recommended trigger gates for Phase 2 (Option 5B)

Promote to hub+workers when any one of these happens in production-like usage:
1. Need guaranteed per-session TUI access for PWA-spawned sessions.
2. Need strict failure isolation between sessions.
3. Need stronger working-directory/process isolation across repos.
4. Need concurrency that stresses a single-process memory envelope.
5. Need multi-host placement.

### Implementation posture I recommend

1. Build Option 1 now and ship quickly.
2. Add basic operational guardrails immediately (session cap, idle timeout, clear “managed vs live” labels).
3. Draft the worker protocol as an internal RFC while Option 1 is being used.
4. Implement Option 5B only after one of the trigger gates is observed (not anticipated).

### Bottom line

If the decision is “what should we do next week,” pick **Option 1**.  
If the decision is “what architecture should we converge to over time,” pick **Option 5B**.  
The winning strategy is **Option 1 now, Option 5B by trigger**, with compatibility seams added from day one.

---

## Recommendation: GPT-5.2 xhigh

> *Collected as part of multi-model feedback on this design doc. This section represents one model's independent analysis of the options and tradeoffs.*

### My core claim (what I think is actually “best”)

If the product requirement includes **multiple concurrent `vibecheck-vibe` (TUI) sessions** that all appear at **one** URL (`vibecheck.shisa.ai`), then the best architecture is:
- **Hub authoritative** for the phone UI surface (one origin, one API contract).
- **Workers connect outbound** to the hub (no inbound worker ports required).
- **A single worker channel carries both events and commands** as soon as feasible (Option 6 shape), even if we initially implement it with a smaller command set.

That is the cleanest way to guarantee:
- stable PWA assumptions (single origin, existing `/api/sessions/*` and `/ws/events/{sid}` contract)
- robust routing (“approve this call_id in that session goes to the right process”)
- multi-host extensibility (workers can run anywhere that can reach the hub)

### Where I agree with the “Option 1 first” argument

Option 1 (in-process managed sessions) is the fastest path to shipping:
- a working “fleet session picker” UX
- spawn/tear-down semantics (create/delete sessions) with minimal code

So if the immediate goal is “multiple sessions in one URL,” and we can accept PWA-only sessions for some of them, I agree: **Option 1 is a great Phase 1**.

### Where I disagree (the key difference)

Option 1 does **not** solve the hardest stated requirement:
- “run multiple `uv run vibecheck-vibe` sessions” (multiple TUIs, multiple OS processes)
- “connect to all of them from vibecheck.shisa.ai”

Once you require *multiple* concurrently running live TUIs, you need a hub/worker model anyway. The question becomes: **do we build a thin proxy hub (Option 4) or an authoritative hub with a worker event stream (Option 5/6)?**

My strong preference is **authoritative hub + worker stream**, because WS proxying and multi-backend routing tends to be a long tail of operational bugs (disconnect semantics, backpressure, close codes, partial writes, etc.). A single “events-in, commands-out” channel is easier to reason about, test, and evolve.

### Why I would avoid Option 4 (hub proxy) as the “main path”

Hub proxy looks cheaper because workers already expose REST+WS, but in practice it front-loads the wrong complexity:
- you end up debugging a WebSocket proxy under flaky mobile networks
- you still need a registry and per-session routing logic
- you still need coherent `/api/sessions` aggregation and state representation at the hub

The “cheap” part (reusing worker WS) is not where projects fail. They fail at the proxy edges.

### What I would build first (minimal authoritative hub slice)

To satisfy the real requirement (“many TUIs, one URL”), the minimal slice is:
- Worker registers with hub (session_id + metadata).
- Worker streams events to hub (persistent WS).
- Hub broadcasts events to PWA clients (existing room-based WS).
- Hub forwards control actions back to the worker.

For control, I’d aim to do **commands over the same worker WS** early:
- simplest deployment (no worker ports, no firewall work, no localhost-only reverse proxy)
- easiest future multi-host story

If we need an intermediate step for speed, hub->worker HTTP on localhost is acceptable, but only if we keep the event stream as the primary mechanism so we don’t re-architect later.

### Suggested objective “trigger gates” (when to prioritize hub/workers over in-process)

If any of these are true, prioritize Option 5B/6 now (not later):
- We need two or more concurrent live TUIs on the same host and the phone must see both.
- We care about crash isolation between sessions (tools or models occasionally wedge).
- We expect multi-host workers (or even just “run a worker from my laptop to the shared hub”).
- We want push notifications to be consistent across the whole fleet from one origin.

If none are true yet, ship Option 1 first, but keep the API payloads ready for worker ownership fields (`origin`, `worker_id`).

### Bottom line

If “multiple `vibecheck-vibe` TUIs at one URL” is a must-have, then **Option 5B moving toward Option 6** is the best primary path.

If “multiple sessions at one URL” is the goal and TUI-per-session is not urgent, then **Option 1 now + explicit trigger gates for Option 5B** is the pragmatic path.

---

## Phase 2: Hub + Remote Workers (Option 5B)

### When to build this

Build Phase 2 when any of these become true:
- Need crash isolation between sessions.
- Need TUI access for PWA-spawned sessions.
- Need more than ~5 concurrent sessions (memory/GIL pressure).
- Need multi-host deployment.

### Architecture

```
Phone PWA ──HTTPS/WSS──> Caddy ──> Hub (FastAPI, :7870)
                                   ├─ /api/sessions  (aggregated: in-process + remote)
                                   ├─ /ws/events/{sid} (broadcast to PWA clients)
                                   ├─ In-process managed sessions (Phase 1)
                                   └─ Remote worker registry
                                       ├─ Worker A (vibecheck-vibe --hub ...) ──WS──> Hub
                                       ├─ Worker B (vibecheck-vibe --hub ...) ──WS──> Hub
                                       └─ Worker C (hub-spawned, tmux)        ──WS──> Hub
```

### Worker protocol

**Registration (worker -> hub):**
```
WS /ws/workers/register?psk=...&worker_id=...&session_id=...
```

After WebSocket handshake, worker sends:
```json
{
  "type": "register",
  "session_id": "session_20260301_...",
  "capabilities": { "live": true, "tui": true, "controllable": true },
  "metadata": { "title": "...", "agent_name": "default", "started_at": "..." }
}
```

**Event stream (worker -> hub):**
Worker sends JSON `Event` payloads (same schema as PWA receives):
```json
{ "type": "assistant", "content": "Hello!", "ts": "..." }
{ "type": "tool_call", "call_id": "tc_1", "tool_name": "bash", "args": {...}, "ts": "..." }
{ "type": "state_change", "state": "waiting_approval", "ts": "..." }
```

Hub receives these, updates its session registry, stores in backlog, broadcasts to PWA clients in the corresponding room.

**Control commands (hub -> worker):**
Hub sends commands on the same WebSocket:
```json
{ "cmd": "inject_message", "content": "yes, do it" }
{ "cmd": "resolve_approval", "call_id": "tc_1", "approved": true }
{ "cmd": "resolve_input", "request_id": "q_1", "response": "42" }
{ "cmd": "set_auto_approve", "enabled": true }
{ "cmd": "shutdown" }
```

**Heartbeat:**
Both sides send pings every 30s. Hub marks session offline after 90s silence.

### CLI shape

```bash
# Run as hub (serves PWA, accepts workers + in-process sessions):
uv run vibecheck-hub                        # new entry point

# Run as standalone (today's behavior, for dev):
uv run vibecheck-vibe

# Run as worker (registers to hub, forwards events, accepts commands):
uv run vibecheck-vibe --hub http://127.0.0.1:7870

# Hub spawns a worker (if spawn endpoint exists):
curl -X POST http://localhost:7870/api/sessions \
  -H "X-PSK: $VIBECHECK_PSK" \
  -d '{"message": "hello", "spawn": "worker"}'
```

### Hub session registry

```python
class RemoteSession:
    session_id: str
    worker_id: str
    worker_ws: WebSocket          # the worker's upstream connection
    capabilities: dict
    state: BridgeState
    backlog: deque[Event]
    last_seen: float
```

The hub's `SessionManager.list()` merges:
- In-process managed sessions (Phase 1)
- Remote worker sessions (Phase 2)

From the PWA's perspective, nothing changes — same REST/WS contract.

### What this gets us beyond Phase 1

- **Crash isolation:** worker death doesn't kill the hub or other sessions.
- **TUI per session:** each worker process can run its own Textual TUI.
- **TUI attach later:** spawn workers in tmux, SSH in and attach anytime.
- **Memory isolation:** each worker has its own Python heap.

---

## Phase 3: TUI Attach for Spawned Sessions

### The problem

When the hub spawns a session (from PWA "New Session"), how does a human get TUI access?

### Option A: tmux spawn (recommended)

Hub runs:
```bash
tmux new-session -d -s "vibecheck-{session_id}" \
  "uv run vibecheck-vibe --hub http://127.0.0.1:7870 --session-id {session_id}"
```

Operator attaches later:
```bash
ssh vibecheck.shisa.ai
tmux attach -t vibecheck-{session_id}
```

Pros:
- Zero additional infrastructure.
- Full TUI experience.
- Survives SSH disconnect.

Cons:
- Requires SSH access to the host.
- No browser-based TUI access.

### Option B: Web terminal (ttyd/gotty)

Run `ttyd` pointed at the tmux session:
```bash
ttyd -p 8080 tmux attach -t vibecheck-{session_id}
```

Expose via Caddy:
```
vibecheck.shisa.ai/tui/{session_id} {
    reverse_proxy 127.0.0.1:8080
}
```

Pros:
- TUI access from browser — no SSH needed.
- Could integrate directly into the PWA.

Cons:
- Additional dependency (ttyd).
- Security surface (web terminal needs auth).
- Port management for multiple terminals.

### Option C: Headless-only (no TUI attach)

Accept that PWA-spawned sessions are headless. TUI is only for CLI-started sessions.

Pros:
- Simplest.
- PWA provides all the control surface needed.

Cons:
- Loses terminal debugging/inspection for managed sessions.

### Recommendation

Start with **Option A (tmux spawn)** — it's zero-dependency and gives full TUI. Add Option B later if browser-based TUI access becomes a priority.

---

## Spawn / Teardown Summary

| Spawn method | Process model | TUI? | TUI attach later? | Crash isolated? |
|---|---|---|---|---|
| In-process managed (Phase 1) | Same process as hub | No | No | No |
| Worker subprocess, no TUI | Separate process | No | No (could upgrade to tmux) | Yes |
| Worker in tmux (Phase 2/3) | Separate process + PTY | Yes (tmux attach) | **Yes** | Yes |
| Worker with web terminal | Separate process + PTY + ttyd | Yes (browser) | **Yes** | Yes |

---

## Session Identity and Routing

### Session IDs

Vibe's `session_id` is the natural key today. Risks:
- Collision across workers is very unlikely, but possible.

If we want explicit uniqueness, define:
- `public_session_id = "{worker_id}:{vibe_session_id}"`

This is a product/API choice. If we keep raw Vibe session IDs, we accept collision risk. For Phase 1 (in-process), collision is impossible since the `SessionManager` dict enforces uniqueness. For Phase 2, we can namespace if needed.

---

## Hub Responsibilities

Minimum:
- Maintain an in-memory registry of sessions (in-process + remote).
- Provide existing public API contract:
  - `GET /api/sessions`
  - `GET /api/sessions/{sid}`
  - `GET /api/sessions/{sid}/state`
  - `POST /api/sessions/{sid}/message`
  - `POST /api/sessions/{sid}/approve`
  - `POST /api/sessions/{sid}/input`
  - `POST /api/sessions/{sid}/auto-approve`
  - `WS /ws/events/{sid}`
- New endpoints:
  - `POST /api/sessions` (create)
  - `DELETE /api/sessions/{sid}` (teardown)

Nice-to-have:
- Persist registry/backlog (so hub restart doesn't blank the fleet).

---

## Frontend Compatibility

If the hub preserves the existing public contract, the Svelte PWA is **unchanged** for Phase 1 except for the "New Session" / "Delete" buttons.

For Phase 2, if the hub aggregates remote worker sessions into the same `/api/sessions` response, the PWA doesn't need to know whether a session is in-process or remote.

If we introduce `public_session_id` (namespaced IDs), the PWA needs small changes to treat that as the primary `sid` everywhere (URL params, caches, WS path, REST paths).

---

## Resource and Safety Concerns

### Memory (Phase 1, in-process)

Each `AgentLoop` + conversation history: ~100-500MB depending on context window usage. On a typical EC2 instance with 8GB RAM, expect to comfortably run 5-10 concurrent sessions. Beyond that, prefer Phase 2 (separate processes).

### GIL contention (Phase 1)

Vibe's `AgentLoop.act()` is async and I/O-bound (LLM API calls). The GIL is rarely contended in practice since most time is spent in `await`. Tool execution (subprocess calls) also releases the GIL. This should not be a bottleneck for typical session counts.

### Crash domain (Phase 1)

A segfault or unhandled exception in one managed session's tool execution could take down the whole server. Mitigations:
- `try/except` around `_run_agent_turn` (already exists).
- Process-level isolation (Phase 2) for untrusted/risky workloads.

### Working directory isolation

Each `AgentLoop` may execute tools that operate on the filesystem relative to `cwd`. Multiple sessions sharing `cwd` could conflict. Options:
- Accept it (sessions work on different tasks in the same repo — common in practice).
- Per-session `chdir` via `os.chdir` in a thread (fragile, affects whole process).
- Per-session `working_dir` passed to tool execution (requires Vibe internals support).
- Process isolation (Phase 2) — each worker gets its own `cwd`.

---

## CLI / Deployment Shape (Proposed)

Suggested commands/modes:
- `uv run vibecheck-hub` (new): run hub on `:7870` and serve the PWA (Phase 2).
- `uv run vibecheck-vibe` (existing): default behavior stays "standalone" for dev.
- `uv run vibecheck-vibe --hub http://127.0.0.1:7870` (new flag): run as a worker (Phase 2).

For Phase 1, `vibecheck-vibe` continues to work exactly as today — the new managed sessions are just additional `SessionBridge` instances in the same process.

On `vibecheck.shisa.ai`:
- Caddy continues to reverse-proxy `:7870` only.
- Workers are not public; they are internal processes on the host.

---

## Phased Implementation Plan

### Phase 0: Document + align (this doc)
- Decide whether to keep raw `session_id` or introduce `public_session_id`.
- Decide Phase 1 scope (minimal vs. with agent/working_dir config).

### Phase 1: In-process managed sessions (Option 1)
- `POST /api/sessions` + `DELETE /api/sessions/{session_id}` endpoints.
- Frontend "New Session" button + "Delete" on managed sessions.
- Tests for create/delete/inject cycle.
- Verify: start `vibecheck-vibe`, create 2 managed sessions from PWA, interact with all 3.

### Phase 2: Hub + remote workers (Option 5B)
- Worker registration WebSocket endpoint on hub.
- Worker-side event forwarding (bridge emits to upstream WS instead of local ConnectionManager).
- Hub-side control command forwarding.
- `--hub` flag on `vibecheck-vibe` to run as worker.
- Verify: start hub, start 2 workers in separate terminals, all 3 appear in PWA.

### Phase 3: Spawn with TUI attach (Option 5B + tmux)
- Hub subprocess spawner (tmux integration).
- `POST /api/sessions` with `"spawn": "worker"` to create an isolated process.
- Verify: spawn from PWA, SSH in, `tmux attach`, see TUI + PWA side by side.

### Phase 4 (optional): Web terminal
- ttyd/gotty integration for browser-based TUI access.
- `/tui/{session_id}` route in Caddy.

---

## Open Questions

1. Do we need to support connecting to multiple sessions simultaneously from one PWA client, or is "one active session at a time" sufficient?
2. Do we accept Vibe `session_id` collision risk, or should we introduce `public_session_id` now?
3. Is "TUI access from PWA" required, or is "TUI exists via SSH/tmux" acceptable for spawned sessions?
4. Do we want hub registry/backlog persistence (sqlite) or is in-memory acceptable?
5. Should managed sessions (Phase 1) support configurable `agent_name` and `working_dir`, or just use defaults?
6. For Phase 2 workers, should the hub automatically discover local `vibecheck-vibe` processes (e.g. scan ports), or require explicit `--hub` registration?
