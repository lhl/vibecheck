<script>
  export let pendingApproval = null
  export let sessionId = ''
  export let psk = ''
  export let onResolved = null

  let isSubmitting = false
  let errorMessage = ''

  $: argsSummary = JSON.stringify(pendingApproval?.args || {})

  async function submitDecision(approved) {
    if (!pendingApproval || !sessionId || isSubmitting) {
      return
    }

    isSubmitting = true
    errorMessage = ''

    try {
      const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(psk ? { 'X-PSK': psk } : {}),
        },
        body: JSON.stringify({
          call_id: pendingApproval.call_id,
          approved,
        }),
      })

      if (!response.ok) {
        let detail = ''
        try {
          const errBody = await response.json()
          detail = typeof errBody?.detail === 'string' ? errBody.detail : ''
        } catch {
          // no-op
        }
        throw new Error(
          detail
            ? `${response.status} ${detail}`
            : `${response.status} ${response.statusText}`.trim(),
        )
      }

      if (typeof onResolved === 'function') {
        onResolved(pendingApproval.call_id, approved)
      }
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Request failed'
    } finally {
      isSubmitting = false
    }
  }
</script>

{#if pendingApproval}
  <section class="approval-panel" aria-live="polite">
    <header>
      <p class="eyebrow">Approval Needed</p>
      <h3>{pendingApproval.tool_name}</h3>
    </header>

    <p class="args">{argsSummary}</p>

    <div class="actions">
      <button type="button" class="approve" on:click={() => submitDecision(true)} disabled={isSubmitting}>
        Approve
      </button>
      <button type="button" class="deny" on:click={() => submitDecision(false)} disabled={isSubmitting}>
        Deny
      </button>
    </div>

    {#if errorMessage}
      <p class="error">{errorMessage}</p>
    {/if}
  </section>
{/if}

<style>
  .approval-panel {
    border: 1px solid var(--session-status-waiting);
    background: var(--card-bg-alt);
    border-radius: 2px;
    padding: 0.75rem;
    display: grid;
    gap: 0.6rem;
  }

  header {
    display: grid;
    gap: 0.2rem;
  }

  .eyebrow {
    margin: 0;
    font-size: 0.68rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--session-status-waiting);
  }

  h3 {
    margin: 0;
    font-size: 0.92rem;
    color: var(--fg);
  }

  .args {
    margin: 0;
    font-size: 0.82rem;
    line-height: 1.35;
    color: var(--text-muted);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }

  button {
    min-height: 40px;
    border-radius: 2px;
    border: 1px solid transparent;
    font-weight: 700;
    font-size: 0.82rem;
  }

  button:disabled {
    opacity: 0.6;
  }

  .approve {
    border-color: #2d8d5c;
    background: #143727;
    color: #b9f6d8;
  }

  .deny {
    border-color: #9a4747;
    background: #3d1919;
    color: #ffd4d4;
  }

  .error {
    margin: 0;
    color: var(--error);
    font-size: 0.75rem;
  }
</style>
