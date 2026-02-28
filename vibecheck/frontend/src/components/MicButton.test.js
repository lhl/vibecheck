import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'

let recording = false

vi.mock('../lib/recorder', () => ({
  isRecording: () => recording,
  startRecording: async () => {
    recording = true
  },
  stopRecording: async () => {
    recording = false
    return new Blob(['audio'], { type: 'audio/webm' })
  },
}))

import MicButton from './MicButton.svelte'

describe('MicButton', () => {
  beforeEach(() => {
    recording = false
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
})
