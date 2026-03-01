<script>
  export let sessions = []
  export let activeSessions = []
  export let olderSessions = []
  export let sessionId = ''
  export let sessionsLoading = false
  export let sessionError = ''
  export let resumeBusy = ''
  export let open = false
  export let onSwitchSession = null
  export let onResumeSession = null
  export let onRefresh = null
  export let onSessionInput = null
  export let onConnect = null
  export let onDisconnect = null
  export let isConnectableSession = () => false

  function sessionTitle(session) {
    if (session?.message_count === 0) return 'New session'
    const title = session?.title
    if (typeof title === 'string' && title.trim()) return title.trim()
    return 'New session'
  }

  function sessionIdPreview(id) {
    if (typeof id !== 'string') return ''
    const trimmed = id.trim()
    if (trimmed.length <= 10) return trimmed
    return `${trimmed.slice(0, 8)}…`
  }

  function formatRelative(value) {
    if (!value || typeof value !== 'string') return ''
    const ms = Date.parse(value)
    if (!Number.isFinite(ms)) return ''
    const deltaSeconds = Math.max(0, Math.floor((Date.now() - ms) / 1000))
    if (deltaSeconds < 60) return `${deltaSeconds}s ago`
    const minutes = Math.floor(deltaSeconds / 60)
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    return `${days}d ago`
  }

  function statusBadge(session) {
    const status = session?.status || ''
    if (status === 'waiting_approval' || status === 'waiting_input') return 'waiting'
    if (status === 'running') return 'running'
    if (status === 'idle') return 'idle'
    return status || 'unknown'
  }
</script>

<div class="session-picker" class:open>
  <div class="picker-inner">
    <div class="session-header">
      <h2>Sessions</h2>
      <button type="button" class="secondary" on:click={onRefresh} disabled={sessionsLoading}>
        {sessionsLoading ? 'Refreshing…' : 'Refresh'}
      </button>
    </div>

    {#if activeSessions.length > 0}
      <p class="section-label">Active</p>
      <ul class="session-list" aria-label="Active sessions">
        {#each activeSessions as session}
          <li>
            <button
              type="button"
              class="session-item"
              class:selected={session.id === sessionId}
              on:click={() => onSwitchSession?.(session.id)}
            >
              <div class="row">
                <span class="session-title">{sessionTitle(session)}</span>
                <span class="status {statusBadge(session)}">{statusBadge(session)}</span>
              </div>
              <div class="row meta-line">
                <span class="meta">started {formatRelative(session.started_at || session.last_activity)}</span>
                {#if session.last_activity}
                  <span class="meta">active {formatRelative(session.last_activity)}</span>
                {/if}
                <span class="meta">{session.message_count || 0} msgs</span>
                <span class="meta mono" title={session.id}>{sessionIdPreview(session.id)}</span>
              </div>
            </button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="meta">No active sessions detected.</p>
    {/if}

    <details class="older-sessions">
      <summary>Browse older sessions</summary>
      {#if olderSessions.length === 0}
        <p class="meta">No older sessions found.</p>
      {:else}
        <ul class="session-list" aria-label="Older sessions">
          {#each olderSessions as session}
            <li class="session-old">
              <div class="session-old-meta">
                <p class="session-old-title">{sessionTitle(session)}</p>
                <p class="meta">
                  started {formatRelative(session.started_at || session.last_activity)}
                  {#if session.last_activity}
                    · active {formatRelative(session.last_activity)}
                  {/if}
                  · {session.message_count || 0} msgs
                </p>
                <p class="meta mono" title={session.id}>{sessionIdPreview(session.id)}</p>
              </div>
              <button
                type="button"
                class="secondary"
                on:click={() => onResumeSession?.(session.id)}
                disabled={resumeBusy === session.id}
              >
                {resumeBusy === session.id ? 'Resuming…' : 'Resume'}
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </details>

    <details class="advanced">
      <summary>Advanced</summary>
      <label for="session-id">Session ID</label>
      <input
        id="session-id"
        value={sessionId}
        placeholder="Session ID"
        on:change={onSessionInput}
      />
      <div class="control-actions">
        <button
          type="button"
          on:click={onConnect}
          disabled={!sessionId || !isConnectableSession(sessionId)}
        >
          Connect
        </button>
        <button type="button" class="secondary" on:click={onDisconnect}>Disconnect</button>
      </div>
    </details>

    {#if sessionError}
      <p class="error">{sessionError}</p>
    {/if}
  </div>
</div>

<style>
  .session-picker {
    flex-shrink: 1;
    min-height: 0;
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease;
  }

  .session-picker.open {
    max-height: 60vh;
    overflow-y: auto;
  }

  .picker-inner {
    padding: 0.75rem;
    border-bottom: 1px solid var(--card-border);
    background: var(--card-bg);
    display: grid;
    gap: 0.45rem;
  }

  .session-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
  }

  .session-header h2 {
    margin: 0;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .section-label {
    margin: 0.35rem 0 0;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--label);
  }

  .session-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.45rem;
  }

  .session-item {
    width: 100%;
    text-align: left;
    padding: 0.65rem;
    border: 1px solid var(--session-border);
    background: var(--session-bg);
    color: inherit;
    border-radius: 2px;
    display: grid;
    gap: 0.35rem;
    cursor: pointer;
    font: inherit;
  }

  .session-item.selected {
    border-color: var(--session-selected);
    box-shadow: 0 0 0 1px var(--session-selected);
  }

  .row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
  }

  .meta-line {
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .session-title {
    font-weight: 700;
    font-size: 0.88rem;
  }

  .status {
    border: 1px solid var(--session-status-idle);
    background: color-mix(in srgb, var(--session-status-idle) 18%, transparent);
    color: var(--fg);
    border-radius: 2px;
    padding: 0.1rem 0.55rem;
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    flex: 0 0 auto;
  }

  .status.waiting {
    border-color: var(--session-status-waiting);
    background: color-mix(in srgb, var(--session-status-waiting) 18%, transparent);
  }

  .status.running {
    border-color: var(--session-status-running);
    background: color-mix(in srgb, var(--session-status-running) 18%, transparent);
  }

  .status.idle {
    border-color: var(--session-status-idle);
    background: color-mix(in srgb, var(--session-status-idle) 18%, transparent);
  }

  .mono {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    word-break: break-all;
  }

  details {
    border: 1px solid var(--session-border);
    background: var(--session-bg);
    border-radius: 2px;
    padding: 0.6rem;
  }

  summary {
    cursor: pointer;
    list-style: none;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--label);
  }

  summary::-webkit-details-marker {
    display: none;
  }

  .session-old {
    display: flex;
    gap: 0.6rem;
    justify-content: space-between;
    align-items: flex-start;
  }

  .session-old-meta {
    display: grid;
    gap: 0.2rem;
    min-width: 0;
  }

  .session-old-title {
    margin: 0;
    font-weight: 800;
    font-size: 0.85rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--label);
  }

  input {
    min-height: 40px;
    border-radius: 2px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    color: var(--input-fg);
    padding: 0 0.7rem;
    font: inherit;
  }

  .control-actions {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.45rem;
    margin-top: 0.3rem;
  }

  button {
    min-height: 40px;
    border-radius: 2px;
    border: 1px solid var(--primary-border);
    background: var(--primary-bg);
    color: var(--primary-fg);
    font-weight: 700;
    font: inherit;
    font-weight: 700;
  }

  button.secondary {
    border-color: var(--secondary-border);
    background: var(--secondary-bg);
    color: var(--secondary-fg);
  }

  button:disabled {
    opacity: 0.58;
  }

  .meta,
  .error {
    margin: 0;
    font-size: 0.76rem;
  }

  .meta {
    color: var(--meta);
  }

  .error {
    color: var(--error);
  }
</style>
