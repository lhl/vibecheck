import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let recording = false
let startDeferred = null
let stopCalls = 0

function createDeferred() {
  let resolve
  const promise = new Promise((resolver) => {
    resolve = resolver
  })
  return { promise, resolve }
}

vi.mock('../lib/recorder', () => ({
  isRecording: () => recording,
  startRecording: async () => {
    const deferred = startDeferred
    if (deferred) {
      await deferred.promise
    }
    recording = true
  },
  stopRecording: async () => {
    stopCalls += 1
    recording = false
    return new Blob(['audio'], { type: 'audio/webm' })
  },
  __setStartDeferred: (deferred) => {
    startDeferred = deferred
  },
  __getStopCalls: () => stopCalls,
  __isRecording: () => recording,
}))

import { __getStopCalls, __isRecording, __setStartDeferred } from '../lib/recorder'
import MicButton from './MicButton.svelte'

describe('MicButton', () => {
  let nowMs = 1000

  beforeEach(() => {
    recording = false
    startDeferred = null
    stopCalls = 0
    nowMs = 1000
    vi.spyOn(Date, 'now').mockImplementation(() => nowMs)
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ text: 'hello', language: 'en', duration_ms: 0 }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
      ),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts audio to /api/voice/transcribe and dispatches transcribed event', async () => {
    const onTranscribed = vi.fn()
    render(MicButton, { psk: 'dev-psk', language: 'en', disabled: false, onTranscribed })

    const button = screen.getByRole('button', { name: /hold to record/i })
    await fireEvent.mouseDown(button)
    // Simulate a hold longer than the tap threshold (300ms)
    nowMs += 500
    await fireEvent.mouseUp(button)

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/voice/transcribe?language=en',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    await waitFor(() => {
      expect(onTranscribed).toHaveBeenCalledWith('hello')
    })
  })

  it('stops recording even if released before startRecording resolves', async () => {
    const deferred = createDeferred()
    __setStartDeferred(deferred)

    render(MicButton, { psk: 'dev-psk', language: 'en', disabled: false, onTranscribed: vi.fn() })

    const button = screen.getByRole('button', { name: /hold to record/i })
    await fireEvent.mouseDown(button)
    nowMs += 500
    await fireEvent.mouseUp(button)

    deferred.resolve()

    await waitFor(() => {
      expect(__getStopCalls()).toBe(1)
      expect(__isRecording()).toBe(false)
    })
  })

  it('stops recording when touch is cancelled', async () => {
    const deferred = createDeferred()
    __setStartDeferred(deferred)

    render(MicButton, { psk: 'dev-psk', language: 'en', disabled: false, onTranscribed: vi.fn() })

    const button = screen.getByRole('button', { name: /hold to record/i })
    await fireEvent.touchStart(button)
    nowMs += 500
    await fireEvent.touchCancel(button)

    deferred.resolve()

    await waitFor(() => {
      expect(__getStopCalls()).toBe(1)
      expect(__isRecording()).toBe(false)
    })
  })

  it('toggles talker mode on quick tap', async () => {
    const onTalkerToggle = vi.fn()
    render(MicButton, { psk: 'dev-psk', language: 'en', disabled: false, onTalkerToggle })

    const button = screen.getByRole('button', { name: /hold to record/i })
    await fireEvent.mouseDown(button)
    // Quick tap — no time advance, stays below threshold
    await fireEvent.mouseUp(button)

    await waitFor(() => {
      expect(onTalkerToggle).toHaveBeenCalledOnce()
    })
  })
})
