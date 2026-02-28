<script>
  export let toolCall
  export let result = null

  let expanded = false

  $: argsJson = JSON.stringify(toolCall?.args || {}, null, 2)
  $: argsPreview = argsJson.replaceAll('\n', ' ').slice(0, 140)
  $: resultOutput = result?.output || ''
  $: hasError = Boolean(result?.is_error)

  function toggleExpanded() {
    expanded = !expanded
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
</article>

<style>
  .tool-call-card {
    border: 1px solid #3a4864;
    border-radius: 12px;
    background: linear-gradient(160deg, #1d273b, #141c2b);
    overflow: hidden;
  }

  .tool-call-card.error {
    border-color: #a64141;
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
    border: 1px solid #4f6a9d;
    background: #1d3157;
    color: #d5e4ff;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .preview {
    font-size: 0.8rem;
    color: #b5c3e2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  pre {
    margin: 0;
    padding: 0.75rem;
    background: rgb(8 12 22 / 0.6);
    border-top: 1px solid #2d3852;
    color: #d7e2fa;
    overflow-x: auto;
    font-size: 0.76rem;
    line-height: 1.35;
    font-family: 'IBM Plex Mono', 'Fira Code', monospace;
  }

  .result h4 {
    margin: 0;
    padding: 0.6rem 0.75rem 0;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #a8b6d6;
  }

  .result.error {
    background: rgb(80 24 24 / 0.2);
  }
</style>
