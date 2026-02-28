import { afterEach, describe, expect, it, vi } from 'vitest'

function createStream() {
  const track = { stop: vi.fn() }
  const stream = { getTracks: () => [track] }
  return { stream, track }
}

function installRecorderMocks() {
  const originalMediaDevicesDescriptor = Object.getOwnPropertyDescriptor(navigator, 'mediaDevices')
  const { stream, track } = createStream()

  const getUserMedia = vi.fn(async () => stream)
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  })

  let recorderInstances = 0

  class StubMediaRecorder {
    static isTypeSupported() {
      return true
    }

    constructor() {
      recorderInstances += 1
      this.state = 'inactive'
      this.mimeType = 'audio/webm;codecs=opus'
      this.ondataavailable = null
      this.onerror = null
      this.onstop = null
    }

    start() {
      this.state = 'recording'
    }

    stop() {
      this.state = 'inactive'
      if (typeof this.onstop === 'function') {
        this.onstop()
      }
    }
  }

  vi.stubGlobal('MediaRecorder', StubMediaRecorder)

  const restore = () => {
    if (originalMediaDevicesDescriptor) {
      Object.defineProperty(navigator, 'mediaDevices', originalMediaDevicesDescriptor)
    } else {
      try {
        delete navigator.mediaDevices
      } catch {
        // no-op
      }
    }
  }

  return { getUserMedia, track, restore, recorderInstances: () => recorderInstances }
}

describe('recorder', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    vi.resetModules()
    vi.useRealTimers()
  })

  it('clears active state on recorder error so a new recording can start', async () => {
    const { getUserMedia, track, restore, recorderInstances } = installRecorderMocks()
    try {
      const { startRecording, stopRecording } = await import('./recorder')

      const first = await startRecording()
      expect(getUserMedia).toHaveBeenCalledTimes(1)
      expect(recorderInstances()).toBe(1)

      first.recorder.onerror?.()
      expect(track.stop).toHaveBeenCalled()
      await first.stopped.catch(() => {})

      const second = await startRecording()
      expect(getUserMedia).toHaveBeenCalledTimes(2)
      expect(recorderInstances()).toBe(2)
      expect(second).not.toBe(first)

      await stopRecording().catch(() => {})
    } finally {
      restore()
    }
  })

  it('auto-stops recordings after the configured max duration', async () => {
    vi.useFakeTimers()
    const { track, restore } = installRecorderMocks()
    try {
      const { isRecording, startRecording, stopRecording } = await import('./recorder')

      await startRecording({ maxMs: 25 })
      expect(isRecording()).toBe(true)

      await vi.advanceTimersByTimeAsync(25)
      expect(track.stop).toHaveBeenCalled()
      expect(isRecording()).toBe(false)

      await expect(stopRecording()).resolves.toBeInstanceOf(Blob)
    } finally {
      restore()
    }
  })
})
