import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { float32ToWavBlob } from './vad.js'

let mockInstance
let capturedOptions

function createMockVAD() {
  mockInstance = {
    started: false,
    destroyed: false,
    start: vi.fn(async () => { mockInstance.started = true }),
    pause: vi.fn(() => { mockInstance.started = false }),
    destroy: vi.fn(() => { mockInstance.destroyed = true; mockInstance.started = false }),
  }
  return mockInstance
}

beforeEach(() => {
  capturedOptions = null
  vi.stubGlobal('window', {
    ...globalThis,
    vad: {
      MicVAD: {
        new: vi.fn(async (opts) => {
          capturedOptions = opts
          return createMockVAD()
        }),
      },
    },
  })
})

afterEach(async () => {
  const mod = await import('./vad.js')
  await mod.destroyVAD()
  vi.restoreAllMocks()
})

describe('float32ToWavBlob', () => {
  it('produces a valid WAV blob from Float32Array', () => {
    const samples = new Float32Array([0.1, -0.2, 0.3, 0.0])
    const blob = float32ToWavBlob(samples)

    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('audio/wav')
    // 44 byte header + 4 samples * 2 bytes each = 52 bytes
    expect(blob.size).toBe(52)
  })

  it('clamps samples to [-1, 1] range', () => {
    const samples = new Float32Array([2.0, -3.0])
    const blob = float32ToWavBlob(samples)
    expect(blob.size).toBe(48) // 44 header + 2*2
  })

  it('handles empty input', () => {
    const blob = float32ToWavBlob(new Float32Array([]))
    expect(blob.size).toBe(44) // header only
  })
})

describe('VAD lifecycle', () => {
  it('initializes MicVAD and starts listening', async () => {
    const { startVAD, isVADActive } = await import('./vad.js')

    await startVAD({ onSpeechEnd: vi.fn() })

    expect(window.vad.MicVAD.new).toHaveBeenCalledOnce()
    expect(mockInstance.start).toHaveBeenCalled()
    expect(isVADActive()).toBe(true)
  })

  it('pauses and resumes without destroying', async () => {
    const { startVAD, pauseVAD, resumeVAD, isVADActive } = await import('./vad.js')
    await startVAD({ onSpeechEnd: vi.fn() })

    await pauseVAD()
    expect(mockInstance.pause).toHaveBeenCalled()
    expect(isVADActive()).toBe(true)

    await resumeVAD()
    expect(mockInstance.start).toHaveBeenCalledTimes(2)
  })

  it('destroys instance and releases resources', async () => {
    const { startVAD, destroyVAD, isVADActive } = await import('./vad.js')
    await startVAD({ onSpeechEnd: vi.fn() })

    await destroyVAD()
    expect(mockInstance.pause).toHaveBeenCalled()
    expect(mockInstance.destroy).toHaveBeenCalled()
    expect(isVADActive()).toBe(false)
  })

  it('destroyVAD is safe to call when no instance exists', async () => {
    const { destroyVAD, isVADActive } = await import('./vad.js')
    await destroyVAD()
    expect(isVADActive()).toBe(false)
  })

  it('passes onSpeechEnd wrapper to MicVAD that converts Float32 to WAV', async () => {
    const { startVAD } = await import('./vad.js')
    const onSpeechEnd = vi.fn()
    await startVAD({ onSpeechEnd })

    // The captured options should have an onSpeechEnd wrapper
    expect(capturedOptions).toBeTruthy()
    expect(typeof capturedOptions.onSpeechEnd).toBe('function')

    // Call the internal wrapper with fake audio
    capturedOptions.onSpeechEnd(new Float32Array([0.5, -0.5]))

    expect(onSpeechEnd).toHaveBeenCalledOnce()
    const blob = onSpeechEnd.mock.calls[0][0]
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('audio/wav')
  })

  it('throws when VAD library is not loaded', async () => {
    vi.stubGlobal('window', { ...globalThis })
    const { destroyVAD, startVAD } = await import('./vad.js')
    await destroyVAD()

    await expect(startVAD({ onSpeechEnd: vi.fn() })).rejects.toThrow('VAD library not loaded')
  })
})
