<script>
  import { onDestroy } from 'svelte'
  import { isRecording, startRecording, stopRecording } from '../lib/recorder'

  export let psk = ''
  export let language = 'ja'
  export let disabled = false
  export let onTranscribed = null

  let recordingStartedAt = 0
  let elapsedLabel = '0.0s'
  let intervalId = null
  let isUploading = false
  let errorMessage = ''
  let startPromise = null
  let stopRequested = false

  function updateElapsed() {
    if (!recordingStartedAt) {
      elapsedLabel = '0.0s'
      return
    }
    elapsedLabel = `${((Date.now() - recordingStartedAt) / 1000).toFixed(1)}s`
  }

  function startTimer() {
    if (intervalId) {
      return
    }
    intervalId = setInterval(updateElapsed, 100)
  }

  function stopTimer() {
    if (!intervalId) {
      return
    }
    clearInterval(intervalId)
    intervalId = null
  }

  async function begin() {
    if (disabled || isUploading || startPromise || isRecording()) {
      return
    }

    errorMessage = ''
    recordingStartedAt = 0
    elapsedLabel = '0.0s'
    stopRequested = false

    try {
      const pending = startRecording()
      startPromise = pending
      await pending
      if (stopRequested) {
        return
      }
      recordingStartedAt = Date.now()
      updateElapsed()
      startTimer()
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

    stopTimer()
    updateElapsed()
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
      recordingStartedAt = 0
      elapsedLabel = '0.0s'
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
    stopTimer()
    // Release mic/tracks if still recording when component unmounts
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
    <span class="dot" aria-hidden="true"></span>
    <span class="timer" aria-hidden="true">{elapsedLabel}</span>
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
    grid-auto-flow: column;
    gap: 0.4rem;
    align-items: center;
    justify-content: center;
    min-height: 42px;
    min-width: 88px;
    padding: 0 0.7rem;
    border-radius: 2px;
    border: 1px solid #6d4a4a;
    background: #241416;
    color: #ffd8d8;
    font-weight: 800;
    user-select: none;
    touch-action: manipulation;
  }

  .mic:disabled {
    opacity: 0.55;
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #6b707d;
  }

  .mic[data-recording='true'] .dot {
    background: #ff4d4d;
    animation: pulse 0.9s infinite;
  }

  .timer {
    font-size: 0.75rem;
    letter-spacing: 0.03em;
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
