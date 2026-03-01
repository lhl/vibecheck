<script>
  export let agentState = 'unknown'
  export let sessionError = ''
  export let onSettingsToggle = null
  export let settingsOpen = false
  export let costDisplay = '--'

  const stateColors = {
    idle: '#555',
    running: '#EF7D31',
    waiting_approval: '#F7D046',
    waiting_input: '#F7D046',
  }

  $: dotColor = stateColors[agentState] || '#555'
  $: stateLabel = agentState.replace(/_/g, ' ')
</script>

<div
  class="status-line"
  on:click={onSettingsToggle}
  role="button"
  tabindex="0"
  on:keydown={(e) => e.key === 'Enter' && onSettingsToggle?.()}
  data-testid="status-line"
>
  <div class="left">
    <span class="dot" style="background: {dotColor}" aria-hidden="true"></span>
    <span class="state-label">{stateLabel}</span>
    {#if sessionError}
      <span class="error-hint" title={sessionError}>!</span>
    {/if}
  </div>
  <div class="right">
    <span class="cost">{costDisplay}</span>
    <span class="caret">{settingsOpen ? '▼' : '▲'}</span>
  </div>
</div>

<style>
  .status-line {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.35rem 0.75rem;
    background: #222;
    border-top: 1px solid var(--card-border);
    cursor: pointer;
    user-select: none;
    min-height: 32px;
    font-size: 0.75rem;
  }

  .left, .right {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .state-label {
    color: var(--text-muted);
    text-transform: lowercase;
  }

  .error-hint {
    color: var(--error);
    font-weight: 800;
  }

  .cost {
    color: var(--text-muted);
  }

  .caret {
    color: var(--text-muted);
    font-size: 0.6rem;
  }
</style>
