let active = null
let orphanedStopped = null

function getPreferredMimeType() {
  const preferred = 'audio/webm;codecs=opus'
  if (typeof window === 'undefined' || typeof window.MediaRecorder === 'undefined') {
    return ''
  }
  if (MediaRecorder.isTypeSupported(preferred)) {
    return preferred
  }
  if (MediaRecorder.isTypeSupported('audio/webm')) {
    return 'audio/webm'
  }
  return ''
}

function stopTracks(stream) {
  if (!stream) {
    return
  }
  for (const track of stream.getTracks()) {
    try {
      track.stop()
    } catch {
      // no-op
    }
  }
}

export function isRecording() {
  return Boolean(active && active.recorder && active.recorder.state === 'recording')
}

export async function startRecording() {
  if (active) {
    return active
  }

  orphanedStopped = null

  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('Microphone access is not available.')
  }

  const mimeType = getPreferredMimeType()
  if (!mimeType) {
    throw new Error('MediaRecorder does not support Opus webm recording.')
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  })

  const chunks = []
  const recorder = new MediaRecorder(stream, { mimeType })

  let resolveStop = null
  let rejectStop = null
  const stopped = new Promise((resolve, reject) => {
    resolveStop = resolve
    rejectStop = reject
  })

  recorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      chunks.push(event.data)
    }
  }

  recorder.onerror = () => {
    stopTracks(stream)
    if (active && active.recorder === recorder) {
      orphanedStopped = stopped
      active = null
    }
    if (typeof rejectStop === 'function') {
      rejectStop(new Error('Recording failed.'))
    }
  }

  recorder.onstop = () => {
    stopTracks(stream)
    const blob = new Blob(chunks, { type: recorder.mimeType || mimeType || 'audio/webm' })
    if (typeof resolveStop === 'function') {
      resolveStop(blob)
    }
    if (active && active.recorder === recorder) {
      orphanedStopped = stopped
      active = null
    }
  }

  recorder.start(200)
  active = { recorder, stream, stopped, startedAt: Date.now(), mimeType }
  return active
}

export async function stopRecording() {
  if (!active) {
    if (orphanedStopped) {
      const stopped = orphanedStopped
      orphanedStopped = null
      return stopped
    }
    throw new Error('No recording is active.')
  }

  const { recorder, stopped } = active
  active = null
  orphanedStopped = null

  if (recorder.state !== 'inactive') {
    recorder.stop()
  }

  return stopped
}
