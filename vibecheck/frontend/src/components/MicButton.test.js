import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
  beforeEach(() => {
    recording = false
    startDeferred = null
    stopCalls = 0
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

  it('posts audio to /api/voice/transcribe and dispatches transcribed event', async () => {
    const onTranscribed = vi.fn()
    render(MicButton, { psk: 'dev-psk', language: 'en', disabled: false, onTranscribed })

    const button = screen.getByRole('button', { name: 'Hold to record' })
    await fireEvent.mouseDown(button)
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

    const button = screen.getByRole('button', { name: 'Hold to record' })
    await fireEvent.mouseDown(button)
    await fireEvent.mouseUp(button)

    deferred.resolve()

    await waitFor(() => {
      expect(__getStopCalls()).toBe(1)
      expect(__isRecording()).toBe(false)
    })
  })
})
