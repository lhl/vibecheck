<script>
  export let agentState = 'unknown'
  export let sessionError = ''
  export let onSettingsToggle = null
  export let settingsOpen = false
  export let costDisplay = '--'
  export let yoloEnabled = false

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
  class:yolo-active={yoloEnabled}
  on:click={onSettingsToggle}
  role="button"
  tabindex="0"
  on:keydown={(e) => e.key === 'Enter' && onSettingsToggle?.()}
  data-testid="status-line"
>
  <div class="left">
    {#if yoloEnabled}
      <span class="yolo-label">YOLO</span>
    {:else}
      <span class="dot" style="background: {dotColor}" aria-hidden="true"></span>
      <span class="state-label">{stateLabel}</span>
      {#if sessionError}
        <span class="error-hint" title={sessionError}>!</span>
      {/if}
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

  .status-line.yolo-active {
    background: #f7d046;
    border-top-color: #111;
  }

  .status-line.yolo-active .cost,
  .status-line.yolo-active .caret {
    color: #111;
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

  .yolo-label {
    color: #111;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
</style>
