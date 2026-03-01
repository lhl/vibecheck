<script>
  import { onDestroy } from 'svelte'
  import { isRecording, startRecording, stopRecording } from '../lib/recorder'

  export let psk = ''
  export let language = 'ja'
  export let disabled = false
  export let talkerActive = false
  export let onTranscribed = null
  export let onRecordingChange = null
  export let onTalkerToggle = null

  const TAP_THRESHOLD_MS = 300

  let isUploading = false
  let errorMessage = ''
  let startPromise = null
  let stopRequested = false
  let pressStartedAt = 0

  function notifyRecording(active) {
    if (typeof onRecordingChange === 'function') {
      onRecordingChange(active)
    }
  }

  async function begin() {
    if (disabled || isUploading || startPromise || isRecording()) {
      return
    }

    errorMessage = ''
    stopRequested = false
    pressStartedAt = Date.now()

    try {
      const pending = startRecording()
      startPromise = pending
      await pending
      if (stopRequested) {
        return
      }
      notifyRecording(true)
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

    const pressDuration = Date.now() - pressStartedAt
    stopRequested = true
    const pending = startPromise
    errorMessage = ''
    notifyRecording(false)

    let blob = null
    try {
      if (pending) {
        await pending
      }
      blob = await stopRecording()
    } catch (error) {
      const message = error instanceof Error ? error.message : ''
      if (message.startsWith('No recording is active')) {
        // Short tap — toggle talker mode
        if (pressDuration < TAP_THRESHOLD_MS && typeof onTalkerToggle === 'function') {
          onTalkerToggle()
        }
        return
      }
      errorMessage = message || 'Recording failed'
      return
    }

    // Short tap with a tiny/empty blob — toggle talker mode instead of transcribing
    if (pressDuration < TAP_THRESHOLD_MS) {
      if (typeof onTalkerToggle === 'function') {
        onTalkerToggle()
      }
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
    if (pressStartedAt && (Date.now() - pressStartedAt) >= TAP_THRESHOLD_MS) {
      finish()
    }
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
    class:talker={talkerActive}
    aria-label={talkerActive ? 'Tap to exit talker mode' : 'Hold to record, tap for talker mode'}
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
    {:else if talkerActive}
      <svg aria-hidden="true" class="mic-icon" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="1" width="6" height="12" rx="3" />
        <path d="M5 10a7 7 0 0 0 14 0" />
        <line x1="12" y1="17" x2="12" y2="21" />
        <line x1="8" y1="21" x2="16" y2="21" />
      </svg>
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
    width: 60px;
    height: 60px;
    padding: 0;
    border-radius: 2px;
    border: 1px solid #9a4747;
    background: rgba(255, 77, 77, 0.06);
    color: #d88;
    user-select: none;
    touch-action: manipulation;
  }

  .mic:disabled {
    opacity: 0.4;
  }

  .mic[data-recording='true'] {
    border-color: #ff4d4d;
    background: rgba(255, 77, 77, 0.18);
    color: #ff4d4d;
  }

  .mic.talker {
    border-color: #fa8072;
    background: rgba(250, 128, 114, 0.25);
    color: #fa8072;
  }

  .mic-icon {
    width: 22px;
    height: 22px;
  }

  .rec-dot {
    width: 16px;
    height: 16px;
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
