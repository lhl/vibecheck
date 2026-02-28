<script>
  export let sessionId = ''
  export let psk = ''
  export let pendingInput = null
  export let connectionStatus = 'disconnected'
  export let onSubmitted = null

  let value = ''
  let isSubmitting = false

  $: isConnected = connectionStatus === 'connected'
  $: isDisabled = !isConnected || !sessionId || isSubmitting
  $: placeholder = pendingInput ? 'Answer the question...' : 'Send a message...'

  async function submit() {
    const text = value.trim()
    if (!text || isDisabled) {
      return
    }

    isSubmitting = true

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
        throw new Error(`${response.status} ${response.statusText}`)
      }

      value = ''
      if (typeof onSubmitted === 'function') {
        onSubmitted({ endpoint, payload })
      }
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

<style>
  .input-bar {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.5rem;
    border: 1px solid #33415f;
    border-radius: 14px;
    background: #161f32;
    padding: 0.5rem;
  }

  textarea {
    resize: none;
    min-height: 42px;
    max-height: 150px;
    border-radius: 10px;
    border: 1px solid #3a4a68;
    background: #101728;
    color: #dfebff;
    padding: 0.6rem 0.7rem;
    line-height: 1.35;
    font: inherit;
  }

  textarea:disabled {
    opacity: 0.6;
  }

  button {
    min-width: 72px;
    border-radius: 10px;
    border: 1px solid #986346;
    background: #3b281b;
    color: #ffdcbf;
    font-weight: 700;
    padding: 0 0.75rem;
  }

  button:disabled {
    opacity: 0.6;
  }
</style>
