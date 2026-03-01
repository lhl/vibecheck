<script>
  import { tick } from 'svelte'
  import MicButton from './MicButton.svelte'

  export let sessionId = ''
  export let psk = ''
  export let pendingInput = null
  export let connectionStatus = 'disconnected'
  export let onSubmitted = null
  export let voiceLanguage = 'ja'
  export let talkerActive = false
  export let talkerState = 'idle'
  export let onTalkerToggle = null

  export let value = ''
  let isSubmitting = false
  let errorMessage = ''
  let textareaEl = null
  let recording = false

  $: isConnected = connectionStatus === 'connected'
  $: isDisabled = !isConnected || !sessionId || isSubmitting
  $: placeholder = pendingInput ? 'Answer the question...' : 'Send a message...'

  $: talkerLabel = (() => {
    switch (talkerState) {
      case 'listening': return 'LISTENING'
      case 'transcribing': return 'TRANSCRIBING'
      case 'running': return 'RUNNING'
      case 'speaking': return 'SPEAKING'
      default: return 'TALKING'
    }
  })()

  function autoResize() {
    if (!textareaEl) return
    textareaEl.style.height = 'auto'
    textareaEl.style.height = `${Math.min(textareaEl.scrollHeight, 150)}px`
  }

  function handleRecordingChange(active) {
    recording = active
  }

  function handleTranscribed(text) {
    const trimmed = typeof text === 'string' ? text.trim() : ''
    if (!trimmed) {
      return
    }

    value = trimmed
    tick().then(() => {
      autoResize()
      submit()
    })
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
      tick().then(autoResize)
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

  function onInput() {
    autoResize()
  }

  function handleTalkerToggle() {
    if (typeof onTalkerToggle === 'function') {
      onTalkerToggle()
    }
  }

  function exitTalker() {
    if (typeof onTalkerToggle === 'function') {
      onTalkerToggle()
    }
  }
</script>

{#if talkerActive}
  <div class="talker-bar">
    <MicButton
      {psk}
      language={voiceLanguage}
      disabled={isDisabled}
      talkerActive={true}
      onTranscribed={handleTranscribed}
      onRecordingChange={handleRecordingChange}
      onTalkerToggle={handleTalkerToggle}
    />
    <div class="talker-label" class:listening={talkerState === 'listening'} class:speaking={talkerState === 'speaking'}>
      <span class="talker-text">{talkerLabel}</span>
      {#if talkerState === 'listening' || talkerState === 'speaking'}
        <span class="talker-pulse" aria-hidden="true"></span>
      {/if}
    </div>
    <button type="button" class="talker-exit" on:click={exitTalker} aria-label="Exit talker mode">&times;</button>
  </div>
{:else}
  <div class="input-bar" class:recording>
    <MicButton
      {psk}
      language={voiceLanguage}
      disabled={isDisabled}
      talkerActive={false}
      onTranscribed={handleTranscribed}
      onRecordingChange={handleRecordingChange}
      onTalkerToggle={handleTalkerToggle}
    />
    <textarea
      rows="1"
      aria-label="Message input"
      bind:value
      bind:this={textareaEl}
      placeholder={placeholder}
      disabled={isDisabled}
      on:keydown={onKeyDown}
      on:input={onInput}
    ></textarea>
    <button type="button" on:click={submit} disabled={isDisabled}>Send</button>
  </div>
{/if}
{#if errorMessage}
  <p class="error">{errorMessage}</p>
{/if}

<style>
  .input-bar {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.35rem;
    align-items: start;
  }

  textarea {
    resize: none;
    min-height: 60px;
    max-height: 150px;
    border-radius: 2px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    color: var(--input-fg);
    padding: 0.5rem 0.6rem;
    line-height: 1.35;
    font: inherit;
    overflow-y: auto;
    transition: border-color 0.15s, background 0.15s;
  }

  .input-bar.recording textarea {
    border-color: #9a4747;
    background: rgba(255, 77, 77, 0.06);
  }

  textarea:disabled {
    opacity: 0.6;
  }

  button {
    min-width: 60px;
    height: 60px;
    border-radius: 2px;
    border: 1px solid var(--primary-border);
    background: var(--primary-bg);
    color: var(--primary-fg);
    font: inherit;
    font-weight: 700;
    font-size: 0.82rem;
    padding: 0 0.5rem;
  }

  button:disabled {
    opacity: 0.6;
  }

  .error {
    margin: 0.4rem 0 0;
    color: var(--error);
    font-size: 0.76rem;
  }

  /* Talker mode bar */
  .talker-bar {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.35rem;
    align-items: center;
  }

  .talker-label {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 60px;
    border-radius: 2px;
    border: 1px solid #e07060;
    background: #fa8072;
    color: #1a1a1a;
    font-weight: 800;
    font-size: 0.95rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .talker-label.listening {
    animation: talker-breathe 2s ease-in-out infinite;
  }

  .talker-label.speaking {
    animation: talker-breathe 1.2s ease-in-out infinite;
  }

  .talker-text {
    user-select: none;
  }

  .talker-pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #1a1a1a;
    animation: pulse 0.9s infinite;
  }

  .talker-exit {
    min-width: 60px;
    height: 60px;
    border-radius: 2px;
    border: 1px solid #9a4747;
    background: rgba(255, 77, 77, 0.1);
    color: #ffbcbc;
    font-size: 1.6rem;
    font-weight: 400;
    line-height: 1;
    padding: 0;
  }

  @keyframes talker-breathe {
    0% { opacity: 1; }
    50% { opacity: 0.75; }
    100% { opacity: 1; }
  }

  @keyframes pulse {
    0% { transform: scale(1); opacity: 0.7; }
    50% { transform: scale(1.25); opacity: 1; }
    100% { transform: scale(1); opacity: 0.7; }
  }
</style>
