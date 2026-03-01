/**
 * VAD (Voice Activity Detection) wrapper using @ricky0123/vad-web + SileroVAD.
 *
 * Loaded via CDN in index.html — the global `vad` object is available at runtime.
 * Provides start/pause/destroy lifecycle and calls back with a WAV blob when
 * speech ends, ready for upload to /api/voice/transcribe.
 */

let instance = null
let onSpeechEndCallback = null
let onSpeechStartCallback = null
let onVADMisfireCallback = null

/**
 * Convert a Float32Array of PCM samples (16 kHz mono) to a WAV blob.
 */
export function float32ToWavBlob(float32, sampleRate = 16000) {
  const numChannels = 1
  const bitsPerSample = 16
  const byteRate = sampleRate * numChannels * (bitsPerSample / 8)
  const blockAlign = numChannels * (bitsPerSample / 8)
  const dataSize = float32.length * (bitsPerSample / 8)
  const headerSize = 44
  const buffer = new ArrayBuffer(headerSize + dataSize)
  const view = new DataView(buffer)

  // RIFF header
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(view, 8, 'WAVE')

  // fmt sub-chunk
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true) // sub-chunk size
  view.setUint16(20, 1, true) // PCM format
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, byteRate, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, bitsPerSample, true)

  // data sub-chunk
  writeString(view, 36, 'data')
  view.setUint32(40, dataSize, true)

  // PCM samples — clamp and convert float32 → int16
  let offset = headerSize
  for (let i = 0; i < float32.length; i++) {
    const sample = Math.max(-1, Math.min(1, float32[i]))
    const int16 = sample < 0 ? sample * 0x8000 : sample * 0x7FFF
    view.setInt16(offset, int16, true)
    offset += 2
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i))
  }
}

/**
 * Initialize and start the VAD.
 *
 * @param {Object} options
 * @param {function(Blob): void} options.onSpeechEnd — called with a WAV blob when speech ends
 * @param {function(): void} [options.onSpeechStart] — called when speech begins
 * @param {function(): void} [options.onVADMisfire] — called on false positive
 * @returns {Promise<void>}
 */
export async function startVAD({ onSpeechEnd, onSpeechStart, onVADMisfire } = {}) {
  if (instance) {
    await instance.start()
    return
  }

  if (typeof window === 'undefined' || !window.vad?.MicVAD) {
    throw new Error('VAD library not loaded. Check CDN scripts in index.html.')
  }

  onSpeechEndCallback = onSpeechEnd || null
  onSpeechStartCallback = onSpeechStart || null
  onVADMisfireCallback = onVADMisfire || null

  instance = await window.vad.MicVAD.new({
    onSpeechEnd: (audio) => {
      if (typeof onSpeechEndCallback === 'function') {
        const wavBlob = float32ToWavBlob(audio)
        onSpeechEndCallback(wavBlob)
      }
    },
    onSpeechStart: () => {
      if (typeof onSpeechStartCallback === 'function') {
        onSpeechStartCallback()
      }
    },
    onVADMisfire: () => {
      if (typeof onVADMisfireCallback === 'function') {
        onVADMisfireCallback()
      }
    },
  })

  await instance.start()
}

/**
 * Pause the VAD (stop listening without destroying).
 * Use during TTS playback to avoid feedback.
 */
export async function pauseVAD() {
  if (instance) {
    instance.pause()
  }
}

/**
 * Resume the VAD after pausing.
 */
export async function resumeVAD() {
  if (instance) {
    await instance.start()
  }
}

/**
 * Destroy the VAD instance and release microphone.
 */
export async function destroyVAD() {
  if (instance) {
    instance.pause()
    instance.destroy()
    instance = null
  }
  onSpeechEndCallback = null
  onSpeechStartCallback = null
  onVADMisfireCallback = null
}

/**
 * Check if VAD is currently active.
 */
export function isVADActive() {
  return instance !== null
}
