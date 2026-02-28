<script>
  export let status = 'disconnected'
  export let reconnectAttempts = 0

  const statusCopy = {
    connected: 'Connected',
    connecting: 'Reconnecting',
    disconnected: 'Disconnected',
  }

  $: label = statusCopy[status] || 'Disconnected'
</script>

<div class="connection-status">
  <span data-testid="connection-dot" class="dot {status}" aria-hidden="true"></span>
  {#if status === 'connecting' && reconnectAttempts > 0}
    <span>{label} ({reconnectAttempts})</span>
  {:else}
    <span>{label}</span>
  {/if}
</div>

<style>
  .connection-status {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.82rem;
    font-weight: 600;
    color: #d8dfef;
  }

  .dot {
    width: 0.6rem;
    height: 0.6rem;
    border-radius: 999px;
    background: #d85c5c;
    box-shadow: 0 0 0 3px rgb(216 92 92 / 0.2);
  }

  .dot.connected {
    background: #1fbe76;
    box-shadow: 0 0 0 3px rgb(31 190 118 / 0.22);
  }

  .dot.connecting {
    background: #e3aa32;
    box-shadow: 0 0 0 3px rgb(227 170 50 / 0.22);
  }
</style>
