<script>
  import MicButton from './MicButton.svelte'

  export let sessionId = ''
  export let psk = ''
  export let pendingInput = null
  export let connectionStatus = 'disconnected'
  export let onSubmitted = null
  export let voiceLanguage = 'ja'

  export let value = ''
  let isSubmitting = false
  let errorMessage = ''

  $: isConnected = connectionStatus === 'connected'
  $: isDisabled = !isConnected || !sessionId || isSubmitting
  $: placeholder = pendingInput ? 'Answer the question...' : 'Send a message...'

  function handleTranscribed(text) {
    const trimmed = typeof text === 'string' ? text.trim() : ''
    if (!trimmed) {
      return
    }

    value = value ? `${value.trimEnd()} ${trimmed}` : trimmed
  }

  async function submit() {
    const text = value.trim()
    if (!text || isDisabled) {
      return
    }

    isSubmitting = true
    errorMessage = ''

    const endpoint = pendingInput ? 'input' : 'message'
    const payload = pendingInput
      ? {
          request_id: pendingInput.request_id,
          response: text,
        }
      : {
          content: text,
        }

    try {
      const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(psk ? { 'X-PSK': psk } : {}),
        },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        let detail = ''
        try {
          const payload = await response.json()
          detail = typeof payload?.detail === 'string' ? payload.detail : ''
        } catch {
          // no-op
        }
        throw new Error(
          detail
            ? `${response.status} ${detail}`
            : `${response.status} ${response.statusText}`.trim(),
        )
      }

      value = ''
      if (typeof onSubmitted === 'function') {
        onSubmitted({ endpoint, payload })
      }
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Request failed'
    } finally {
      isSubmitting = false
    }
  }

  function onKeyDown(event) {
    if (event.key !== 'Enter' || event.shiftKey) {
      return
    }
    event.preventDefault()
    submit()
  }
</script>

<div class="input-bar">
  <MicButton
    {psk}
    language={voiceLanguage}
    disabled={isDisabled}
    onTranscribed={handleTranscribed}
  />
  <textarea
    rows="1"
    aria-label="Message input"
    bind:value
    placeholder={placeholder}
    disabled={isDisabled}
    on:keydown={onKeyDown}
  ></textarea>
  <button type="button" on:click={submit} disabled={isDisabled}>Send</button>
</div>
{#if errorMessage}
  <p class="error">{errorMessage}</p>
{/if}

<style>
  .input-bar {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.5rem;
    border: 1px solid var(--card-border);
    border-radius: 2px;
    background: var(--card-bg-alt);
    padding: 0.5rem;
  }

  textarea {
    resize: none;
    min-height: 42px;
    max-height: 150px;
    border-radius: 2px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    color: var(--input-fg);
    padding: 0.6rem 0.7rem;
    line-height: 1.35;
    font: inherit;
  }

  textarea:disabled {
    opacity: 0.6;
  }

  button {
    min-width: 72px;
    border-radius: 2px;
    border: 1px solid var(--primary-border);
    background: var(--primary-bg);
    color: var(--primary-fg);
    font-weight: 700;
    padding: 0 0.75rem;
  }

  button:disabled {
    opacity: 0.6;
  }

  .error {
    margin: 0.4rem 0 0;
    color: var(--error);
    font-size: 0.76rem;
  }
</style>
