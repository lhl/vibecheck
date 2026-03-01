# Multi-Session Plan (vibecheck.shisa.ai as a Hub)

> **Status:** Proposed (design doc)
> **Last updated:** 2026-03-01
>
> **Goal:** Open `https://vibecheck.shisa.ai/` and see + connect to **all** running Vibe sessions we spin up (including multiple concurrent `uv run vibecheck-vibe` terminal sessions).

This document synthesizes the architecture options for multi-session when **each live session requires in-process access to its own `AgentLoop`** (live approvals/input), but we still want **one** public origin and **one** WebSocket API surface for the PWA.

Related docs:
- `docs/PLAN.md` (current roadmap and single-process multi-session design)
- `docs/ANALYSIS-session-attachment.md` (why cross-process live attach is impossible without IPC)

---

## Terminology

- **Hub:** the one public FastAPI server behind Caddy (the only origin the PWA talks to).
- **Worker:** a per-session process that owns a live `AgentLoop` (usually started via `uv run vibecheck-vibe`).
- **Session:** a Vibe conversation identified by `session_id` (and optionally namespaced by worker).

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
   - A separate process cannot resolve another process’s pending Futures without a purpose-built IPC/control channel.

2. **One TCP port ⇢ one server process**
   - Only one process can bind `:7870`.
   - If we want `vibecheck.shisa.ai` to represent the whole fleet, we need a single “front door” service on the public port.

3. **Multiple Textual TUIs implies multiple OS processes**
   - Each session with a terminal UI needs a real TTY (or a PTY via tmux/script/etc.).
   - We should assume “one live TUI session per worker process.”

---

## Target UX / Requirements

Must-have:
- From `vibecheck.shisa.ai`:
  - list all active sessions (“fleet”)
  - connect to a chosen session and see live events
  - send a message, approve/deny tool calls, answer questions
- Sessions started in terminals (`vibecheck-vibe`) should appear automatically.

Nice-to-have:
- Start (spawn) new sessions from the PWA.
- Stop (tear down) sessions from the PWA.
- Optional: TUI access for PWA-spawned sessions (likely via tmux + SSH, or a web terminal).

Non-goals (for now):
- Perfect load balancing across machines.
- Multi-tenant auth (PSK remains the security boundary).

---

## Options

### Option 0: Status Quo (One `vibecheck-vibe` per host)

How it works:
- Run exactly one `vibecheck-vibe` on `:7870`.

Pros:
- No new code.
- Matches current demo path.

Cons:
- Does not satisfy “run as many sessions as we want.”

---

### Option 1: Multiple Ports + User Chooses Port (No Hub)

How it works:
- Run N `vibecheck-vibe` processes on `:7871`, `:7872`, ...
- Operator manually navigates to different origins/ports.

Pros:
- Very low engineering cost.

Cons:
- Fails the primary goal: one `vibecheck.shisa.ai` surface aggregating all sessions.
- Push notifications and “session picker” become fragmented per origin.

---

### Option 2: Reverse Proxy Trickery (Path/Subdomain per Session)

How it works:
- Run multiple backends on different ports.
- Configure Caddy/Nginx to route:
  - `/ws/events/{session_id}` to the right backend
  - `/api/sessions/...` to the right backend

Pros:
- Keep workers unchanged.

Cons:
- Needs a dynamic routing table keyed by `session_id`.
- Caddy config is static by default; dynamic per-session routing is non-trivial.
- Still needs an aggregator for `/api/sessions` (each backend only knows itself).

Verdict:
- Not recommended as the primary plan. It punts the hard part (dynamic registry) to the proxy layer.

---

### Option 3: Hub + Worker Servers (Hub Proxies to Workers)

How it works:
- Run a **hub** server on `:7870` (public, behind Caddy).
- Run N **workers** (each `vibecheck-vibe`) on internal ports (`127.0.0.1:7871+`).
- Each worker registers itself with the hub:
  - `session_id`
  - worker base URL (control plane)
  - capabilities (live controllable, has TUI, etc.)
- The hub:
  - serves PWA
  - exposes `/api/sessions` aggregated across workers
  - terminates client WebSockets at `/ws/events/{session_id}`
  - proxies streaming events from the correct worker to the client
  - proxies REST actions (`approve`, `input`, `message`, `auto-approve`) to the worker

Pros:
- Minimal conceptual change to existing worker: it can keep its REST + WS stack.
- Hub is a “single origin” for the PWA, satisfying the main requirement.

Cons:
- Hub must implement a reliable WS proxy/bridge per active session.
- Two sources of truth for session state/backlog (worker vs hub) unless the hub stays stateless.
- Requires internal networking (hub must reach worker ports).

Best fit:
- Good stepping stone if we want a quick win with minimal worker refactors.

---

### Option 4: Hub is Authoritative; Workers Forward Events (Recommended)

How it works:
- Run **one** public hub (`:7870`) that is the only server the PWA ever talks to.
- Each live session runs in a **worker** process that owns the `AgentLoop`.
- Workers do NOT need to expose a public WS endpoint for clients.
- Instead:
  - Worker forwards every `Event` to hub (push model).
  - Hub stores per-session backlog and broadcasts to connected PWA clients at `/ws/events/{session_id}`.
  - For control actions, hub forwards commands to the owning worker (HTTP) or via a dedicated control channel.

Two sub-variants:
- **4A: Worker -> Hub via HTTP POST**
  - simplest implementation
  - noisier (many requests) and easier to overload
- **4B: Worker -> Hub via persistent WebSocket (preferred)**
  - efficient, backpressure-friendly
  - hub can detect disconnects quickly (marks session offline)

Pros:
- Hub becomes the single source of truth for:
  - what the PWA sees
  - backlog
  - push notifications (hub sees events directly)
- No WS proxying complexity (hub is the WS server; workers are event publishers).
- Extends naturally to multi-host in the future (workers connect out to the hub).

Cons:
- Requires new “worker protocol” (registration + event stream + optional control channel).
- Requires some refactor so `vibecheck-vibe` can run as a worker (and not as the public server).

Verdict:
- This is the cleanest long-term design for “many sessions, one vibecheck.shisa.ai.”

---

### Option 5: Full Worker Control Channel (No Worker Ports)

How it works:
- Workers connect to hub over a single outbound WebSocket:
  - send events upstream
  - receive control commands downstream (inject message, resolve approval, etc.)
- Workers do not need to bind any TCP ports.

Pros:
- Simplifies networking and firewalling.
- Best for distributed workers (multiple machines).

Cons:
- More protocol work up front (command routing, acks, retries, idempotency).

Verdict:
- Good “v2” of Option 4B once the hub/worker split is proven.

---

### Option 6: tmux/PTY Sidecar (Terminal Scraping Fallback)

How it works:
- Run normal `vibe` sessions in tmux panes.
- Sidecar scrapes terminal output + injects keystrokes for approvals.

Pros:
- Works even if Vibe internals change, as long as the UI is scriptable.

Cons:
- Not typed events, fragile parsing, hard to keep state correct.
- Worst UX and highest maintenance.

Verdict:
- Fallback only (already documented elsewhere).

---

### Option 7: Upstream ACP / Native IPC (Wait for Vibe Support)

How it works:
- Use (or contribute) an upstream control protocol that supports attaching to an already-running session.

Pros:
- Most robust long-term if upstream commits to stable APIs.

Cons:
- Out of our direct control and schedule.
- Not available in Vibe today for “attach to an existing running AgentLoop.”

Verdict:
- Keep an eye on it, but plan as if it won’t land in time.

---

## Recommended Direction

Primary target:
- **Option 4B: Hub authoritative, workers forward events over a persistent connection**

Fastest incremental path:
1. Implement Option 3 (hub + worker registration + hub-forwarded REST) OR a minimal Option 4A (HTTP POST forwarding) to prove the end-to-end UX.
2. Upgrade to Option 4B (persistent worker-to-hub WS) for performance and reliability.
3. Add Option 5-style downstream control over the same channel (remove worker ports).

---

## Proposed Architecture (Option 4B)

### High-level diagram

```
Phone PWA ──HTTPS/WSS──> Caddy ──> Hub (FastAPI, :7870)
                                   ├─ /api/sessions  (aggregated)
                                   ├─ /ws/events/{sid} (broadcast)
                                   └─ (push notifications, optional)

Terminal A: uv run vibecheck-vibe ──(WS/HTTP out)──> Hub
Terminal B: uv run vibecheck-vibe ──(WS/HTTP out)──> Hub
Terminal C: uv run vibecheck-vibe ──(WS/HTTP out)──> Hub
```

### Key idea

- The hub owns the **client-facing** WebSocket rooms.
- Workers own the **live** `AgentLoop` and produce events.
- Hub routes control actions to the owning worker.

---

## Session Identity and Routing

### Session IDs

Vibe’s `session_id` is the natural key today. Risks:
- Collision across workers is very unlikely, but possible.

If we want explicit uniqueness, define:
- `public_session_id = "{worker_id}:{vibe_session_id}"`

This would require:
- PWA uses `public_session_id` everywhere.
- Hub maps `public_session_id -> worker_id -> vibe_session_id`.

This is a product/API choice. If we keep raw Vibe session IDs, we accept collision risk.

---

## Hub Responsibilities

Minimum:
- Maintain an in-memory registry of sessions:
  - `session_id`, `worker_id`, `connected`, `last_seen`, `title`, `started_at`, `state`, `controllable`, `auto_approve`
- Provide existing public API contract:
  - `GET /api/sessions`
  - `GET /api/sessions/{sid}`
  - `GET /api/sessions/{sid}/state`
  - `POST /api/sessions/{sid}/message`
  - `POST /api/sessions/{sid}/approve`
  - `POST /api/sessions/{sid}/input`
  - `POST /api/sessions/{sid}/auto-approve`
  - `WS /ws/events/{sid}`

Nice-to-have:
- Persist registry/backlog (so hub restart doesn’t blank the fleet).

---

## Frontend Compatibility

If the hub preserves the existing public contract:
- REST: `/api/sessions`, `/api/sessions/{sid}/...`
- WS: `/ws/events/{sid}`

Then the Svelte PWA can remain “single-origin” and unchanged. Session aggregation becomes a backend concern only.

If we introduce `public_session_id` (namespaced IDs), the PWA needs small changes to treat that as the primary `sid` everywhere (URL params, caches, WS path, REST paths).

---

## Worker Responsibilities

Minimum:
- Create the live `AgentLoop` + `SessionBridge` (same as today).
- Register with hub after determining `session_id`.
- Forward events to hub.
- Accept control actions from hub (either via HTTP endpoints or control channel).

TUI requirements:
- A worker started by a human in SSH already has a TTY.
- A worker spawned by the hub needs a PTY strategy (see Spawn/Tear-down section).

---

## Worker Registration and Event Transport (Proposed)

This is intentionally “plan-level” and not final API design.

### Registration

Worker -> Hub:
- register: `POST /api/workers/register`
  - `worker_id` (uuid)
  - `session_id`
  - `capabilities`: `{ live: true, tui: true, controllable: true }`
  - `metadata`: `{ title, started_at }`

### Event stream

Worker -> Hub:
- persistent websocket: `WS /ws/workers/{worker_id}`
  - worker sends JSON `Event` payloads (same schema as PWA expects)
  - hub acks and updates session state/backlog

### Control actions

Hub -> Worker:
- Phase 1: hub calls worker’s private HTTP server endpoints (proxy existing REST).
- Phase 2: hub sends commands on the worker control channel:
  - `inject_message`
  - `resolve_approval`
  - `resolve_input`
  - `set_auto_approve`

---

## Spawn / Tear-Down (Future)

### Spawn goals

From PWA:
- “New session” button
- choose agent/profile/toolset
- optional initial prompt
- decide whether it needs a TUI

### Spawn implementation options

Option A: Headless managed sessions (no TUI)
- Hub spawns/owns an `AgentLoop` in-process (today’s “managed” mode).
- Lowest friction, no PTY requirements.
- Does not satisfy “TUI access” but satisfies “more sessions.”

Option B: Spawn workers without UI (still separate processes)
- Hub spawns `vibecheck-worker` processes that run an AgentLoop without Textual.
- Keeps isolation benefits while avoiding PTY complexity.

Option C: Spawn TUI workers in tmux
- Hub runs: `tmux new-session -d -s vibecheck-{id} uv run vibecheck-vibe --worker ...`
- Operator can SSH and attach to tmux session for TUI.
- Optional add-on: web terminal (ttyd/wetty) if we want TUI access via browser.

### Tear-down

For managed sessions:
- Hub can cancel tasks / detach bridges.

For worker sessions:
- Hub can send a “shutdown” command to worker.
- Or hub can send SIGTERM to a tracked PID (local-only).

---

## Phased Implementation Plan (Concrete)

Phase 0: Document + align (this doc)
- Decide whether to keep raw `session_id` or introduce `public_session_id`.

Phase 1: Multi-session visible at one origin (quick win)
- Add a hub server mode that can aggregate sessions.
- Add worker registration.
- Choose one transport:
  - Option 3 (hub proxies) if we want minimal worker changes, or
  - Option 4A (worker HTTP POST forward) if we want hub-authoritative quickly.
- Verify:
  - start two `vibecheck-vibe` workers in two SSH terminals
  - both appear in `GET /api/sessions` on the hub
  - PWA can switch between them and control each

Phase 2: Reliable event transport (upgrade)
- Replace HTTP forward with persistent worker WS (Option 4B).
- Add heartbeats and disconnect semantics.
- Hub becomes authoritative for backlog/state.

Phase 3: Spawn/tear-down (headless first)
- Add hub endpoint to create “managed” sessions (no TUI).
- Add tear-down support.

Phase 4: Spawn/tear-down with TUI (optional)
- Implement tmux-spawned workers.
- Provide operator workflow for TUI access (SSH attach) or web terminal integration.

---

## CLI / Deployment Shape (Proposed)

This is a packaging detail, but it affects how we roll it out safely.

Suggested commands/modes:
- `uv run vibecheck-hub` (new): run hub on `:7870` and serve the PWA.
- `uv run vibecheck-vibe` (existing): default behavior stays “standalone” for dev.
- `uv run vibecheck-vibe --hub http://127.0.0.1:7870` (new flag): run as a worker.
  - registers to hub
  - forwards events to hub
  - accepts commands from hub (HTTP or control channel)
  - binds worker ports only on localhost (or not at all if Option 5)

On `vibecheck.shisa.ai`:
- Caddy continues to reverse-proxy `:7870` only.
- Workers are not public; they are internal processes on the host (at least initially).

---

## Open Questions

1. Do we need to support connecting to multiple sessions simultaneously from one PWA client, or is “one active session at a time” sufficient?
2. Do we accept Vibe `session_id` collision risk, or should we introduce `public_session_id` now?
3. Is “TUI access from PWA” required, or is “TUI exists via SSH/tmux” acceptable for spawned sessions?
4. Do we want hub registry/backlog persistence (sqlite) or is in-memory acceptable for hackathon/demo?
