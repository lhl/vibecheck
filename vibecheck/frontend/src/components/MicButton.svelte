<script>
  import { onDestroy } from 'svelte'
  import { isRecording, startRecording, stopRecording } from '../lib/recorder'

  export let psk = ''
  export let language = 'ja'
  export let disabled = false
  export let onTranscribed = null

  let isUploading = false
  let errorMessage = ''
  let startPromise = null
  let stopRequested = false

  async function begin() {
    if (disabled || isUploading || startPromise || isRecording()) {
      return
    }

    errorMessage = ''
    stopRequested = false

    try {
      const pending = startRecording()
      startPromise = pending
      await pending
      if (stopRequested) {
        return
      }
    } catch (error) {
      if (!stopRequested) {
        errorMessage = error instanceof Error ? error.message : 'Recording failed'
      }
    } finally {
      startPromise = null
    }
  }

  async function finish() {
    if (disabled || isUploading) {
      return
    }

    stopRequested = true
    const pending = startPromise
    errorMessage = ''

    let blob = null
    try {
      if (pending) {
        await pending
      }
      blob = await stopRecording()
    } catch (error) {
      const message = error instanceof Error ? error.message : ''
      if (message.startsWith('No recording is active')) {
        return
      }
      errorMessage = message || 'Recording failed'
      return
    }

    if (!blob || blob.size === 0) {
      errorMessage = 'Recording was empty.'
      return
    }

    isUploading = true

    try {
      const response = await fetch(`/api/voice/transcribe?language=${encodeURIComponent(language)}`, {
        method: 'POST',
        headers: {
          ...(psk ? { 'X-PSK': psk } : {}),
          'Content-Type': blob.type || 'audio/webm',
        },
        body: blob,
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

      const payload = await response.json()
      const text = typeof payload?.text === 'string' ? payload.text.trim() : ''
      if (text && typeof onTranscribed === 'function') {
        onTranscribed(text)
      }
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Transcription failed'
    } finally {
      isUploading = false
    }
  }

  function handleMouseDown(event) {
    event.preventDefault()
    begin()
  }

  function handleMouseUp(event) {
    event.preventDefault()
    finish()
  }

  function handleMouseLeave() {
    finish()
  }

  function handleTouchStart(event) {
    event.preventDefault()
    begin()
  }

  function handleTouchEnd(event) {
    event.preventDefault()
    finish()
  }

  function handleTouchCancel(event) {
    event.preventDefault()
    finish()
  }

  onDestroy(() => {
    if (isRecording()) {
      try {
        stopRecording()
      } catch {
        // no-op
      }
    }
  })
</script>

<div class="mic-wrap">
  <button
    type="button"
    class="mic"
    aria-label="Hold to record"
    disabled={disabled || isUploading}
    data-recording={isRecording() ? 'true' : 'false'}
    on:mousedown={handleMouseDown}
    on:mouseup={handleMouseUp}
    on:mouseleave={handleMouseLeave}
    on:touchstart={handleTouchStart}
    on:touchend={handleTouchEnd}
    on:touchcancel={handleTouchCancel}
  >
    {#if isRecording()}
      <span class="rec-dot" aria-hidden="true"></span>
    {:else}
      <svg aria-hidden="true" class="mic-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="1" width="6" height="12" rx="3" />
        <path d="M5 10a7 7 0 0 0 14 0" />
        <line x1="12" y1="17" x2="12" y2="21" />
        <line x1="8" y1="21" x2="16" y2="21" />
      </svg>
    {/if}
  </button>
  {#if errorMessage}
    <p class="error">{errorMessage}</p>
  {/if}
</div>

<style>
  .mic-wrap {
    display: grid;
    gap: 0.25rem;
    justify-items: start;
  }

  .mic {
    display: grid;
    place-items: center;
    width: 44px;
    height: 42px;
    padding: 0;
    border-radius: 2px;
    border: 1px solid rgba(255,255,255,0.12);
    background: transparent;
    color: var(--text-muted, #888);
    user-select: none;
    touch-action: manipulation;
  }

  .mic:disabled {
    opacity: 0.4;
  }

  .mic[data-recording='true'] {
    border-color: #ff4d4d;
    background: rgba(255, 77, 77, 0.1);
  }

  .mic-icon {
    width: 20px;
    height: 20px;
  }

  .rec-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #ff4d4d;
    animation: pulse 0.9s infinite;
  }

  .error {
    margin: 0;
    font-size: 0.7rem;
    color: #ffbcbc;
  }

  @keyframes pulse {
    0% {
      transform: scale(1);
      opacity: 0.7;
    }
    50% {
      transform: scale(1.25);
      opacity: 1;
    }
    100% {
      transform: scale(1);
      opacity: 0.7;
    }
  }
</style>
