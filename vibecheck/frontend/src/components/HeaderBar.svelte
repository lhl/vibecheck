<script>
  import ConnectionStatus from './ConnectionStatus.svelte'

  export let connectionStatus = 'disconnected'
  export let reconnectAttempts = 0
  export let activeSessionTitle = ''
  export let pickerOpen = false
  export let onTogglePicker = null
</script>

<header class="header-bar" on:click={onTogglePicker} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && onTogglePicker?.()}>
  <span class="logo">vibecheck</span>
  <span class="session-label">{activeSessionTitle || 'No session'}</span>
  <ConnectionStatus status={connectionStatus} {reconnectAttempts} />
</header>

<style>
  .header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--card-border);
    background: var(--card-bg);
    cursor: pointer;
    user-select: none;
    min-height: 44px;
  }

  .logo {
    font-weight: 800;
    font-size: 1rem;
    letter-spacing: 0.02em;
    color: var(--fg);
  }

  .session-label {
    font-size: 0.78rem;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 40%;
    text-align: center;
  }
</style>
