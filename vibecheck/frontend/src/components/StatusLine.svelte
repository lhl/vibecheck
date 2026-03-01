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
  {#if yoloEnabled}
    <span class="yolo-marker">YOLO</span>
  {:else}
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
  {/if}
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
    justify-content: center;
    background: #f7d046;
    border-top-color: #111;
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

  .yolo-marker {
    background: #111;
    color: #f7d046;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 0.1rem 0.7rem;
    border: 1px solid #111;
    line-height: 1.1;
  }
</style>
