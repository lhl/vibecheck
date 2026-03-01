<script>
  export let toolCall
  export let result = null
  export let sessionId = ''
  export let psk = ''

  let expanded = false
  let diffBusy = false
  let diffError = ''
  let diffPayload = null
  let showDiff = false

  $: argsJson = JSON.stringify(toolCall?.args || {}, null, 2)
  $: argsPreview = argsJson.replaceAll('\n', ' ').slice(0, 140)
  $: resultOutput = result?.output || ''
  $: hasError = Boolean(result?.is_error)
  $: canShowDiff =
    Boolean(sessionId && psk && toolCall?.call_id) &&
    (toolCall?.tool_name === 'write_file' || toolCall?.tool_name === 'search_replace')

  function toggleExpanded() {
    expanded = !expanded
  }

  async function toggleDiff() {
    if (!canShowDiff || diffBusy) {
      return
    }

    diffError = ''

    if (showDiff) {
      showDiff = false
      return
    }

    if (diffPayload) {
      showDiff = true
      return
    }

    diffBusy = true
    try {
      const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/diffs`, {
        headers: { 'X-PSK': psk },
      })
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`)
      }
      const payload = await response.json()
      const diffs = Array.isArray(payload) ? payload : []
      const match = diffs.find((entry) => entry?.call_id === toolCall.call_id) || null
      if (!match) {
        throw new Error('Diff not available yet.')
      }
      diffPayload = match
      showDiff = true
    } catch (error) {
      diffError = error instanceof Error ? error.message : 'Diff fetch failed'
    } finally {
      diffBusy = false
    }
  }
</script>

<article data-testid="tool-call-card" class="tool-call-card" class:error={hasError}>
  <button type="button" class="toggle" on:click={toggleExpanded} aria-expanded={expanded}>
    <span class="badge">{toolCall?.tool_name || 'tool'}</span>
    <span class="preview">{argsPreview}</span>
  </button>

  {#if expanded}
    <pre>{argsJson}</pre>
  {/if}

  {#if result}
    <section class="result" class:error={hasError}>
      <h4>Result</h4>
      <pre>{resultOutput}</pre>
    </section>
  {/if}

  {#if canShowDiff}
    <section class="diff" class:visible={showDiff}>
      <button type="button" class="secondary diff-toggle" on:click={toggleDiff} disabled={diffBusy}>
        {showDiff ? 'Hide diff' : diffPayload ? 'Show diff' : diffBusy ? 'Loading diff…' : 'Load diff'}
      </button>
      {#if diffError}
        <p class="error">{diffError}</p>
      {/if}
      {#if showDiff && diffPayload}
        <pre>{diffPayload.unified_diff || ''}</pre>
      {/if}
    </section>
  {/if}
</article>

<style>
  .tool-call-card {
    border: 1px solid var(--card-border);
    border-radius: 2px;
    background: var(--card-bg-alt);
    overflow: hidden;
  }

  .tool-call-card.error {
    border-color: var(--danger-border);
  }

  .toggle {
    border: 0;
    width: 100%;
    background: transparent;
    color: inherit;
    padding: 0.75rem;
    text-align: left;
    cursor: pointer;
    display: grid;
    gap: 0.35rem;
  }

  .badge {
    display: inline-block;
    width: fit-content;
    border: 1px solid var(--secondary-border);
    background: var(--secondary-bg);
    color: var(--secondary-fg);
    padding: 0.15rem 0.5rem;
    border-radius: 2px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .preview {
    font-size: 0.8rem;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  pre {
    margin: 0;
    padding: 0.75rem;
    background: var(--input-bg);
    border-top: 1px solid var(--card-border);
    color: var(--input-fg);
    overflow-x: auto;
    font-size: 0.76rem;
    line-height: 1.35;
    font-family: 'JetBrains Mono', monospace;
  }

  .result h4 {
    margin: 0;
    padding: 0.6rem 0.75rem 0;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--label);
  }

  .result.error {
    background: color-mix(in srgb, var(--danger-bg) 65%, transparent);
  }

  .diff {
    border-top: 1px solid var(--card-border);
    padding: 0.6rem 0.75rem;
    display: grid;
    gap: 0.4rem;
  }

  .diff-toggle {
    min-height: 36px;
    width: fit-content;
    border-radius: 2px;
    border: 1px solid var(--secondary-border);
    background: var(--secondary-bg);
    color: var(--secondary-fg);
    font-weight: 700;
    padding: 0 0.75rem;
  }

  .diff-toggle:disabled {
    opacity: 0.58;
  }

  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.76rem;
  }
</style>
