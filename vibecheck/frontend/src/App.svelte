<script>
  import { onDestroy, onMount, tick } from 'svelte'
  import ApprovalPanel from './components/ApprovalPanel.svelte'
  import ChatMessage from './components/ChatMessage.svelte'
  import HeaderBar from './components/HeaderBar.svelte'
  import InputBar from './components/InputBar.svelte'
  import SessionPicker from './components/SessionPicker.svelte'
  import SettingsPanel from './components/SettingsPanel.svelte'
  import StatusLine from './components/StatusLine.svelte'
  import ToolCallCard from './components/ToolCallCard.svelte'
  import {
    clearStoredPsk,
    clearStoredSessionId,
    loadInitialPsk,
    storePsk,
    storeSessionId,
  } from './lib/auth'
  import { subscribeToPush, unsubscribeFromPush, isPushSupported } from './lib/push'
  import {
    loadNotificationsEnabled,
    loadVoiceLanguage,
    storeNotificationsEnabled,
    storeVoiceLanguage,
  } from './lib/settings'
  import { startVAD, pauseVAD, resumeVAD, destroyVAD } from './lib/vad'
  import { createWebSocket } from './lib/ws'
  import { connection } from './stores/connection'
  import {
    appendEvent,
    events,
    latestStats,
    mergeEvents,
    pendingApproval,
    pendingInput,
    resetEvents,
    toolResultsByCall,
  } from './stores/events'

  const query = new URLSearchParams(window.location.search)

  const initialSessionId = query.get('sid') || query.get('session_id') || ''
  const initialAction = query.get('action') || ''
  const initialCallId = query.get('call_id') || ''
  const initialNotificationSource = query.get('notif_source') || ''

  let psk = loadInitialPsk()
  let pskDraft = psk
  let sessionId = initialSessionId
  let sessions = []
  let sessionError = ''
  let streamElement = null
  let socketClient = null
  let refreshTimer = null
  let activeSessionId = ''
  let voiceLanguage = loadVoiceLanguage()
  let notificationsEnabled = loadNotificationsEnabled()
  let notificationsError = ''
  let notificationsBusy = false
  let notificationActionBusy = false
  let sessionsLoading = false
  let resumeBusy = ''
  let pskSettingsDraft = ''
  let sessionPickerOpen = true
  let settingsOpen = false
  let talkerActive = false
  let talkerState = 'idle'
  let talkerAudio = null
  let talkerTtsAbort = null
  let talkerSttAbort = null
  let talkerSubmitAssistantCount = 0

  const EVENT_CACHE_PREFIX = 'vibecheck_events_'
  const EVENT_CACHE_LIMIT = 50
  const NOTIFICATION_TRACE_KEY = 'vibecheck_notification_trace'
  const NOTIFICATION_TRACE_CONSOLE_KEY = 'vibecheck_notification_trace_console'
  const NOTIFICATION_TRACE_LIMIT = 100
  let cacheWriteTimer = null
  let lastHapticCallId = ''

  $: pushSupported = isPushSupported()

  let isNearBottom = true
  let showNewMessages = false
  let renderedTimelineCount = 0

  $: timeline = $events.filter((event) =>
    event.type === 'assistant' || event.type === 'user_message' || event.type === 'tool_call',
  )
  $: latestState = [...$events].reverse().find((event) => event.type === 'state') || null

  function formatCost(stats) {
    if (!stats) return '--'
    const tokens = stats.total_tokens || 0
    const tokenStr = tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}K` : `${tokens}`
    if (stats.is_local) return `FREE | ${tokenStr} tok`
    const cost = stats.session_cost || 0
    return `$${cost.toFixed(4)} | ${tokenStr} tok`
  }

  $: costDisplay = formatCost($latestStats)

  $: {
    const callId = $pendingApproval?.call_id || ''
    if (callId && callId !== lastHapticCallId) {
      lastHapticCallId = callId
      if (navigator?.vibrate) {
        try {
          navigator.vibrate(200)
        } catch {
          // no-op
        }
      }
    }
  }

  $: activeSessions = [...sessions]
    .filter((session) => session?.status && session.status !== 'disconnected' && session.controllable)
    .sort((a, b) => parseIsoMs(b.started_at || b.last_activity) - parseIsoMs(a.started_at || a.last_activity))

  $: olderSessions = [...sessions]
    .filter((session) => !session?.controllable || session?.status === 'disconnected')
    .sort((a, b) => parseIsoMs(b.started_at || b.last_activity) - parseIsoMs(a.started_at || a.last_activity))

  $: if (streamElement && timeline.length !== renderedTimelineCount) {
    const grew = timeline.length > renderedTimelineCount
    renderedTimelineCount = timeline.length

    if (grew) {
      tick().then(() => {
        if (!streamElement) {
          return
        }

        if (isNearBottom) {
          streamElement.scrollTop = streamElement.scrollHeight
          showNewMessages = false
        } else {
          showNewMessages = true
        }
      })
    }
  }

  function buildEventId(prefix) {
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 7)}`
  }

  function websocketUrlForSession(id) {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${window.location.host}/ws/events/${encodeURIComponent(id)}`
  }

  function parseIsoMs(value) {
    if (!value || typeof value !== 'string') {
      return 0
    }
    const ms = Date.parse(value)
    return Number.isFinite(ms) ? ms : 0
  }

  function sessionTitle(session) {
    if (session?.message_count === 0) {
      return 'New session'
    }

    const title = session?.title
    if (typeof title === 'string' && title.trim()) {
      return title.trim()
    }

    return 'New session'
  }

  function cacheKey(sessionId) {
    return `${EVENT_CACHE_PREFIX}${sessionId}`
  }

  function loadNotificationTrace() {
    try {
      const raw = window.localStorage.getItem(NOTIFICATION_TRACE_KEY)
      if (!raw) {
        return []
      }
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }

  function persistNotificationTrace(entries) {
    try {
      const bounded = entries.slice(Math.max(0, entries.length - NOTIFICATION_TRACE_LIMIT))
      window.localStorage.setItem(NOTIFICATION_TRACE_KEY, JSON.stringify(bounded))
    } catch {
      // no-op
    }
  }

  function recordNotificationTrace(step, details = {}) {
    const entry = {
      step,
      ts: new Date().toISOString(),
      ...details,
    }
    persistNotificationTrace([...loadNotificationTrace(), entry])
    try {
      if (window.localStorage.getItem(NOTIFICATION_TRACE_CONSOLE_KEY) === '1') {
        console.info('[vibecheck:notification]', entry)
      }
    } catch {
      // no-op
    }
  }

  function loadCachedEvents(sessionId) {
    if (!sessionId) {
      return []
    }
    try {
      const raw = window.localStorage.getItem(cacheKey(sessionId))
      if (!raw) {
        return []
      }
      const payload = JSON.parse(raw)
      return Array.isArray(payload) ? payload : []
    } catch {
      return []
    }
  }

  function persistCachedEvents(sessionId, list) {
    if (!sessionId) {
      return
    }
    if (!Array.isArray(list)) {
      return
    }
    try {
      const sliced = list.slice(Math.max(0, list.length - EVENT_CACHE_LIMIT))
      window.localStorage.setItem(cacheKey(sessionId), JSON.stringify(sliced))
    } catch {
      // no-op
    }
  }

  function isConnectableSession(id) {
    if (!id) {
      return false
    }
    const session = sessions.find((entry) => entry?.id === id) || null
    return Boolean(session && session.controllable && session.status !== 'disconnected')
  }

  async function apiJson(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(psk ? { 'X-PSK': psk } : {}),
      },
    })

    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`)
    }

    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      return response.json()
    }

    return null
  }

  function sessionIdFromUrl(url) {
    if (!url) {
      return ''
    }
    try {
      const parsed = new URL(url, window.location.origin)
      return parsed.searchParams.get('sid') || parsed.searchParams.get('session_id') || ''
    } catch {
      return ''
    }
  }

  function callIdFromUrl(url) {
    if (!url) {
      return ''
    }
    try {
      const parsed = new URL(url, window.location.origin)
      return parsed.searchParams.get('call_id') || ''
    } catch {
      return ''
    }
  }

  function notificationSourceFromUrl(url) {
    if (!url) {
      return ''
    }
    try {
      const parsed = new URL(url, window.location.origin)
      return parsed.searchParams.get('notif_source') || ''
    } catch {
      return ''
    }
  }

  async function handleNotificationAction(action, url, callIdHint, sourceHint = '') {
    const normalized = typeof action === 'string' ? action.trim().toLowerCase() : ''
    const source =
      (typeof sourceHint === 'string' && sourceHint.trim()) || notificationSourceFromUrl(url) || 'unknown'
    recordNotificationTrace('received', {
      action: normalized || '(empty)',
      source,
      has_url: Boolean(url),
      has_call_id_hint: Boolean(callIdHint),
    })

    if (normalized !== 'approve' && normalized !== 'deny') {
      recordNotificationTrace('skip_invalid_action', { action: normalized || '(empty)', source })
      return
    }

    if (!psk || notificationActionBusy) {
      recordNotificationTrace('skip_busy_or_no_psk', {
        action: normalized,
        source,
        has_psk: Boolean(psk),
        busy: notificationActionBusy,
      })
      return
    }

    const targetSessionId = sessionIdFromUrl(url) || sessionId
    if (!targetSessionId) {
      recordNotificationTrace('skip_missing_session', { action: normalized, source })
      return
    }

    notificationActionBusy = true
    try {
      if (targetSessionId !== sessionId) {
        sessionId = targetSessionId
        storeSessionId(targetSessionId)
        connectSocket()
      }
      recordNotificationTrace('resolved_session', {
        action: normalized,
        source,
        session_id: targetSessionId,
      })

      // Prefer the call_id bound to the notification; fall back to current pending only if absent
      let callId = (typeof callIdHint === 'string' && callIdHint) || callIdFromUrl(url) || ''
      if (!callId) {
        const state = await apiJson(`/api/sessions/${encodeURIComponent(targetSessionId)}/state`)
        callId = state?.pending_approval?.call_id || ''
      }
      if (!callId) {
        recordNotificationTrace('skip_missing_call_id', {
          action: normalized,
          source,
          session_id: targetSessionId,
        })
        return
      }

      const approved = normalized === 'approve'
      recordNotificationTrace('approve_request', {
        action: normalized,
        source,
        session_id: targetSessionId,
        call_id: callId,
        approved,
      })
      await apiJson(`/api/sessions/${encodeURIComponent(targetSessionId)}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Vibecheck-Notification-Action': normalized,
          'X-Vibecheck-Notification-Source': source,
        },
        body: JSON.stringify({ call_id: callId, approved }),
      })

      handleApprovalResolved(callId, approved, `notification:${source}`)
      recordNotificationTrace('approve_ok', {
        action: normalized,
        source,
        session_id: targetSessionId,
        call_id: callId,
        approved,
      })

      if (typeof url === 'string' && url && url.includes('action=')) {
        try {
          const parsed = new URL(url, window.location.origin)
          parsed.searchParams.delete('action')
          parsed.searchParams.delete('call_id')
          parsed.searchParams.delete('notif_source')
          window.history.replaceState({}, '', parsed.pathname + parsed.search)
        } catch {
          // no-op
        }
      }
    } catch (error) {
      recordNotificationTrace('approve_error', {
        action: normalized,
        source,
        session_id: targetSessionId,
        error: error instanceof Error ? error.message : String(error),
      })
      // best-effort: action buttons should never block opening the app
    } finally {
      notificationActionBusy = false
    }
  }

  async function refreshSessions() {
    if (!psk) {
      sessions = []
      sessionError = ''
      return
    }

    sessionsLoading = true
    try {
      const payload = await apiJson('/api/sessions')
      sessions = Array.isArray(payload) ? payload : []
      sessionError = ''

      if (sessionId) {
        storeSessionId(sessionId)
      }
    } catch (error) {
      sessionError = error instanceof Error ? error.message : 'Failed to load sessions'
    } finally {
      sessionsLoading = false
    }
  }

  async function ensureNotificationSessionAttached(targetId, source) {
    const normalizedTarget = typeof targetId === 'string' ? targetId.trim() : ''
    const normalizedSource = typeof source === 'string' ? source.trim() : ''
    if (!normalizedTarget || !normalizedSource) {
      return
    }

    if (isConnectableSession(normalizedTarget)) {
      recordNotificationTrace('notification_attach_connectable', {
        session_id: normalizedTarget,
        source: normalizedSource,
      })
      return
    }

    recordNotificationTrace('notification_attach_resume_attempt', {
      session_id: normalizedTarget,
      source: normalizedSource,
    })

    try {
      await apiJson(`/api/sessions/${encodeURIComponent(normalizedTarget)}/resume`, {
        method: 'POST',
      })
      await refreshSessions()
      recordNotificationTrace('notification_attach_resume_result', {
        session_id: normalizedTarget,
        source: normalizedSource,
        connectable: isConnectableSession(normalizedTarget),
      })
    } catch (error) {
      recordNotificationTrace('notification_attach_resume_error', {
        session_id: normalizedTarget,
        source: normalizedSource,
        error: error instanceof Error ? error.message : String(error),
      })
    }
  }

  function startRefreshTimer() {
    if (refreshTimer) {
      return
    }
    refreshTimer = setInterval(() => {
      refreshSessions()
    }, 10_000)
  }

  function stopRefreshTimer() {
    if (!refreshTimer) {
      return
    }
    clearInterval(refreshTimer)
    refreshTimer = null
  }

  function connectSocket() {
    if (!psk || !sessionId) {
      return
    }
    if (!isConnectableSession(sessionId)) {
      return
    }

    const shouldResetTimeline = activeSessionId !== sessionId
    disconnectSocket()
    if (shouldResetTimeline) {
      resetEvents()
      mergeEvents(loadCachedEvents(sessionId))
      showNewMessages = false
      renderedTimelineCount = 0
    }
    activeSessionId = sessionId
    socketClient = createWebSocket(websocketUrlForSession(sessionId), psk)
    socketClient.connect()
  }

  function disconnectSocket() {
    if (!socketClient) {
      return
    }

    socketClient.disconnect()
    socketClient = null
  }

  function savePsk() {
    const trimmed = pskDraft.trim()
    if (!trimmed) {
      return
    }

    storePsk(trimmed)
    psk = trimmed
    pskDraft = trimmed
    pskSettingsDraft = trimmed
    refreshSessions().then(() => {
      startRefreshTimer()
      if (sessionId && isConnectableSession(sessionId)) {
        connectSocket()
      }
    })
  }

  function clearPsk() {
    disconnectSocket()
    clearStoredPsk()
    psk = ''
    pskDraft = ''
    pskSettingsDraft = ''
    sessionId = ''
    activeSessionId = ''
    sessions = []
    sessionError = ''
    stopRefreshTimer()
    clearStoredSessionId()
    resetEvents()
    showNewMessages = false
    renderedTimelineCount = 0
  }

  function handlePskDraftChange(event) {
    pskSettingsDraft = event.detail?.value || event.currentTarget?.value || ''
  }

  function savePskFromSettings() {
    const trimmed = pskSettingsDraft.trim()
    if (!trimmed) {
      return
    }
    if (trimmed === psk) {
      pskSettingsDraft = psk
      return
    }

    disconnectSocket()
    storePsk(trimmed)
    psk = trimmed
    pskDraft = trimmed
    pskSettingsDraft = trimmed

    refreshSessions().then(() => {
      startRefreshTimer()
      if (sessionId && isConnectableSession(sessionId)) {
        connectSocket()
      }
    })
  }

  function handleSessionInput(event) {
    sessionId = event.currentTarget.value.trim()
    if (sessionId) {
      storeSessionId(sessionId)
    }
  }

  function switchSession(targetId) {
    const normalized = typeof targetId === 'string' ? targetId.trim() : ''
    if (!normalized) {
      return
    }
    sessionId = normalized
    storeSessionId(normalized)
    sessionPickerOpen = false
    connectSocket()
  }

  async function resumeSession(targetId) {
    const normalized = typeof targetId === 'string' ? targetId.trim() : ''
    if (!normalized || !psk || resumeBusy) {
      return
    }

    resumeBusy = normalized
    sessionError = ''

    try {
      const payload = await apiJson(`/api/sessions/${encodeURIComponent(normalized)}/resume`, {
        method: 'POST',
      })
      sessionId = normalized
      storeSessionId(normalized)
      await refreshSessions()
      connectSocket()
      if (payload?.backlog) {
        mergeEvents(payload.backlog)
      }
    } catch (error) {
      sessionError = error instanceof Error ? error.message : 'Failed to resume session'
    } finally {
      resumeBusy = ''
    }
  }

  function handleVoiceLanguageChange(event) {
    voiceLanguage = event.detail?.value || event.currentTarget?.value
    storeVoiceLanguage(voiceLanguage)
  }

  function confirmAndClearPsk() {
    const shouldForget =
      typeof window === 'undefined' || typeof window.confirm !== 'function'
        ? true
        : window.confirm('Forget the saved PSK and lock the app?')
    if (!shouldForget) {
      return
    }
    clearPsk()
  }

  // ---------------------------------------------------------------------------
  // Talker mode (VAD-powered voice loop)
  // ---------------------------------------------------------------------------

  async function toggleTalker() {
    if (talkerActive) {
      // Exiting talker mode
      talkerActive = false
      talkerState = 'idle'
      if (talkerSttAbort) {
        talkerSttAbort.abort()
        talkerSttAbort = null
      }
      if (talkerTtsAbort) {
        talkerTtsAbort.abort()
        talkerTtsAbort = null
      }
      stopTalkerAudio()
      await destroyVAD()
    } else {
      // Entering talker mode
      talkerActive = true
      talkerState = 'listening'
      try {
        await startVAD({
          onSpeechEnd: handleVADSpeechEnd,
          onSpeechStart: handleVADSpeechStart,
        })
      } catch (error) {
        console.warn('[talker] VAD init failed:', error)
        talkerActive = false
        talkerState = 'idle'
      }
    }
  }

  function handleVADSpeechStart() {
    if (talkerActive && talkerState === 'listening') {
      talkerState = 'listening'
    }
  }

  async function handleVADSpeechEnd(wavBlob) {
    if (!talkerActive || !wavBlob || wavBlob.size === 0) {
      return
    }

    talkerState = 'transcribing'
    await pauseVAD()

    // Abort any previous in-flight STT/submit pipeline
    if (talkerSttAbort) {
      talkerSttAbort.abort()
    }
    const abort = new AbortController()
    talkerSttAbort = abort

    try {
      const response = await fetch(`/api/voice/transcribe?language=${encodeURIComponent(voiceLanguage)}`, {
        method: 'POST',
        headers: {
          ...(psk ? { 'X-PSK': psk } : {}),
          'Content-Type': 'audio/wav',
        },
        body: wavBlob,
        signal: abort.signal,
      })

      if (!talkerActive) return  // exited during STT fetch

      if (!response.ok) {
        console.warn('[talker] STT failed:', response.status)
        talkerState = 'listening'
        await resumeVAD()
        return
      }

      const payload = await response.json()
      if (!talkerActive) return  // exited during json parse

      const text = typeof payload?.text === 'string' ? payload.text.trim() : ''
      if (!text) {
        talkerState = 'listening'
        await resumeVAD()
        return
      }

      // Snapshot assistant count before submission so we only speak new responses
      talkerSubmitAssistantCount = timeline.filter((e) => e.type === 'assistant').length

      // Submit the transcribed text as a message
      talkerState = 'running'
      const endpoint = $pendingInput ? 'input' : 'message'
      const body = $pendingInput
        ? { request_id: $pendingInput.request_id, response: text }
        : { content: text }

      const submitResponse = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(psk ? { 'X-PSK': psk } : {}),
        },
        body: JSON.stringify(body),
        signal: abort.signal,
      })

      if (!talkerActive) return  // exited during submit

      if (!submitResponse.ok) {
        console.warn('[talker] Submit failed:', submitResponse.status)
        talkerState = 'listening'
        await resumeVAD()
        return
      }

      if (typeof handleSubmitted === 'function') {
        handleSubmitted({ endpoint, payload: body })
      }

      // Stay in 'running' state — the reactive block below will detect
      // when the agent finishes and trigger TTS
    } catch (error) {
      if (error?.name === 'AbortError') return  // intentional abort on toggle-off
      console.warn('[talker] Speech processing error:', error)
      if (talkerActive) {
        talkerState = 'listening'
        await resumeVAD()
      }
    } finally {
      if (talkerSttAbort === abort) {
        talkerSttAbort = null
      }
    }
  }

  function stopTalkerAudio() {
    if (talkerAudio) {
      try {
        talkerAudio.pause()
        talkerAudio.src = ''
      } catch {
        // no-op
      }
      talkerAudio = null
    }
  }

  async function talkerSpeak(text) {
    if (!talkerActive || !text) {
      if (talkerActive) {
        talkerState = 'listening'
        await resumeVAD()
      }
      return
    }

    talkerState = 'speaking'
    stopTalkerAudio()

    // Abort any previous in-flight TTS fetch
    if (talkerTtsAbort) {
      talkerTtsAbort.abort()
    }
    const abort = new AbortController()
    talkerTtsAbort = abort

    try {
      const response = await fetch('/api/voice/synthesize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(psk ? { 'X-PSK': psk } : {}),
        },
        body: JSON.stringify({ text }),
        signal: abort.signal,
      })

      if (!talkerActive) return  // exited during fetch

      if (!response.ok) {
        console.warn('[talker] TTS failed:', response.status)
        talkerState = 'listening'
        await resumeVAD()
        return
      }

      const blob = await response.blob()
      if (!talkerActive) return  // exited during blob read

      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      talkerAudio = audio

      audio.onended = async () => {
        URL.revokeObjectURL(url)
        talkerAudio = null
        if (talkerActive) {
          talkerState = 'listening'
          await resumeVAD()
        }
      }

      audio.onerror = async () => {
        URL.revokeObjectURL(url)
        talkerAudio = null
        if (talkerActive) {
          talkerState = 'listening'
          await resumeVAD()
        }
      }

      if (!talkerActive) {  // exited before play
        URL.revokeObjectURL(url)
        talkerAudio = null
        return
      }

      await audio.play()
    } catch (error) {
      if (error?.name === 'AbortError') return  // intentional abort on toggle-off
      // Clean up URL + audio ref on any failure (e.g. autoplay policy rejection)
      if (talkerAudio) {
        const staleUrl = talkerAudio.src
        talkerAudio.pause()
        talkerAudio = null
        if (staleUrl && staleUrl.startsWith('blob:')) {
          URL.revokeObjectURL(staleUrl)
        }
      }
      console.warn('[talker] TTS error:', error)
      if (talkerActive) {
        talkerState = 'listening'
        await resumeVAD()
      }
    } finally {
      if (talkerTtsAbort === abort) {
        talkerTtsAbort = null
      }
    }
  }

  // Watch agent state for completion while talker mode is running.
  // Only trigger TTS when state transitions to 'idle' (not waiting_approval
  // or waiting_input, which don't mean the agent finished a response).
  // Only speak assistant events that arrived *after* the submission.
  let talkerPrevAgentState = ''
  $: {
    const currentAgentState = latestState?.state || 'unknown'
    if (talkerActive && talkerState === 'running') {
      const wasActive = talkerPrevAgentState === 'running' || talkerPrevAgentState === 'tool_running'
      const isNowIdle = currentAgentState === 'idle'
      if (wasActive && isNowIdle) {
        const assistantEvents = timeline.filter((e) => e.type === 'assistant')
        // Only consider assistant events that arrived after we submitted
        const newEvents = assistantEvents.slice(talkerSubmitAssistantCount)
        if (newEvents.length > 0) {
          const latest = newEvents[newEvents.length - 1]
          const content = typeof latest?.content === 'string' ? latest.content.trim() : ''
          if (content) {
            talkerSpeak(content)
          } else {
            talkerState = 'listening'
            resumeVAD()
          }
        } else {
          talkerState = 'listening'
          resumeVAD()
        }
      }
    }
    talkerPrevAgentState = currentAgentState
  }

  function handleTalkerSubmitted(info) {
    handleSubmitted(info)
    if (talkerActive) {
      talkerState = 'running'
    }
  }

  function toggleSessionPicker() {
    sessionPickerOpen = !sessionPickerOpen
  }

  function toggleSettings() {
    if (!settingsOpen) {
      pskSettingsDraft = psk
    }
    settingsOpen = !settingsOpen
  }

  $: activeSessionTitle = (() => {
    const match = sessions.find((s) => s?.id === sessionId)
    if (!match) return ''
    return sessionTitle(match)
  })()

  async function toggleNotifications() {
    if (!pushSupported || notificationsBusy) {
      return
    }

    notificationsBusy = true
    notificationsError = ''

    try {
      if (notificationsEnabled) {
        await unsubscribeFromPush(psk)
        notificationsEnabled = false
      } else {
        await subscribeToPush(psk)
        notificationsEnabled = true
      }
      storeNotificationsEnabled(notificationsEnabled)
    } catch (error) {
      notificationsError = error instanceof Error ? error.message : 'Push request failed'
    } finally {
      notificationsBusy = false
    }
  }

  function onStreamScroll() {
    if (!streamElement) {
      return
    }

    const distanceFromBottom =
      streamElement.scrollHeight - (streamElement.scrollTop + streamElement.clientHeight)

    isNearBottom = distanceFromBottom <= 100
    if (isNearBottom) {
      showNewMessages = false
    }
  }

  function jumpToLatest() {
    if (!streamElement) {
      return
    }

    streamElement.scrollTop = streamElement.scrollHeight
    isNearBottom = true
    showNewMessages = false
  }

  function handleApprovalResolved(callId, approved, source = 'pwa_ui') {
    appendEvent({
      type: 'approval_resolution',
      id: buildEventId('approval-resolution-local'),
      timestamp: Date.now() / 1000,
      call_id: callId,
      approved,
      edited_args: null,
      source,
    })
  }

  function handleSubmitted({ endpoint, payload }) {
    if (endpoint === 'input') {
      appendEvent({
        type: 'input_resolution',
        id: buildEventId('input-resolution-local'),
        timestamp: Date.now() / 1000,
        request_id: payload.request_id,
        response: payload.response,
      })
    }
  }

  const unsubscribeEvents = events.subscribe((list) => {
    if (!activeSessionId) {
      return
    }

    if (cacheWriteTimer) {
      clearTimeout(cacheWriteTimer)
    }

    cacheWriteTimer = setTimeout(() => {
      persistCachedEvents(activeSessionId, list)
      cacheWriteTimer = null
    }, 250)
  })

  onMount(() => {
    if (window) {
      window.__vibecheckNotificationTrace = {
        dump: () => loadNotificationTrace(),
        clear: () => persistNotificationTrace([]),
        enableConsole: () => window.localStorage.setItem(NOTIFICATION_TRACE_CONSOLE_KEY, '1'),
        disableConsole: () => window.localStorage.removeItem(NOTIFICATION_TRACE_CONSOLE_KEY),
      }
    }

    const messageHandler = (event) => {
      const payload = event?.data
      if (!payload || payload.type !== 'notification_action') {
        return
      }
      handleNotificationAction(
        payload.action,
        payload.url,
        payload.call_id,
        typeof payload.source === 'string' ? payload.source : 'window_message',
      )
    }

    const serviceWorkerTarget = navigator?.serviceWorker
    if (serviceWorkerTarget?.addEventListener) {
      serviceWorkerTarget.addEventListener('message', messageHandler)
    }
    window.addEventListener('message', messageHandler)

    if (psk) {
      ;(async () => {
        try {
          const notificationSource = initialNotificationSource || notificationSourceFromUrl(window.location.href)
          const targetSessionId = sessionIdFromUrl(window.location.href) || sessionId
          if (targetSessionId && targetSessionId !== sessionId) {
            sessionId = targetSessionId
            storeSessionId(targetSessionId)
          }

          await handleNotificationAction(
            initialAction,
            window.location.href,
            initialCallId,
            initialNotificationSource || 'url_query',
          )
          await refreshSessions()
          if (notificationSource && targetSessionId) {
            await ensureNotificationSessionAttached(targetSessionId, notificationSource)
          }
          startRefreshTimer()

          if (sessionId && isConnectableSession(sessionId)) {
            connectSocket()
          }
        } catch {
          // no-op
        }
      })()
    }

    return () => {
      if (serviceWorkerTarget?.removeEventListener) {
        serviceWorkerTarget.removeEventListener('message', messageHandler)
      }
      window.removeEventListener('message', messageHandler)
      if (window?.__vibecheckNotificationTrace) {
        delete window.__vibecheckNotificationTrace
      }
    }
  })

  onDestroy(() => {
    stopRefreshTimer()
    disconnectSocket()
    stopTalkerAudio()
    destroyVAD()
    if (cacheWriteTimer) {
      clearTimeout(cacheWriteTimer)
      cacheWriteTimer = null
    }
    unsubscribeEvents()
  })
</script>

{#if !psk}
  <main class="psk-gate">
    <section class="gate-card">
      <h1>Enter PSK</h1>
      <p>Use the shared key from your deploy environment to unlock mobile controls.</p>
      <input type="password" bind:value={pskDraft} placeholder="Pre-shared key" />
      <button type="button" on:click={savePsk}>Save Key</button>
    </section>
  </main>
{:else}
  <div class="shell">
    <HeaderBar
      connectionStatus={$connection.status}
      reconnectAttempts={$connection.reconnectAttempts}
      {activeSessionTitle}
      pickerOpen={sessionPickerOpen}
      onTogglePicker={toggleSessionPicker}
    />

    <SessionPicker
      {sessions}
      {activeSessions}
      {olderSessions}
      {sessionId}
      {sessionsLoading}
      {sessionError}
      {resumeBusy}
      open={sessionPickerOpen}
      onSwitchSession={switchSession}
      onResumeSession={resumeSession}
      onRefresh={refreshSessions}
      onSessionInput={handleSessionInput}
      onConnect={connectSocket}
      onDisconnect={disconnectSocket}
      {isConnectableSession}
    />

    <section class="timeline-wrap">
      <div class="timeline" bind:this={streamElement} on:scroll={onStreamScroll} data-testid="chat-scroll">
        {#if timeline.length === 0}
          <p class="empty">
            {activeSessionId
              ? 'No events yet. Trigger a turn in your agent.'
              : 'Select an active session or resume an older one.'}
          </p>
        {:else}
          {#each timeline as event, index (event.id || `${event.type}-${index}`)}
            {#if event.type === 'tool_call'}
              <ToolCallCard
                toolCall={event}
                result={$toolResultsByCall.get(event.call_id) || null}
                sessionId={activeSessionId}
                {psk}
              />
            {:else}
              <ChatMessage {event} {psk} targetLanguage={voiceLanguage} />
            {/if}
          {/each}
        {/if}
      </div>

      {#if showNewMessages}
        <button type="button" class="jump" on:click={jumpToLatest}>New messages ↓</button>
      {/if}
    </section>

    <footer class="composer">
      <ApprovalPanel
        pendingApproval={$pendingApproval}
        {sessionId}
        {psk}
        onResolved={handleApprovalResolved}
      />
      <InputBar
        {sessionId}
        {psk}
        {voiceLanguage}
        {talkerActive}
        {talkerState}
        pendingInput={$pendingInput}
        connectionStatus={$connection.status}
        onSubmitted={talkerActive ? handleTalkerSubmitted : handleSubmitted}
        onTalkerToggle={toggleTalker}
      />
    </footer>

    <div class="settings-drawer" class:open={settingsOpen}>
      <SettingsPanel
        {voiceLanguage}
        {notificationsEnabled}
        {pushSupported}
        {notificationsBusy}
        {notificationsError}
        pskDraft={pskSettingsDraft}
        on:voiceLanguageChange={handleVoiceLanguageChange}
        on:toggleNotifications={toggleNotifications}
        on:pskDraftChange={handlePskDraftChange}
        on:saveKey={savePskFromSettings}
        on:forgetKey={confirmAndClearPsk}
      />
    </div>

    <StatusLine
      agentState={latestState?.state || 'unknown'}
      {sessionError}
      onSettingsToggle={toggleSettings}
      {settingsOpen}
      {costDisplay}
    />
  </div>
{/if}

<style>
  :global(html) {
    --bg: #1a1a1a;
    --fg: #e0e0e0;
    --card-border: rgba(255,255,255,0.1);
    --card-border-strong: rgba(255,255,255,0.15);
    --card-bg: #2a2a2a;
    --card-bg-alt: #252525;
    --text-muted: #888;
    --label: #888;
    --input-border: rgba(255,255,255,0.12);
    --input-bg: #1a1a1a;
    --input-fg: #e0e0e0;
    --primary-border: #EF7D31;
    --primary-bg: #3a2010;
    --primary-fg: #ffe1c6;
    --secondary-border: rgba(255,255,255,0.15);
    --secondary-bg: #333;
    --secondary-fg: #e0e0e0;
    --danger-border: #8b4a4a;
    --danger-bg: #351819;
    --danger-fg: #ffd1d1;
    --meta: #888;
    --error: #ffbbbb;
    --empty: #888;
    --session-bg: #222;
    --session-border: rgba(255,255,255,0.1);
    --session-selected: #EF7D31;
    --session-status-waiting: #EF7D31;
    --session-status-running: #888;
    --session-status-idle: #555;
  }

  :global(html), :global(body) {
    height: 100%;
    overflow: hidden;
  }

  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--fg);
    font-family: 'JetBrains Mono', monospace;
    overscroll-behavior: none;
  }

  .psk-gate {
    min-height: 100dvh;
    display: grid;
    place-items: center;
    padding: 1rem;
  }

  .gate-card {
    width: min(100%, 26rem);
    border: 1px solid var(--card-border-strong);
    border-radius: 2px;
    background: var(--card-bg-alt);
    padding: 1rem;
    display: grid;
    gap: 0.8rem;
  }

  .gate-card h1 {
    margin: 0;
    font-size: 1.2rem;
  }

  .gate-card p {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.4;
  }

  input,
  button {
    font: inherit;
  }

  input {
    min-height: 40px;
    border-radius: 2px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    color: var(--input-fg);
    padding: 0 0.7rem;
  }

  button {
    min-height: 40px;
    border-radius: 2px;
    border: 1px solid var(--primary-border);
    background: var(--primary-bg);
    color: var(--primary-fg);
    font-weight: 700;
  }

  button:disabled {
    opacity: 0.58;
  }

  .shell {
    position: fixed;
    inset: 0;
    display: flex;
    flex-direction: column;
    margin: 0 auto;
    width: min(100%, 600px);
    padding-top: env(safe-area-inset-top);
    padding-bottom: env(safe-area-inset-bottom);
    padding-left: env(safe-area-inset-left);
    padding-right: env(safe-area-inset-right);
    overflow: hidden;
  }

  .timeline-wrap {
    flex: 1;
    min-height: 0;
    position: relative;
  }

  .timeline {
    height: 100%;
    overflow-y: auto;
    overflow-x: auto;
    padding: 0.75rem;
    display: grid;
    gap: 0.55rem;
    align-content: start;
  }

  .empty {
    margin: 0;
    color: var(--empty);
    font-size: 0.88rem;
    line-height: 1.4;
  }

  .jump {
    position: absolute;
    right: 0.75rem;
    bottom: 0.75rem;
    min-height: 36px;
    min-width: 148px;
    border-radius: 2px;
    border-color: var(--primary-border);
    background: var(--primary-bg);
    color: var(--primary-fg);
    box-shadow: 0 10px 25px rgb(0 0 0 / 0.35);
  }

  .composer {
    flex-shrink: 0;
    padding: 0.4rem 0.5rem;
    display: grid;
    gap: 0.4rem;
    border-top: 1px solid var(--card-border);
  }

  .settings-drawer {
    overflow: hidden;
    max-height: 0;
    transition: max-height 0.3s ease;
    background: var(--card-bg);
    border-top: 1px solid var(--card-border);
  }

  .settings-drawer.open {
    max-height: 50vh;
    overflow-y: auto;
  }
</style>
