<script>
  import { onMount } from 'svelte'

  const STATE_IDLE = 'idle'
  const STATE_RECORDING = 'recording'
  const STATE_TRANSCRIBING = 'transcribing'
  const STATE_SPEAKING = 'speaking'
  const STATE_ERROR = 'error'
  const PREVIEW_STATES = [
    STATE_IDLE,
    STATE_RECORDING,
    STATE_TRANSCRIBING,
    STATE_SPEAKING,
    STATE_ERROR,
  ]
  const PREVIEW_STATUS = {
    [STATE_IDLE]: 'Ready',
    [STATE_RECORDING]: 'Recording preview active',
    [STATE_TRANSCRIBING]: 'Transcribing preview...',
    [STATE_SPEAKING]: 'Speaking preview...',
    [STATE_ERROR]: 'Previewing error state',
  }

  const MIN_RECORDING_MS = 350
  const MIN_AUDIO_BYTES = 2048
  const FALLBACK_VOICES = [
    { voice_id: 'JBFqnCBsd6RMkjVDRZzb', name: 'George', language: 'EN' },
    { voice_id: 'EXAVITQu4vr4xnSDxMaL', name: 'Bella', language: 'EN' },
    { voice_id: 'pNInz6obpgDQGcFmaJgB', name: 'Adam', language: 'EN' },
    { voice_id: 'B8gJV1IhpuegLxdpXFOE', name: 'Kuon', language: 'JP' },
    { voice_id: 'j210dv0vWm7fCknyQpbA', name: 'Hinata', language: 'JP' },
    { voice_id: '3JDquces8E8bkmvbh6Bc', name: 'Otani', language: 'JP' },
  ]
  const VISION_STATE_IDLE = 'idle'
  const VISION_STATE_IMAGE_SELECTED = 'image_selected'
  const VISION_STATE_DESCRIBING = 'describing'
  const VISION_STATE_DESCRIBED = 'described'
  const VISION_STATE_ERROR = 'error'
  const VISION_ALLOWED_MIME_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
  const VISION_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
  const VISION_NO_SELECTION_STATUS = 'No image selected'
  const VISION_NO_SELECTION_GUIDANCE = 'No image selected. Choose Take Photo or Upload Photo.'

  let uiState = STATE_IDLE
  let statusMessage = 'Ready'
  let transcript = ''
  let errorMessage = ''
  let lastFailedStage = ''

  let voices = []
  let selectedVoiceId = ''

  let mediaRecorder = null
  let mediaStream = null
  let recordingSessionCounter = 0
  let currentRecordingSessionId = 0
  const droppedRecordingSessionIds = new Set()
  let lastRecordingBlob = null

  let currentAudio = null
  let currentAudioUrl = ''
  let requestInFlight = false
  let micPermissionInFlight = false
  let visionState = VISION_STATE_IDLE
  let visionStatusMessage = VISION_NO_SELECTION_STATUS
  let visionDescription = ''
  let visionErrorMessage = ''
  let selectedImageFile = null
  let selectedImageName = ''
  let selectedImagePreviewUrl = ''
  let selectedImagePreviewRevocable = false
  let takePhotoInputElement = null
  let uploadPhotoInputElement = null
  // Tracks visual-flow sequence changes (selection and describe) for stale-result guards.
  let visionSequenceCounter = 0

  const isRecording = () => uiState === STATE_RECORDING
  const isBusy = () => uiState === STATE_TRANSCRIBING || uiState === STATE_SPEAKING
  const isRecordActionDisabled = () => isBusy() || requestInFlight || micPermissionInFlight

  onMount(() => {
    loadVoices().catch((error) => {
      console.error('Unexpected loadVoices failure:', error)
    })
    return () => {
      stopTracks()
      stopAudio()
      releaseImagePreview()
    }
  })

  function stopTracks(targetStream = mediaStream) {
    if (!targetStream) {
      return
    }
    for (const track of targetStream.getTracks()) {
      track.stop()
    }
    if (targetStream === mediaStream) {
      mediaStream = null
    }
  }

  function stopAudio() {
    if (currentAudio) {
      currentAudio.pause()
      currentAudio = null
    }
    if (currentAudioUrl) {
      URL.revokeObjectURL(currentAudioUrl)
      currentAudioUrl = ''
    }
  }

  function releaseImagePreview() {
    if (selectedImagePreviewUrl && selectedImagePreviewRevocable && typeof URL.revokeObjectURL === 'function') {
      URL.revokeObjectURL(selectedImagePreviewUrl)
    }
    selectedImagePreviewUrl = ''
    selectedImagePreviewRevocable = false
  }

  function resetVisionSelection() {
    selectedImageFile = null
    selectedImageName = ''
    releaseImagePreview()
  }

  function setError(stage, message) {
    uiState = STATE_ERROR
    errorMessage = message
    lastFailedStage = stage
    statusMessage = stage === 'stt' ? 'Transcription failed' : 'Playback failed'
  }

  function clearError() {
    errorMessage = ''
    lastFailedStage = ''
  }

  function previewState(state) {
    if (!PREVIEW_STATES.includes(state)) {
      return
    }

    if (mediaRecorder?.state === 'recording') {
      droppedRecordingSessionIds.add(currentRecordingSessionId)
      mediaRecorder.stop()
    }

    if (state !== STATE_SPEAKING) {
      stopAudio()
    }

    uiState = state
    statusMessage = PREVIEW_STATUS[state]

    if (state === STATE_ERROR) {
      errorMessage = 'Example error message for layout checks.'
      lastFailedStage = 'stt'
      return
    }

    clearError()
  }

  function getRecorderMimeType() {
    const preferred = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
    for (const type of preferred) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type
      }
    }
    return ''
  }

  function isSecureOrigin() {
    if (typeof window.isSecureContext === 'boolean') {
      return window.isSecureContext
    }

    const protocol = window.location?.protocol ?? ''
    const hostname = window.location?.hostname ?? ''
    if (protocol === 'https:') {
      return true
    }
    return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
  }

  function getRecordingSupportError() {
    if (!isSecureOrigin()) {
      return 'Recording requires HTTPS on phones. Open this page over https:// (or localhost).'
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      return 'This browser cannot access the microphone from this page.'
    }
    if (typeof window.MediaRecorder === 'undefined') {
      return 'This browser does not support recording with MediaRecorder.'
    }
    return ''
  }

  async function loadVoices() {
    try {
      const response = await fetch('/api/voices')
      if (!response.ok) {
        throw new Error('failed to load voice list')
      }
      const payload = await response.json()
      voices = payload.voices ?? FALLBACK_VOICES
    } catch {
      voices = FALLBACK_VOICES
    }

    if (!selectedVoiceId && voices.length > 0) {
      selectedVoiceId = voices[0].voice_id
    }
  }

  function formatVoiceLabel(voice) {
    const language = typeof voice.language === 'string' ? voice.language.trim().toUpperCase() : ''
    if (!language) {
      return voice.name
    }
    return `${voice.name} (${language})`
  }

  function launchTakePhotoPicker() {
    if (visionState === VISION_STATE_DESCRIBING) {
      return
    }
    takePhotoInputElement?.click()
  }

  function launchUploadPhotoPicker() {
    if (visionState === VISION_STATE_DESCRIBING) {
      return
    }
    uploadPhotoInputElement?.click()
  }

  function validateImageFile(file) {
    if (!VISION_ALLOWED_MIME_TYPES.has(file.type)) {
      return 'Unsupported file type. Use JPEG, PNG, or WEBP.'
    }
    if (file.size > VISION_MAX_UPLOAD_BYTES) {
      return 'Image exceeds 10MB limit.'
    }
    return ''
  }

  async function buildImagePreview(file) {
    if (typeof URL.createObjectURL === 'function') {
      return { url: URL.createObjectURL(file), revocable: true }
    }

    const fileReaderResult = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        if (typeof reader.result === 'string') {
          resolve(reader.result)
          return
        }
        reject(new Error('invalid file preview payload'))
      }
      reader.onerror = () => {
        reject(new Error('file read failed'))
      }
      reader.readAsDataURL(file)
    })

    return { url: fileReaderResult, revocable: false }
  }

  async function assignSelectedImage(file) {
    const { url, revocable } = await buildImagePreview(file)
    releaseImagePreview()
    selectedImageFile = file
    selectedImageName = file.name
    selectedImagePreviewUrl = url
    selectedImagePreviewRevocable = revocable
  }

  function setVisionError(message, options = {}) {
    const guidance = options.allowRetry ? 'Tap Describe to retry.' : 'Choose Take Photo or Upload Photo and try again.'
    visionState = VISION_STATE_ERROR
    visionErrorMessage = `${message} ${guidance}`
    visionStatusMessage = 'Describe image failed'
    visionDescription = ''
  }

  async function getVisionFailureDetail(response) {
    try {
      const payload = await response.json()
      if (typeof payload?.detail === 'string' && payload.detail.trim()) {
        return payload.detail.trim()
      }
    } catch {
      // Fall through to status-derived fallback.
    }
    return `Vision request failed with status ${response.status}.`
  }

  async function handleImageInput(event) {
    const fileInput = event.currentTarget
    const imageFile = fileInput?.files?.[0] ?? null
    if (fileInput) {
      fileInput.value = ''
    }

    if (!imageFile) {
      visionErrorMessage = ''
      if (!selectedImageFile) {
        visionState = VISION_STATE_IDLE
        visionStatusMessage = VISION_NO_SELECTION_GUIDANCE
        visionDescription = ''
        return
      }

      if (visionState === VISION_STATE_ERROR) {
        visionState = VISION_STATE_IMAGE_SELECTED
        visionStatusMessage = 'Image selected. Tap Describe.'
      }
      return
    }

    const hadSelectedImage = Boolean(selectedImageFile)
    visionSequenceCounter += 1
    visionErrorMessage = ''
    visionDescription = ''

    const validationError = validateImageFile(imageFile)
    if (validationError) {
      if (!hadSelectedImage) {
        resetVisionSelection()
      }
      setVisionError(validationError, { allowRetry: hadSelectedImage })
      return
    }

    try {
      await assignSelectedImage(imageFile)
    } catch {
      if (!hadSelectedImage) {
        resetVisionSelection()
      }
      setVisionError('Could not preview image. Try a different photo.', { allowRetry: hadSelectedImage })
      return
    }

    visionState = VISION_STATE_IMAGE_SELECTED
    visionStatusMessage = 'Image selected. Tap Describe.'
  }

  async function describeSelectedImage() {
    if (!selectedImageFile || visionState === VISION_STATE_DESCRIBING) {
      return
    }

    const requestId = ++visionSequenceCounter
    visionErrorMessage = ''
    visionDescription = ''
    visionState = VISION_STATE_DESCRIBING
    visionStatusMessage = 'Describe image in progress...'

    const requestBody = new FormData()
    requestBody.append('image', selectedImageFile)

    let response = null
    try {
      response = await fetch('/api/vision', {
        method: 'POST',
        body: requestBody,
      })
    } catch {
      if (requestId !== visionSequenceCounter) {
        return
      }
      setVisionError('Could not reach vision service.', { allowRetry: true })
      return
    }

    if (requestId !== visionSequenceCounter) {
      return
    }

    if (!response.ok) {
      const detail = await getVisionFailureDetail(response)
      if (requestId !== visionSequenceCounter) {
        return
      }
      setVisionError(detail, { allowRetry: true })
      return
    }

    let payload = null
    try {
      payload = await response.json()
    } catch {
      if (requestId !== visionSequenceCounter) {
        return
      }
      setVisionError('Vision response was invalid.', { allowRetry: true })
      return
    }

    if (requestId !== visionSequenceCounter) {
      return
    }

    const responseText = typeof payload?.text === 'string' ? payload.text.trim() : ''
    if (!responseText) {
      setVisionError('Vision response did not include description text.', { allowRetry: true })
      return
    }

    visionState = VISION_STATE_DESCRIBED
    visionStatusMessage = 'Description ready'
    visionDescription = responseText
  }

  async function startRecording() {
    if (isRecording() || isRecordActionDisabled()) {
      return
    }
    const supportError = getRecordingSupportError()
    if (supportError) {
      setError('stt', supportError)
      return
    }

    clearError()
    transcript = ''
    lastRecordingBlob = null
    statusMessage = 'Requesting microphone access...'
    micPermissionInFlight = true

    let grantedStream = null
    try {
      stopAudio()
      grantedStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
    } catch {
      setError('stt', 'Microphone permission denied. Allow access and try again.')
      micPermissionInFlight = false
      return
    }
    micPermissionInFlight = false
    mediaStream = grantedStream

    const recordingStartedAt = Date.now()
    const recordingChunks = []
    const sessionId = ++recordingSessionCounter
    const options = {}
    const mimeType = getRecorderMimeType()
    if (mimeType) {
      options.mimeType = mimeType
    }

    const stream = mediaStream
    const recorder = new MediaRecorder(stream, options)
    mediaRecorder = recorder
    currentRecordingSessionId = sessionId

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordingChunks.push(event.data)
      }
    }
    recorder.onerror = () => {
      const isActiveSession = mediaRecorder === recorder && currentRecordingSessionId === sessionId
      stopTracks(stream)

      if (!isActiveSession) {
        return
      }

      mediaRecorder = null
      currentRecordingSessionId = 0
      setError('stt', 'Recording failed. Please try again.')
    }
    recorder.onstop = () => {
      const recordedMimeType = recorder.mimeType || 'audio/webm'
      stopTracks(stream)
      if (mediaRecorder === recorder) {
        mediaRecorder = null
      }
      if (currentRecordingSessionId === sessionId) {
        currentRecordingSessionId = 0
      }

      if (droppedRecordingSessionIds.has(sessionId)) {
        droppedRecordingSessionIds.delete(sessionId)
        return
      }

      const blob = new Blob(recordingChunks, { type: recordedMimeType })
      processRecording(blob, Date.now() - recordingStartedAt).catch((error) => {
        console.error('Unexpected processRecording failure:', error)
        if (error instanceof Error && error.message.trim()) {
          setError('stt', error.message)
          return
        }
        setError('stt', 'Recording processing failed. Please try again.')
      })
    }

    recorder.start(200)
    uiState = STATE_RECORDING
    statusMessage = 'Recording... tap Stop when finished'
  }

  function stopRecording() {
    if (!mediaRecorder || mediaRecorder.state !== 'recording') {
      return
    }
    uiState = STATE_TRANSCRIBING
    statusMessage = 'Transcribing...'
    mediaRecorder.stop()
  }

  async function processRecording(blob, elapsedMs = MIN_RECORDING_MS) {
    if (elapsedMs < MIN_RECORDING_MS || blob.size < MIN_AUDIO_BYTES) {
      setError('stt', 'Recording is too short. Hold record a bit longer.')
      return
    }

    lastRecordingBlob = blob
    requestInFlight = true
    if (uiState !== STATE_TRANSCRIBING) {
      uiState = STATE_TRANSCRIBING
      statusMessage = 'Transcribing...'
    }

    try {
      transcript = await sendToStt(blob)
    } catch (error) {
      requestInFlight = false
      setError('stt', error.message)
      return
    }

    try {
      await runTtsPlayback(transcript)
      requestInFlight = false
      uiState = STATE_IDLE
      statusMessage = 'Playback complete'
      clearError()
    } catch (error) {
      requestInFlight = false
      setError('tts', error.message)
    }
  }

  async function sendToStt(blob) {
    const formData = new FormData()
    formData.append('audio', blob, `recording-${Date.now()}.webm`)
    formData.append('language', 'en')

    const response = await fetch('/api/stt', { method: 'POST', body: formData })
    if (!response.ok) {
      const detail = await readErrorDetail(response, 'STT request failed')
      throw new Error(detail)
    }

    const payload = await response.json()
    const text = (payload.text ?? '').trim()
    if (!text) {
      throw new Error('Transcription came back empty')
    }
    return text
  }

  async function runTtsPlayback(text) {
    uiState = STATE_SPEAKING
    statusMessage = 'Generating speech...'

    const response = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice_id: selectedVoiceId }),
    })

    if (!response.ok) {
      const detail = await readErrorDetail(response, 'TTS request failed')
      throw new Error(detail)
    }

    const audioBlob = await response.blob()
    if (audioBlob.size === 0) {
      throw new Error('TTS returned empty audio')
    }

    await playAudioBlob(audioBlob)
  }

  async function playAudioBlob(audioBlob) {
    stopAudio()
    statusMessage = 'Speaking...'
    currentAudioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(currentAudioUrl)
    currentAudio = audio

    await new Promise((resolve, reject) => {
      audio.onended = () => {
        stopAudio()
        resolve()
      }
      audio.onerror = () => {
        stopAudio()
        reject(new Error('Audio playback failed'))
      }
      const playPromise = audio.play()
      if (playPromise) {
        playPromise.catch(() => {
          stopAudio()
          reject(new Error('Playback blocked. Tap retry to play audio.'))
        })
      }
    })
  }

  async function retryStt() {
    if (!lastRecordingBlob || requestInFlight || isRecording()) {
      return
    }
    clearError()
    await processRecording(lastRecordingBlob)
  }

  async function retryTts() {
    if (lastFailedStage !== 'tts' || requestInFlight || isRecording()) {
      return
    }
    const text = transcript.trim()
    if (!text) {
      return
    }
    clearError()
    requestInFlight = true
    try {
      await runTtsPlayback(text)
      requestInFlight = false
      uiState = STATE_IDLE
      statusMessage = 'Playback complete'
    } catch (error) {
      requestInFlight = false
      setError('tts', error.message)
    }
  }

  async function readErrorDetail(response, fallback) {
    try {
      const payload = await response.json()
      if (typeof payload.detail === 'string' && payload.detail.trim()) {
        return payload.detail
      }
    } catch {
      // Ignore JSON parse failures and use fallback below.
    }
    return `${fallback} (HTTP ${response.status})`
  }
</script>

<main class="shell">
  <header class="card">
    <h1>Voice Loop Prototype</h1>
    <p>Record speech, transcribe, then synthesize playback.</p>
  </header>

  <section class={`card controls state-surface state-${uiState}`}>
    <label for="voice-select">Voice</label>
    <select
      id="voice-select"
      bind:value={selectedVoiceId}
      disabled={isRecording() || isBusy() || requestInFlight || micPermissionInFlight}
    >
      {#each voices as voice}
        <option value={voice.voice_id}>{formatVoiceLabel(voice)}</option>
      {/each}
    </select>
    <p class="voice-note">Recommended for Japanese: Otani (JP).</p>

    {#if isRecording()}
      <button class="action action-stop" onclick={stopRecording}>Stop</button>
    {:else}
      <button class="action action-record" onclick={startRecording} disabled={isRecordActionDisabled()}>
        Record
      </button>
    {/if}

    <p class={`state-pill state-${uiState}`} data-testid="state-pill">{uiState}</p>
    <p class="status" role="status" aria-live="polite" data-testid="status-message">{statusMessage}</p>
  </section>

  <section class="card state-preview">
    <h2>State Preview</h2>
    <p class="preview-copy">Use these buttons to preview all UI states without API calls.</p>
    <div class="preview-grid">
      {#each PREVIEW_STATES as state}
        <button
          class={`preview-button preview-${state} ${uiState === state ? 'is-active' : ''}`}
          onclick={() => previewState(state)}
          disabled={requestInFlight || micPermissionInFlight}
        >
          {state}
        </button>
      {/each}
    </div>
  </section>

  <section class="card vision">
    <h2>Image Describe</h2>
    <p class="preview-copy">
      Capture from camera or upload from gallery/desktop, then run Describe on the selected image.
    </p>

    <input
      class="hidden-file-input"
      bind:this={takePhotoInputElement}
      type="file"
      accept="image/*"
      capture="environment"
      data-testid="take-photo-input"
      aria-hidden="true"
      tabindex="-1"
      onchange={handleImageInput}
    />
    <input
      class="hidden-file-input"
      bind:this={uploadPhotoInputElement}
      type="file"
      accept="image/*"
      data-testid="upload-photo-input"
      aria-hidden="true"
      tabindex="-1"
      onchange={handleImageInput}
    />

    <div class="vision-actions">
      <button class="secondary" type="button" onclick={launchTakePhotoPicker} disabled={visionState === VISION_STATE_DESCRIBING}>
        Take Photo
      </button>
      <button class="secondary" type="button" onclick={launchUploadPhotoPicker} disabled={visionState === VISION_STATE_DESCRIBING}>
        Upload Photo
      </button>
    </div>

    <button
      class="action action-describe"
      type="button"
      onclick={describeSelectedImage}
      disabled={!selectedImageFile || visionState === VISION_STATE_DESCRIBING}
    >
      Describe
    </button>

    <p class={`state-pill vision-state-pill vision-state-${visionState}`} data-testid="vision-state-pill">{visionState}</p>
    <p class="status" aria-live={visionState === VISION_STATE_ERROR ? 'off' : 'polite'} data-testid="vision-status-message">
      {visionStatusMessage}
    </p>

    {#if visionErrorMessage}
      <p class="vision-error" data-testid="vision-error-message" role="alert">{visionErrorMessage}</p>
    {/if}

    <div class="vision-preview">
      {#if selectedImagePreviewUrl}
        <img src={selectedImagePreviewUrl} alt="Selected preview" />
        <p class="vision-file-name">{selectedImageName}</p>
      {:else}
        <p class="placeholder">No image selected yet.</p>
      {/if}
    </div>
  </section>

  <section class="card vision-description">
    <h2>Image Description</h2>
    {#if visionDescription}
      <p>{visionDescription}</p>
    {:else}
      <p class="placeholder">Description output will appear here.</p>
    {/if}
  </section>

  <section class="card transcript">
    <h2>Transcript</h2>
    {#if transcript}
      <p>{transcript}</p>
    {:else}
      <p class="placeholder">Your transcript will appear here.</p>
    {/if}
  </section>

  {#if errorMessage}
    <section class="card error">
      <h2>Error</h2>
      <p>{errorMessage}</p>
      <div class="retry-row">
        {#if lastFailedStage === 'stt' && lastRecordingBlob}
          <button
            class="secondary"
            onclick={retryStt}
            disabled={requestInFlight || micPermissionInFlight || isRecording()}
          >
            Retry STT
          </button>
        {/if}
        {#if lastFailedStage === 'tts' && transcript}
          <button
            class="secondary"
            onclick={retryTts}
            disabled={requestInFlight || micPermissionInFlight || isRecording()}
          >
            Retry TTS
          </button>
        {/if}
      </div>
    </section>
  {/if}
</main>
