import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.svelte'

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function installMediaDevices(getUserMedia) {
  const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, 'mediaDevices')
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  })

  return () => {
    if (originalMediaDevices) {
      Object.defineProperty(navigator, 'mediaDevices', originalMediaDevices)
      return
    }
    Reflect.deleteProperty(navigator, 'mediaDevices')
  }
}

function installRecorderMock({ chunkBytes = 4096 } = {}) {
  class MockMediaRecorder {
    static isTypeSupported() {
      return true
    }

    constructor() {
      this.state = 'inactive'
      this.mimeType = 'audio/webm'
      this.ondataavailable = null
      this.onerror = null
      this.onstop = null
    }

    start() {
      this.state = 'recording'
    }

    stop() {
      this.state = 'inactive'
      if (chunkBytes > 0 && this.ondataavailable) {
        const data = new Blob([new Uint8Array(chunkBytes)], { type: this.mimeType })
        this.ondataavailable({ data })
      }
      if (this.onstop) {
        this.onstop()
      }
    }
  }

  vi.stubGlobal('MediaRecorder', MockMediaRecorder)
  window.MediaRecorder = MockMediaRecorder
}

function installPlaybackMocks() {
  const originalCreateObjectURL = URL.createObjectURL
  const originalRevokeObjectURL = URL.revokeObjectURL

  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: vi.fn(() => 'blob:mock-audio'),
  })
  Object.defineProperty(URL, 'revokeObjectURL', {
    configurable: true,
    value: vi.fn(),
  })

  class MockAudio {
    constructor() {
      this.onended = null
      this.onerror = null
      this.preload = 'auto'
    }

    pause() {
      return undefined
    }

    play() {
      queueMicrotask(() => {
        if (this.onended) {
          this.onended()
        }
      })
      return Promise.resolve()
    }
  }

  vi.stubGlobal('Audio', MockAudio)
  window.Audio = MockAudio

  return () => {
    if (originalCreateObjectURL) {
      Object.defineProperty(URL, 'createObjectURL', {
        configurable: true,
        value: originalCreateObjectURL,
      })
    } else {
      Reflect.deleteProperty(URL, 'createObjectURL')
    }

    if (originalRevokeObjectURL) {
      Object.defineProperty(URL, 'revokeObjectURL', {
        configurable: true,
        value: originalRevokeObjectURL,
      })
    } else {
      Reflect.deleteProperty(URL, 'revokeObjectURL')
    }
  }
}

function installDateNowIncrementMock(step = 400, start = 1000) {
  let current = start
  return vi.spyOn(Date, 'now').mockImplementation(() => {
    current += step
    return current
  })
}

function createDeferred() {
  let resolve
  let reject
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })
  return { promise, resolve, reject }
}

describe('App milestone 2 state preview', () => {
  let fetchMock

  beforeEach(() => {
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [
            { voice_id: 'voice-one', name: 'Voice One' },
            { voice_id: 'voice-two', name: 'Voice Two' },
          ],
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders a state preview panel with all five states', async () => {
    render(App)

    expect(screen.getByRole('heading', { name: 'State Preview' })).toBeInTheDocument()
    expect(screen.getByText('Recommended for Japanese: Otani (JP).')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Ready')
    expect(screen.getByRole('button', { name: 'idle' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'recording' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'transcribing' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'speaking' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'error' })).toBeInTheDocument()
    expect(await screen.findByText('Voice One')).toBeInTheDocument()
  })

  it('renders language tags in voice labels when provided by the API', async () => {
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [
            { voice_id: 'voice-one', name: 'Voice One', language: 'EN' },
            { voice_id: 'voice-two', name: 'Voice Two', language: 'JP' },
          ],
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(App)

    expect(await screen.findByRole('option', { name: 'Voice One (EN)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Voice Two (JP)' })).toBeInTheDocument()
  })

  it('switches to error state preview without API calls', async () => {
    render(App)

    await fireEvent.click(screen.getByRole('button', { name: 'error' }))
    expect(screen.getByTestId('state-pill')).toHaveTextContent('error')
    expect(screen.getByTestId('status-message')).toHaveTextContent('Previewing error state')
    expect(screen.getByRole('heading', { name: 'Error' })).toBeInTheDocument()
  })

  it('updates the state pill and surface class for each preview state', async () => {
    const { container } = render(App)

    const expectedStates = ['idle', 'recording', 'transcribing', 'speaking', 'error']

    for (const state of expectedStates) {
      await fireEvent.click(screen.getByRole('button', { name: state }))
      expect(screen.getByTestId('state-pill')).toHaveTextContent(state)
      expect(container.querySelector('.state-surface')).toHaveClass(`state-${state}`)
    }
  })

  it('stops active recording when preview state is changed', async () => {
    const stopTrack = vi.fn()
    const mockStream = { getTracks: () => [{ stop: stopTrack }] }
    const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, 'mediaDevices')

    class MockMediaRecorder {
      static stopCalls = 0
      static isTypeSupported() {
        return true
      }

      constructor() {
        this.state = 'inactive'
        this.mimeType = 'audio/webm'
        this.ondataavailable = null
        this.onerror = null
        this.onstop = null
      }

      start() {
        this.state = 'recording'
      }

      stop() {
        MockMediaRecorder.stopCalls += 1
        this.state = 'inactive'
        if (this.onstop) {
          this.onstop()
        }
      }
    }

    try {
      Object.defineProperty(navigator, 'mediaDevices', {
        configurable: true,
        value: { getUserMedia: vi.fn().mockResolvedValue(mockStream) },
      })
      vi.stubGlobal('MediaRecorder', MockMediaRecorder)
      window.MediaRecorder = MockMediaRecorder

      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()

      await fireEvent.click(screen.getByRole('button', { name: 'idle' }))

      expect(MockMediaRecorder.stopCalls).toBe(1)
      expect(stopTrack).toHaveBeenCalledTimes(1)
      expect(fetchMock).not.toHaveBeenCalledWith('/api/stt', expect.anything())
    } finally {
      if (originalMediaDevices) {
        Object.defineProperty(navigator, 'mediaDevices', originalMediaDevices)
      } else {
        Reflect.deleteProperty(navigator, 'mediaDevices')
      }
    }
  })

  it('does not stop a new recording when a previous preview-canceled recorder finishes', async () => {
    const stopTrackOne = vi.fn()
    const stopTrackTwo = vi.fn()
    const streamOne = { getTracks: () => [{ stop: stopTrackOne }] }
    const streamTwo = { getTracks: () => [{ stop: stopTrackTwo }] }
    const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, 'mediaDevices')

    class AsyncStopMediaRecorder {
      static stopQueue = []

      static isTypeSupported() {
        return true
      }

      static flushOneStop() {
        const callback = AsyncStopMediaRecorder.stopQueue.shift()
        if (callback) {
          callback()
        }
      }

      constructor() {
        this.state = 'inactive'
        this.mimeType = 'audio/webm'
        this.ondataavailable = null
        this.onerror = null
        this.onstop = null
      }

      start() {
        this.state = 'recording'
      }

      stop() {
        this.state = 'inactive'
        AsyncStopMediaRecorder.stopQueue.push(() => {
          if (this.onstop) {
            this.onstop()
          }
        })
      }
    }

    try {
      const getUserMedia = vi.fn().mockResolvedValueOnce(streamOne).mockResolvedValueOnce(streamTwo)
      Object.defineProperty(navigator, 'mediaDevices', {
        configurable: true,
        value: { getUserMedia },
      })
      vi.stubGlobal('MediaRecorder', AsyncStopMediaRecorder)
      window.MediaRecorder = AsyncStopMediaRecorder

      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'idle' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))

      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
      AsyncStopMediaRecorder.flushOneStop()

      expect(stopTrackOne).toHaveBeenCalledTimes(1)
      expect(stopTrackTwo).not.toHaveBeenCalled()
      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
    } finally {
      if (originalMediaDevices) {
        Object.defineProperty(navigator, 'mediaDevices', originalMediaDevices)
      } else {
        Reflect.deleteProperty(navigator, 'mediaDevices')
      }
    }
  })

  it('ignores stale recorder errors from a previous session', async () => {
    const stopTrackOne = vi.fn()
    const stopTrackTwo = vi.fn()
    const streamOne = { getTracks: () => [{ stop: stopTrackOne }] }
    const streamTwo = { getTracks: () => [{ stop: stopTrackTwo }] }
    const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, 'mediaDevices')

    class RecorderWithManualError {
      static instances = []

      static isTypeSupported() {
        return true
      }

      static emitError(index) {
        const instance = RecorderWithManualError.instances[index]
        if (instance?.onerror) {
          instance.onerror()
        }
      }

      constructor() {
        this.state = 'inactive'
        this.mimeType = 'audio/webm'
        this.ondataavailable = null
        this.onerror = null
        this.onstop = null
        RecorderWithManualError.instances.push(this)
      }

      start() {
        this.state = 'recording'
      }

      stop() {
        this.state = 'inactive'
        if (this.onstop) {
          this.onstop()
        }
      }
    }

    try {
      const getUserMedia = vi.fn().mockResolvedValueOnce(streamOne).mockResolvedValueOnce(streamTwo)
      Object.defineProperty(navigator, 'mediaDevices', {
        configurable: true,
        value: { getUserMedia },
      })
      vi.stubGlobal('MediaRecorder', RecorderWithManualError)
      window.MediaRecorder = RecorderWithManualError

      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'idle' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))

      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()

      RecorderWithManualError.emitError(0)

      expect(screen.queryByRole('heading', { name: 'Error' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
      expect(stopTrackOne).toHaveBeenCalled()
      expect(stopTrackTwo).not.toHaveBeenCalled()
    } finally {
      if (originalMediaDevices) {
        Object.defineProperty(navigator, 'mediaDevices', originalMediaDevices)
      } else {
        Reflect.deleteProperty(navigator, 'mediaDevices')
      }
    }
  })

  it('does not process dropped recording when stale error arrives before delayed stop', async () => {
    const stopTrackOne = vi.fn()
    const stopTrackTwo = vi.fn()
    const streamOne = { getTracks: () => [{ stop: stopTrackOne }] }
    const streamTwo = { getTracks: () => [{ stop: stopTrackTwo }] }
    const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, 'mediaDevices')

    class DelayedStopRecorder {
      static instances = []
      static stopQueue = []

      static isTypeSupported() {
        return true
      }

      static emitError(index) {
        const instance = DelayedStopRecorder.instances[index]
        if (instance?.onerror) {
          instance.onerror()
        }
      }

      static flushOneStop() {
        const callback = DelayedStopRecorder.stopQueue.shift()
        if (callback) {
          callback()
        }
      }

      constructor() {
        this.state = 'inactive'
        this.mimeType = 'audio/webm'
        this.ondataavailable = null
        this.onerror = null
        this.onstop = null
        DelayedStopRecorder.instances.push(this)
      }

      start() {
        this.state = 'recording'
      }

      stop() {
        this.state = 'inactive'
        DelayedStopRecorder.stopQueue.push(() => {
          if (this.onstop) {
            this.onstop()
          }
        })
      }
    }

    try {
      const getUserMedia = vi.fn().mockResolvedValueOnce(streamOne).mockResolvedValueOnce(streamTwo)
      Object.defineProperty(navigator, 'mediaDevices', {
        configurable: true,
        value: { getUserMedia },
      })
      vi.stubGlobal('MediaRecorder', DelayedStopRecorder)
      window.MediaRecorder = DelayedStopRecorder

      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'idle' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))

      DelayedStopRecorder.emitError(0)
      DelayedStopRecorder.flushOneStop()
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
      })

      expect(fetchMock).not.toHaveBeenCalledWith('/api/stt', expect.anything())
      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
      expect(stopTrackOne).toHaveBeenCalled()
      expect(stopTrackTwo).not.toHaveBeenCalled()
    } finally {
      if (originalMediaDevices) {
        Object.defineProperty(navigator, 'mediaDevices', originalMediaDevices)
      } else {
        Reflect.deleteProperty(navigator, 'mediaDevices')
      }
    }
  })
})

describe('App milestone 3 STT integration', () => {
  let fetchMock
  let restorePlaybackMocks

  beforeEach(() => {
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        return jsonResponse({ text: 'transcribed text', language: 'en' })
      }
      if (resource === '/api/tts') {
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    restorePlaybackMocks = installPlaybackMocks()
  })

  afterEach(() => {
    if (restorePlaybackMocks) {
      restorePlaybackMocks()
      restorePlaybackMocks = null
    }
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('records, uploads to /api/stt, and completes clean playback path', async () => {
    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(await screen.findByText('transcribed text')).toBeInTheDocument()
      expect(fetchMock).toHaveBeenCalledWith('/api/stt', expect.objectContaining({ method: 'POST' }))
      expect(fetchMock).toHaveBeenCalledWith('/api/tts', expect.objectContaining({ method: 'POST' }))
      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('idle')
      })
      expect(screen.queryByRole('heading', { name: 'Error' })).not.toBeInTheDocument()
      expect(screen.getByTestId('status-message')).toHaveTextContent('Playback complete')
    } finally {
      restoreMediaDevices()
    }
  })

  it('posts expected FormData fields to /api/stt', async () => {
    let sttRequestBody
    fetchMock = vi.fn(async (resource, options = {}) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        sttRequestBody = options.body
        return jsonResponse({ text: 'shape check', language: 'en' })
      }
      if (resource === '/api/tts') {
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      await screen.findByText('shape check')
      expect(sttRequestBody).toBeInstanceOf(FormData)
      expect(sttRequestBody.get('language')).toBe('en')

      const audioField = sttRequestBody.get('audio')
      expect(audioField).toBeInstanceOf(Blob)
      expect(audioField.size).toBeGreaterThan(0)
    } finally {
      restoreMediaDevices()
    }
  })

  it('shows actionable error when microphone permission is denied', async () => {
    const restoreMediaDevices = installMediaDevices(vi.fn().mockRejectedValue(new Error('denied')))
    installRecorderMock()

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))

      expect(await screen.findByRole('heading', { name: 'Error' })).toBeInTheDocument()
      expect(screen.getByText(/microphone permission denied/i)).toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalledWith('/api/stt', expect.anything())
    } finally {
      restoreMediaDevices()
    }
  })

  it('shows unsupported-browser error when MediaRecorder is unavailable', async () => {
    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    const originalWindowMediaRecorder = window.MediaRecorder

    try {
      window.MediaRecorder = undefined

      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))

      expect(await screen.findByRole('heading', { name: 'Error' })).toBeInTheDocument()
      expect(screen.getByText(/does not support recording/i)).toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalledWith('/api/stt', expect.anything())
    } finally {
      window.MediaRecorder = originalWindowMediaRecorder
      restoreMediaDevices()
    }
  })

  it('shows https-required error when microphone APIs are blocked by insecure context', async () => {
    const getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [] })
    const restoreMediaDevices = installMediaDevices(getUserMedia)
    installRecorderMock()

    const originalIsSecureContext = Object.getOwnPropertyDescriptor(window, 'isSecureContext')

    try {
      Object.defineProperty(window, 'isSecureContext', {
        configurable: true,
        value: false,
      })

      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))

      expect(await screen.findByRole('heading', { name: 'Error' })).toBeInTheDocument()
      expect(screen.getByText(/requires https/i)).toBeInTheDocument()
      expect(getUserMedia).not.toHaveBeenCalled()
    } finally {
      if (originalIsSecureContext) {
        Object.defineProperty(window, 'isSecureContext', originalIsSecureContext)
      } else {
        Reflect.deleteProperty(window, 'isSecureContext')
      }
      restoreMediaDevices()
    }
  })

  it('rejects very short recordings and does not call /api/stt', async () => {
    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(100)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(await screen.findByText(/recording is too short/i)).toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalledWith('/api/stt', expect.anything())
    } finally {
      restoreMediaDevices()
    }
  })

  it('rejects recordings smaller than the byte-size floor and does not call /api/stt', async () => {
    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 1500 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(await screen.findByText(/recording is too short/i)).toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalledWith('/api/stt', expect.anything())
    } finally {
      restoreMediaDevices()
    }
  })

  it('shows explicit error when STT response text is empty', async () => {
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        return jsonResponse({ text: '   ', language: 'en' })
      }
      if (resource === '/api/tts') {
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(await screen.findByText(/transcription came back empty/i)).toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalledWith('/api/tts', expect.anything())
    } finally {
      restoreMediaDevices()
    }
  })

  it('offers Retry STT and re-attempts transcription after a failed STT request', async () => {
    let sttAttempts = 0
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        sttAttempts += 1
        return jsonResponse({ detail: 'upstream unavailable' }, 502)
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      const retryButton = await screen.findByRole('button', { name: 'Retry STT' })
      expect(retryButton).toBeInTheDocument()
      expect(sttAttempts).toBe(1)

      await fireEvent.click(retryButton)
      await screen.findByRole('heading', { name: 'Error' })
      expect(sttAttempts).toBe(2)
    } finally {
      restoreMediaDevices()
    }
  })
})

describe('App milestone 4 TTS integration and playback', () => {
  let fetchMock
  let restorePlaybackMocks

  beforeEach(() => {
    restorePlaybackMocks = installPlaybackMocks()
  })

  afterEach(() => {
    if (restorePlaybackMocks) {
      restorePlaybackMocks()
      restorePlaybackMocks = null
    }
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('posts selected voice to /api/tts and shows speaking state during playback', async () => {
    let ttsPayload = null
    fetchMock = vi.fn(async (resource, options = {}) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [
            { voice_id: 'voice-one', name: 'Voice One' },
            { voice_id: 'voice-two', name: 'Voice Two' },
          ],
        })
      }
      if (resource === '/api/stt') {
        return jsonResponse({ text: 'speak this back', language: 'en' })
      }
      if (resource === '/api/tts') {
        ttsPayload = JSON.parse(options.body)
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    class ControlledAudio {
      static instances = []

      constructor() {
        this.onended = null
        this.onerror = null
        this.preload = 'auto'
        ControlledAudio.instances.push(this)
      }

      pause() {
        return undefined
      }

      play() {
        return Promise.resolve()
      }
    }

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)
    vi.stubGlobal('Audio', ControlledAudio)
    window.Audio = ControlledAudio

    try {
      render(App)

      await screen.findByRole('option', { name: 'Voice Two' })
      await fireEvent.change(screen.getByRole('combobox', { name: 'Voice' }), {
        target: { value: 'voice-two' },
      })

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('speaking')
        expect(screen.getByTestId('status-message')).toHaveTextContent('Speaking...')
      })
      expect(ttsPayload).toEqual({ text: 'speak this back', voice_id: 'voice-two' })

      const activeAudio = ControlledAudio.instances.at(-1)
      expect(activeAudio).toBeDefined()
      activeAudio.onended()

      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('idle')
      })
      expect(screen.getByTestId('status-message')).toHaveTextContent('Playback complete')
    } finally {
      restoreMediaDevices()
    }
  })

  it('surfaces TTS HTTP error details and offers Retry TTS', async () => {
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        return jsonResponse({ text: 'retry playback', language: 'en' })
      }
      if (resource === '/api/tts') {
        return jsonResponse({ detail: 'TTS upstream unavailable' }, 502)
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(await screen.findByRole('heading', { name: 'Error' })).toBeInTheDocument()
      expect(screen.getByText('TTS upstream unavailable')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Retry TTS' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Retry STT' })).not.toBeInTheDocument()
    } finally {
      restoreMediaDevices()
    }
  })

  it('surfaces an explicit error when /api/tts returns empty audio', async () => {
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        return jsonResponse({ text: 'retry playback', language: 'en' })
      }
      if (resource === '/api/tts') {
        return new Response(new Uint8Array(), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(await screen.findByRole('heading', { name: 'Error' })).toBeInTheDocument()
      expect(screen.getByText('TTS returned empty audio')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Retry TTS' })).toBeInTheDocument()
    } finally {
      restoreMediaDevices()
    }
  })

  it('surfaces playback errors and allows Retry TTS to recover', async () => {
    let ttsAttempts = 0
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        return jsonResponse({ text: 'retry playback', language: 'en' })
      }
      if (resource === '/api/tts') {
        ttsAttempts += 1
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    class FlakyAudio {
      static playCalls = 0

      constructor() {
        this.onended = null
        this.onerror = null
        this.preload = 'auto'
      }

      pause() {
        return undefined
      }

      play() {
        FlakyAudio.playCalls += 1
        if (FlakyAudio.playCalls === 1) {
          return Promise.reject(new Error('blocked by browser'))
        }
        queueMicrotask(() => {
          if (this.onended) {
            this.onended()
          }
        })
        return Promise.resolve()
      }
    }

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)
    vi.stubGlobal('Audio', FlakyAudio)
    window.Audio = FlakyAudio

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(await screen.findByRole('heading', { name: 'Error' })).toBeInTheDocument()
      expect(screen.getByText(/playback blocked\. tap retry to play audio\./i)).toBeInTheDocument()
      expect(ttsAttempts).toBe(1)

      await fireEvent.click(screen.getByRole('button', { name: 'Retry TTS' }))

      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('idle')
      })
      expect(screen.getByTestId('status-message')).toHaveTextContent('Playback complete')
      expect(screen.queryByRole('heading', { name: 'Error' })).not.toBeInTheDocument()
      expect(ttsAttempts).toBe(2)
    } finally {
      restoreMediaDevices()
    }
  })

  it('hides Retry TTS after a later STT failure to avoid replaying stale transcript', async () => {
    let sttAttempts = 0
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        sttAttempts += 1
        if (sttAttempts === 1) {
          return jsonResponse({ text: 'first transcript', language: 'en' })
        }
        return jsonResponse({ detail: 'upstream unavailable' }, 502)
      }
      if (resource === '/api/tts') {
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('idle')
      })
      expect(screen.getByText('first transcript')).toBeInTheDocument()

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(await screen.findByRole('heading', { name: 'Error' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Retry STT' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Retry TTS' })).not.toBeInTheDocument()
    } finally {
      restoreMediaDevices()
    }
  })
})

describe('App visual milestone 3 end-to-end flow', () => {
  let fetchMock

  beforeEach(() => {
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return jsonResponse({
          text: 'A compact desk setup with a laptop and coffee mug.',
          prompt: 'Describe this image',
          model: 'mistral-large-latest',
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders image controls and keeps Describe disabled until a valid image is selected', async () => {
    render(App)

    expect(screen.getByRole('heading', { name: 'Image Describe' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Take Photo' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upload Photo' })).toBeInTheDocument()

    const cameraInput = screen.getByTestId('take-photo-input')
    expect(cameraInput).toHaveAttribute('accept', 'image/*')
    expect(cameraInput).toHaveAttribute('capture', 'environment')
    expect(cameraInput).toHaveAttribute('tabindex', '-1')
    expect(cameraInput).toHaveAttribute('aria-hidden', 'true')

    const uploadInput = screen.getByTestId('upload-photo-input')
    expect(uploadInput).toHaveAttribute('accept', 'image/*')
    expect(uploadInput).not.toHaveAttribute('capture')
    expect(uploadInput).toHaveAttribute('tabindex', '-1')
    expect(uploadInput).toHaveAttribute('aria-hidden', 'true')

    expect(screen.getByRole('button', { name: 'Describe' })).toBeDisabled()
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('idle')
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent('No image selected')
  })

  it('shows an image preview and enables Describe after selecting a valid image', async () => {
    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([137, 80, 78, 71])], 'sample.png', { type: 'image/png' })

    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })

    expect(screen.getByRole('button', { name: 'Describe' })).toBeEnabled()
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    expect(screen.getByAltText('Selected preview')).toBeInTheDocument()
    expect(screen.getByText('sample.png')).toBeInTheDocument()
  })

  it('shows validation error for unsupported image type and keeps Describe disabled', async () => {
    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const invalidMimeFile = new File(['plain text'], 'notes.txt', { type: 'text/plain' })

    await fireEvent.change(uploadInput, {
      target: { files: [invalidMimeFile] },
    })

    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Unsupported file type. Use JPEG, PNG, or WEBP.')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent(
      'Choose Take Photo or Upload Photo and try again.',
    )
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent('Describe image failed')
    expect(screen.getByTestId('vision-status-message')).toHaveAttribute('aria-live', 'off')
    expect(screen.getByRole('button', { name: 'Describe' })).toBeDisabled()
  })

  it('shows validation error for oversized image files', async () => {
    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const oversizedBytes = new Uint8Array(10 * 1024 * 1024 + 64)
    const oversizedFile = new File([oversizedBytes], 'large-photo.jpg', { type: 'image/jpeg' })

    await fireEvent.change(uploadInput, {
      target: { files: [oversizedFile] },
    })

    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Image exceeds 10MB limit.')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent(
      'Choose Take Photo or Upload Photo and try again.',
    )
    expect(screen.getByRole('button', { name: 'Describe' })).toBeDisabled()
  })

  it('transitions visual status across image_selected, describing, and described', async () => {
    const visionDeferred = createDeferred()
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return visionDeferred.promise
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([255, 216, 255, 224])], 'camera.jpg', { type: 'image/jpeg' })

    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('describing')
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent('Describe image in progress')

    visionDeferred.resolve(
      jsonResponse({
        text: 'A city skyline reflected in water at dusk.',
        prompt: 'Describe this image',
        model: 'mistral-large-latest',
      }),
    )
    expect(await screen.findByText('A city skyline reflected in water at dusk.')).toBeInTheDocument()
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('described')
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent('Description ready')
  })

  it('posts multipart form data to /api/vision and renders the returned text', async () => {
    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([255, 216, 255, 224])], 'camera.jpg', { type: 'image/jpeg' })

    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))

    expect(await screen.findByText('A compact desk setup with a laptop and coffee mug.')).toBeInTheDocument()
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('described')
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent('Description ready')

    const visionCall = fetchMock.mock.calls.find(([resource]) => resource === '/api/vision')
    expect(visionCall).toBeTruthy()
    const [, requestOptions] = visionCall
    expect(requestOptions).toMatchObject({
      method: 'POST',
    })
    expect(requestOptions.body).toBeInstanceOf(FormData)
    const submittedImage = requestOptions.body.get('image')
    expect(submittedImage).toBeInstanceOf(File)
    expect(submittedImage.name).toBe('camera.jpg')
    expect(submittedImage.type).toBe('image/jpeg')
    expect(submittedImage.size).toBe(validFile.size)
  })

  it('wires Take Photo and Upload Photo button clicks to the hidden input click handlers', async () => {
    render(App)

    const takePhotoInput = screen.getByTestId('take-photo-input')
    const uploadPhotoInput = screen.getByTestId('upload-photo-input')
    const takeClickSpy = vi.spyOn(takePhotoInput, 'click')
    const uploadClickSpy = vi.spyOn(uploadPhotoInput, 'click')

    await fireEvent.click(screen.getByRole('button', { name: 'Take Photo' }))
    await fireEvent.click(screen.getByRole('button', { name: 'Upload Photo' }))

    expect(takeClickSpy).toHaveBeenCalledTimes(1)
    expect(uploadClickSpy).toHaveBeenCalledTimes(1)
  })

  it('disables picker buttons while visual describe is in progress', async () => {
    const visionDeferred = createDeferred()
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return visionDeferred.promise
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([255, 216, 255, 224])], 'camera.jpg', { type: 'image/jpeg' })
    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))

    expect(screen.getByRole('button', { name: 'Take Photo' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Upload Photo' })).toBeDisabled()

    visionDeferred.resolve(
      jsonResponse({
        text: 'A cyclist riding along a tree-lined street.',
        prompt: 'Describe this image',
        model: 'mistral-large-latest',
      }),
    )
    await screen.findByText('A cyclist riding along a tree-lined street.')
    expect(screen.getByRole('button', { name: 'Take Photo' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Upload Photo' })).toBeEnabled()
  })

  it('shows vision API error, keeps image selected, and retries with the same image', async () => {
    let visionAttempt = 0
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        visionAttempt += 1
        if (visionAttempt === 1) {
          return jsonResponse({ detail: 'Vision upstream unavailable' }, 502)
        }
        return jsonResponse({
          text: 'A person holding a phone near a window.',
          prompt: 'Describe this image',
          model: 'mistral-large-latest',
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })

    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([255, 216, 255, 224])], 'retry.jpg', { type: 'image/jpeg' })

    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
    await waitFor(() => {
      expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    })
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Vision upstream unavailable')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Tap Describe to retry.')
    expect(screen.getByText('retry.jpg')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Describe' })).toBeEnabled()

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
    expect(await screen.findByText('A person holding a phone near a window.')).toBeInTheDocument()
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('described')

    const visionCalls = fetchMock.mock.calls.filter(([resource]) => resource === '/api/vision')
    expect(visionCalls).toHaveLength(2)
    const firstImage = visionCalls[0][1].body.get('image')
    const secondImage = visionCalls[1][1].body.get('image')
    expect(firstImage).toBeInstanceOf(File)
    expect(secondImage).toBeInstanceOf(File)
    expect(secondImage.name).toBe(firstImage.name)
    expect(secondImage.size).toBe(firstImage.size)
    expect(secondImage.type).toBe(firstImage.type)
  })

  it('ignores stale invalid-json failure from an outdated describe request', async () => {
    const jsonDeferred = createDeferred()
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return {
          ok: true,
          status: 200,
          json: () => jsonDeferred.promise,
        }
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })

    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const firstFile = new File([new Uint8Array([137, 80, 78, 71])], 'first.png', { type: 'image/png' })
    const secondFile = new File([new Uint8Array([255, 216, 255, 224])], 'second.jpg', { type: 'image/jpeg' })

    await fireEvent.change(uploadInput, {
      target: { files: [firstFile] },
    })
    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('describing')

    await fireEvent.change(uploadInput, {
      target: { files: [secondFile] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    expect(screen.getByText('second.jpg')).toBeInTheDocument()

    jsonDeferred.reject(new Error('invalid json payload'))

    await waitFor(() => {
      expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    })
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent('Image selected. Tap Describe.')
    expect(screen.queryByTestId('vision-error-message')).not.toBeInTheDocument()
    expect(screen.queryByText('Vision response was invalid.')).not.toBeInTheDocument()
  })

  it('ignores stale success response from an outdated describe request', async () => {
    const jsonDeferred = createDeferred()
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return {
          ok: true,
          status: 200,
          json: () => jsonDeferred.promise,
        }
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })

    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const firstFile = new File([new Uint8Array([137, 80, 78, 71])], 'first.png', { type: 'image/png' })
    const secondFile = new File([new Uint8Array([255, 216, 255, 224])], 'second.jpg', { type: 'image/jpeg' })

    await fireEvent.change(uploadInput, {
      target: { files: [firstFile] },
    })
    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('describing')

    await fireEvent.change(uploadInput, {
      target: { files: [secondFile] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    expect(screen.getByText('second.jpg')).toBeInTheDocument()

    jsonDeferred.resolve({
      text: 'Outdated description should be ignored.',
      prompt: 'Describe this image',
      model: 'mistral-large-latest',
    })

    await waitFor(() => {
      expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    })
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent('Image selected. Tap Describe.')
    expect(screen.queryByText('Outdated description should be ignored.')).not.toBeInTheDocument()
    expect(screen.queryByTestId('vision-error-message')).not.toBeInTheDocument()
  })

  it('ignores stale non-2xx detail parsing from an outdated describe request', async () => {
    const errorDetailDeferred = createDeferred()
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return {
          ok: false,
          status: 502,
          json: () => errorDetailDeferred.promise,
        }
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })

    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const firstFile = new File([new Uint8Array([137, 80, 78, 71])], 'first.png', { type: 'image/png' })
    const secondFile = new File([new Uint8Array([255, 216, 255, 224])], 'second.jpg', { type: 'image/jpeg' })

    await fireEvent.change(uploadInput, {
      target: { files: [firstFile] },
    })
    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('describing')

    await fireEvent.change(uploadInput, {
      target: { files: [secondFile] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    expect(screen.getByText('second.jpg')).toBeInTheDocument()

    errorDetailDeferred.resolve({ detail: 'Outdated upstream error should be ignored.' })

    await waitFor(() => {
      expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    })
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent('Image selected. Tap Describe.')
    expect(screen.queryByText('Outdated upstream error should be ignored.')).not.toBeInTheDocument()
    expect(screen.queryByTestId('vision-error-message')).not.toBeInTheDocument()
  })

  it('shows retryable error when vision request cannot reach backend', async () => {
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        throw new TypeError('network down')
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })

    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([137, 80, 78, 71])], 'offline.png', { type: 'image/png' })
    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))

    await waitFor(() => {
      expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    })
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Could not reach vision service.')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Tap Describe to retry.')
    expect(screen.getByText('offline.png')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Describe' })).toBeEnabled()
  })

  it('shows retryable error when vision success response has invalid JSON body', async () => {
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return {
          ok: true,
          status: 200,
          json: async () => {
            throw new Error('invalid json body')
          },
        }
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })

    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([137, 80, 78, 71])], 'bad-json.png', { type: 'image/png' })
    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))

    await waitFor(() => {
      expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    })
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Vision response was invalid.')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Tap Describe to retry.')
  })

  it('shows retryable error when vision response text is empty', async () => {
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return jsonResponse({
          text: '   ',
          prompt: 'Describe this image',
          model: 'mistral-large-latest',
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })

    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([137, 80, 78, 71])], 'empty-text.png', { type: 'image/png' })
    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))

    await waitFor(() => {
      expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    })
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent(
      'Vision response did not include description text.',
    )
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Tap Describe to retry.')
  })

  it('falls back to status-based error detail when vision error body is not JSON', async () => {
    fetchMock.mockImplementation(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/vision') {
        return new Response('upstream unavailable', {
          status: 502,
          headers: { 'Content-Type': 'text/plain' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })

    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([137, 80, 78, 71])], 'plain-error.png', { type: 'image/png' })
    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))

    await waitFor(() => {
      expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    })
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Vision request failed with status 502.')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Tap Describe to retry.')
  })

  it('keeps prior valid image selected when an invalid replacement is chosen', async () => {
    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')
    const validFile = new File([new Uint8Array([137, 80, 78, 71])], 'sample.png', { type: 'image/png' })
    const invalidMimeFile = new File(['plain text'], 'notes.txt', { type: 'text/plain' })

    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })
    await fireEvent.change(uploadInput, {
      target: { files: [invalidMimeFile] },
    })

    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Unsupported file type. Use JPEG, PNG, or WEBP.')
    expect(screen.getByTestId('vision-error-message')).toHaveTextContent('Tap Describe to retry.')
    expect(screen.getByText('sample.png')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Describe' })).toBeEnabled()
  })

  it('handles empty file selection for idle, prior-valid, and prior-error paths', async () => {
    render(App)

    const uploadInput = screen.getByTestId('upload-photo-input')

    await fireEvent.change(uploadInput, {
      target: { files: [] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('idle')
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent(
      'No image selected. Choose Take Photo or Upload Photo.',
    )
    expect(screen.queryByTestId('vision-error-message')).not.toBeInTheDocument()

    const initialInvalidMimeFile = new File(['plain text'], 'bad-first.txt', { type: 'text/plain' })
    await fireEvent.change(uploadInput, {
      target: { files: [initialInvalidMimeFile] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    expect(screen.getByTestId('vision-error-message')).toBeInTheDocument()

    await fireEvent.change(uploadInput, {
      target: { files: [] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('idle')
    expect(screen.getByTestId('vision-status-message')).toHaveTextContent(
      'No image selected. Choose Take Photo or Upload Photo.',
    )
    expect(screen.queryByTestId('vision-error-message')).not.toBeInTheDocument()

    const validFile = new File([new Uint8Array([137, 80, 78, 71])], 'sample.png', { type: 'image/png' })
    await fireEvent.change(uploadInput, {
      target: { files: [validFile] },
    })
    await fireEvent.change(uploadInput, {
      target: { files: [] },
    })

    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    expect(screen.getByText('sample.png')).toBeInTheDocument()

    const invalidMimeFile = new File(['plain text'], 'notes.txt', { type: 'text/plain' })
    await fireEvent.change(uploadInput, {
      target: { files: [invalidMimeFile] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('error')
    expect(screen.getByTestId('vision-error-message')).toBeInTheDocument()

    await fireEvent.change(uploadInput, {
      target: { files: [] },
    })
    expect(screen.getByTestId('vision-state-pill')).toHaveTextContent('image_selected')
    expect(screen.getByText('sample.png')).toBeInTheDocument()
    expect(screen.queryByTestId('vision-error-message')).not.toBeInTheDocument()
  })
})

describe('App milestone 5 hardening and stability', () => {
  let fetchMock
  let restorePlaybackMocks

  beforeEach(() => {
    restorePlaybackMocks = installPlaybackMocks()
  })

  afterEach(() => {
    if (restorePlaybackMocks) {
      restorePlaybackMocks()
      restorePlaybackMocks = null
    }
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('clears stale transcript state when a new recording starts', async () => {
    let sttAttempts = 0
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        sttAttempts += 1
        if (sttAttempts === 1) {
          return jsonResponse({ text: 'first transcript', language: 'en' })
        }
        return jsonResponse({ text: 'second transcript', language: 'en' })
      }
      if (resource === '/api/tts') {
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      await screen.findByText('first transcript')
      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('idle')
      })

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))

      expect(screen.queryByText('first transcript')).not.toBeInTheDocument()
      expect(screen.getByText('Your transcript will appear here.')).toBeInTheDocument()
    } finally {
      restoreMediaDevices()
    }
  })

  it('disables non-essential controls while transcription request is in flight', async () => {
    const sttDeferred = createDeferred()
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        return sttDeferred.promise
      }
      if (resource === '/api/tts') {
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('transcribing')
      })
      expect(screen.getByRole('combobox', { name: 'Voice' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'Record' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'idle' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'recording' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'transcribing' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'speaking' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'error' })).toBeDisabled()

      sttDeferred.resolve(jsonResponse({ text: 'deferred transcript', language: 'en' }))
      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('idle')
      })
    } finally {
      restoreMediaDevices()
    }
  })

  it('blocks a second record start while microphone permission request is still pending', async () => {
    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const stopTrack = vi.fn()
    const micPermissionDeferred = createDeferred()
    const getUserMedia = vi.fn().mockReturnValue(micPermissionDeferred.promise)
    const restoreMediaDevices = installMediaDevices(getUserMedia)
    installRecorderMock({ chunkBytes: 4096 })

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))

      expect(getUserMedia).toHaveBeenCalledTimes(1)
      expect(screen.getByRole('button', { name: 'Record' })).toBeDisabled()
      expect(screen.getByTestId('status-message')).toHaveTextContent('Requesting microphone access...')

      micPermissionDeferred.resolve({ getTracks: () => [{ stop: stopTrack }] })
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
      })
    } finally {
      restoreMediaDevices()
    }
  })

  it('keeps controls disabled while retry tts request is in flight', async () => {
    const retryTtsDeferred = createDeferred()
    let ttsAttempts = 0

    fetchMock = vi.fn(async (resource) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        return jsonResponse({ text: 'retry me', language: 'en' })
      }
      if (resource === '/api/tts') {
        ttsAttempts += 1
        if (ttsAttempts === 1) {
          return jsonResponse({ detail: 'TTS upstream unavailable' }, 502)
        }
        return retryTtsDeferred.promise
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
      await screen.findByRole('button', { name: 'Retry TTS' })

      await fireEvent.click(screen.getByRole('button', { name: 'Retry TTS' }))

      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('speaking')
      })
      expect(screen.getByRole('combobox', { name: 'Voice' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'Record' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'idle' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'recording' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'transcribing' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'speaking' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'error' })).toBeDisabled()

      retryTtsDeferred.resolve(
        new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        }),
      )
      await waitFor(() => {
        expect(screen.getByTestId('state-pill')).toHaveTextContent('idle')
      })
      expect(screen.getByTestId('status-message')).toHaveTextContent('Playback complete')
    } finally {
      restoreMediaDevices()
    }
  })

  it('sends browser requests only to proxy endpoints without provider API auth headers', async () => {
    let sttHeaders = null
    let ttsHeaders = null
    let visionHeaders = null

    fetchMock = vi.fn(async (resource, options = {}) => {
      if (resource === '/api/voices') {
        return jsonResponse({
          voices: [{ voice_id: 'voice-one', name: 'Voice One' }],
        })
      }
      if (resource === '/api/stt') {
        sttHeaders = options.headers ?? {}
        return jsonResponse({ text: 'header check', language: 'en' })
      }
      if (resource === '/api/tts') {
        ttsHeaders = options.headers ?? {}
        return new Response(new Uint8Array([73, 68, 51]), {
          status: 200,
          headers: { 'Content-Type': 'audio/mpeg' },
        })
      }
      if (resource === '/api/vision') {
        visionHeaders = options.headers ?? {}
        return jsonResponse({
          text: 'proxy header vision',
          prompt: 'Describe this image',
          model: 'mistral-large-latest',
        })
      }
      return jsonResponse({ detail: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)

    const restoreMediaDevices = installMediaDevices(vi.fn().mockResolvedValue({ getTracks: () => [] }))
    installRecorderMock({ chunkBytes: 4096 })
    installDateNowIncrementMock(400)

    try {
      render(App)

      await fireEvent.click(screen.getByRole('button', { name: 'Record' }))
      await fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
      await screen.findByText('header check')

      const uploadInput = screen.getByTestId('upload-photo-input')
      const validFile = new File([new Uint8Array([137, 80, 78, 71])], 'proxy.png', { type: 'image/png' })
      await fireEvent.change(uploadInput, {
        target: { files: [validFile] },
      })
      await fireEvent.click(screen.getByRole('button', { name: 'Describe' }))
      await screen.findByText('proxy header vision')

      const calledUrls = fetchMock.mock.calls.map(([resource]) => resource)
      expect(calledUrls).toContain('/api/voices')
      expect(calledUrls).toContain('/api/stt')
      expect(calledUrls).toContain('/api/tts')
      expect(calledUrls).toContain('/api/vision')
      expect(calledUrls.every((resource) => typeof resource === 'string' && resource.startsWith('/api/'))).toBe(
        true,
      )

      expect(Object.keys(sttHeaders)).toEqual([])
      expect(ttsHeaders).toEqual({ 'Content-Type': 'application/json' })
      expect(ttsHeaders.authorization ?? ttsHeaders.Authorization).toBeUndefined()
      expect(ttsHeaders['xi-api-key']).toBeUndefined()
      expect(Object.keys(visionHeaders)).toEqual([])
      expect(visionHeaders.authorization ?? visionHeaders.Authorization).toBeUndefined()
      expect(visionHeaders['xi-api-key']).toBeUndefined()
    } finally {
      restoreMediaDevices()
    }
  })
})
