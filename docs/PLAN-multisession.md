# Multi-Session Plan for `vibecheck.shisa.ai`

> **Status:** Draft (open alternatives)  
> **Last updated:** 2026-03-01  
> **Goal:** From one public URL (`https://vibecheck.shisa.ai`), list and control all active Vibe sessions, and later spawn/tear down sessions with both TUI and PWA access.

---

## 1) Problem Statement

Today, each `uv run vibecheck-vibe` process owns:
- one in-process live `AgentLoop`,
- one in-process `SessionManager`,
- one WebSocket server (default `:7870`).

That gives great same-process control for one live session, but no single shared control plane across multiple `vibecheck-vibe` processes.

---

## 2) Requirements

## Functional
- One public entrypoint (`vibecheck.shisa.ai`) for all sessions.
- Show all controllable sessions (live + resumed/managed).
- Connect PWA to any session’s real-time event stream.
- Route `approve`, `input`, and `message` actions to the correct session/process.
- Support both:
  - manually started sessions,
  - system-spawned sessions (future).
- Future: create/stop sessions from PWA while preserving optional terminal TUI access.

## Non-Functional
- Keep current mobile API stable where possible (`/api/sessions`, `/ws/events/{id}`).
- Avoid exposing worker ports publicly.
- Recover from worker restarts (heartbeat + stale session cleanup).
- Keep security split between public client auth and internal worker auth.

---

## 3) Option Set

## Option A — **Hub + Worker Mesh (Recommended target)**

Run a central **Hub** at `vibecheck.shisa.ai` and N **Worker** processes (each worker is a `vibecheck-vibe` session host).

- Hub responsibilities:
  - global session registry (`global_session_id -> worker + local_session_id`),
  - fan-out WebSocket events to clients,
  - route action APIs to owning worker,
  - optional spawn/stop orchestration.
- Worker responsibilities:
  - own live `AgentLoop` + TUI + local bridge callbacks,
  - stream events to hub,
  - execute routed actions for local sessions.

**Pros**
- Preserves same-process callback correctness per session.
- Scales to many sessions and potentially many hosts.
- Clean path to spawn/teardown and policy controls.

**Cons**
- Highest implementation effort.
- Requires internal protocol + lifecycle management.

---

## Option B — **Caddy Fan-Out to Many Independent Servers**

Run multiple independent `vibecheck-vibe` instances on different ports/subdomains and route traffic with Caddy.

Example:
- `vibecheck.shisa.ai/s/session-a/* -> :7871`
- `vibecheck.shisa.ai/s/session-b/* -> :7872`

**Pros**
- Fastest to stand up.
- Minimal backend refactor.

**Cons**
- No real global session list without extra aggregator.
- PWA must understand per-session base paths or route prefixes.
- Harder to add robust spawn/stop + worker health.

---

## Option C — **Message Broker Backbone (Hub + Redis/NATS)**

Like Option A, but workers publish events to a broker and hub consumes.

**Pros**
- Better decoupling, replay, and durability options.
- Easier multi-host scale.

**Cons**
- Extra infra and operational complexity.
- Overkill for short-term single-host deployment.

---

## Option D — **Single Supervisor Process, Multi-Session In-Process**

One supervisor process creates and owns multiple managed `AgentLoop`s directly.

**Pros**
- Simple control plane.
- No inter-process routing.

**Cons**
- Hard to provide true per-session terminal TUI parity.
- Large architectural shift away from current `vibecheck-vibe` model.

---

## Option E — **tmux/PTY Bridging Fallback**

Treat sessions as terminal processes and bridge via PTY/tmux.

**Pros**
- Works with almost any CLI session model.

**Cons**
- Loses typed event/callback advantages.
- More brittle and lower-fidelity approvals/input handling.

---

## 4) Decision Matrix (Initial)

| Option | Time to First Value | Long-Term Fit | TUI + PWA Parity | Operational Complexity |
|---|---:|---:|---:|---:|
| A: Hub + Workers | Medium | High | High | Medium |
| B: Caddy Fan-Out | High | Low-Medium | Medium | Low |
| C: Broker Backbone | Low-Medium | High | High | High |
| D: Single Supervisor | Medium | Medium | Low-Medium | Medium |
| E: PTY Fallback | Medium | Low | Low | Medium |

**Working recommendation:**  
- **Short term:** Option B if we need immediate multi-instance access with minimal code.  
- **Target architecture:** Option A for a correct, scalable control plane and spawn/stop support.

---

## 5) Recommended Target Architecture (Option A)

## Public Surface (unchanged for PWA)
- `GET /api/sessions`
- `GET /api/sessions/{id}`
- `POST /api/sessions/{id}/approve`
- `POST /api/sessions/{id}/input`
- `POST /api/sessions/{id}/message`
- `WS /ws/events/{id}`

Hub resolves `{id}` to owning worker and forwards action/event traffic.

## Internal Worker Protocol (new)
- Worker registration:
  - `POST /internal/workers/register`
  - payload: worker identity, capabilities, currently hosted sessions.
- Heartbeats:
  - `POST /internal/workers/{worker_id}/heartbeat`
- Event ingress:
  - worker->hub stream (WS or HTTP batched events).
- Action routing:
  - hub->worker private endpoint(s) for approve/input/message.

## Session Identity
- Keep current Vibe `session_id`, but store composite key internally:
  - `global_session_key = {worker_id}:{session_id}`
- Public API can continue exposing plain `session_id` if guaranteed unique, otherwise move to opaque `id` and keep raw IDs in metadata.

## Security
- Public auth: existing PSK (`VIBECHECK_PSK`).
- Worker auth: separate internal token/mTLS (do not reuse public PSK).
- Network: workers on private network only; no public worker ports.

---

## 6) Spawn / Teardown with TUI + PWA (Future)

## Spawn
- Add `POST /api/sessions` on hub.
- Hub asks local supervisor to start a worker/session.
- Recommended runtime for TUI access: start in `tmux` with deterministic session name.
- Return:
  - session id,
  - attach metadata (`ssh ...; tmux attach -t <name>`),
  - PWA connectability status.

## Teardown
- Add `DELETE /api/sessions/{id}` on hub.
- Route to worker/supervisor for graceful stop:
  - SIGTERM,
  - timeout,
  - SIGKILL fallback.

## TUI Access Model
- **Operator TUI:** SSH + tmux attach to spawned session.
- **PWA control:** unchanged via hub API/WS.
- Future optional enhancement: browser terminal bridge for TUI view/control.

---

## 7) Incremental Rollout Plan

## Milestone M0 — Immediate Multi-Instance Access (fast path)
- Run multiple `vibecheck-vibe` instances on different ports.
- Configure Caddy routing strategy (subdomain or path prefix).
- Manual session mapping doc + operational runbook.

## Milestone M1 — Hub Read Aggregation
- Introduce central hub service with worker registry + health.
- Aggregate session list across workers (`GET /api/sessions` unified).
- Keep control actions temporarily direct or partially routed.

## Milestone M2 — Full Routed Control
- Route approve/input/message via hub.
- Route WS events via hub with per-session fan-out.
- Add stale worker/session eviction and reconnect handling.

## Milestone M3 — Orchestration
- Implement `POST /api/sessions` and `DELETE /api/sessions/{id}`.
- Add supervisor integration + tmux-backed TUI spawn.
- Add quota/policy limits (max sessions, per-user caps).

## Milestone M4 — Hardening
- Worker auth hardening (token rotation / mTLS).
- Audit logging for routed actions.
- Load/perf testing, failure-mode tests, and rollout guardrails.

---

## 8) Open Questions

- Should public session IDs remain raw Vibe IDs or become hub-issued opaque IDs?
- Single-host only first, or design for multi-host workers immediately?
- Should worker->hub event transport be persistent WS or HTTP batch with retries?
- Do we require browser-based TUI remoting, or is SSH/tmux sufficient for initial “TUI access”?
- What policy should govern auto-spawned sessions (TTL, idle timeout, max concurrent)?

---

## 9) Definition of Done (for this initiative)

- From `https://vibecheck.shisa.ai`, a user can:
  - see all active sessions,
  - connect to any session stream,
  - approve/input/message any session correctly.
- System can optionally spawn and tear down sessions via API.
- Spawned sessions are reachable from both:
  - PWA control plane,
  - operator terminal TUI path.

