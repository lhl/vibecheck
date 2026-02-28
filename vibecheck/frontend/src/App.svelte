<script>
  import { onDestroy, onMount, tick } from 'svelte'
  import ApprovalPanel from './components/ApprovalPanel.svelte'
  import ChatMessage from './components/ChatMessage.svelte'
  import ConnectionStatus from './components/ConnectionStatus.svelte'
  import InputBar from './components/InputBar.svelte'
  import SettingsPanel from './components/SettingsPanel.svelte'
  import ToolCallCard from './components/ToolCallCard.svelte'
  import {
    clearStoredPsk,
    clearStoredSessionId,
    loadInitialPsk,
    loadStoredSessionId,
    storePsk,
    storeSessionId,
  } from './lib/auth'
  import { subscribeToPush, unsubscribeFromPush, isPushSupported } from './lib/push'
  import {
    loadAutoTranslateEnabled,
    loadNotificationsEnabled,
    loadThemePreference,
    loadVoiceLanguage,
    storeAutoTranslateEnabled,
    storeNotificationsEnabled,
    storeThemePreference,
    storeVoiceLanguage,
  } from './lib/settings'
  import { createWebSocket } from './lib/ws'
  import { connection } from './stores/connection'
  import {
    appendEvent,
    events,
    mergeEvents,
    pendingApproval,
    pendingInput,
    resetEvents,
    toolResultsByCall,
  } from './stores/events'

  const query = new URLSearchParams(window.location.search)

  const initialSessionId = query.get('sid') || query.get('session_id') || loadStoredSessionId() || ''
  const initialAction = query.get('action') || ''
  const initialCallId = query.get('call_id') || ''

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
  let autoTranslateEnabled = loadAutoTranslateEnabled()
  let notificationsError = ''
  let notificationsBusy = false
  let notificationActionBusy = false
  let sessionsLoading = false
  let resumeBusy = ''
  let theme = loadThemePreference()

  const EVENT_CACHE_PREFIX = 'vibecheck_events_'
  const EVENT_CACHE_LIMIT = 50
  let cacheWriteTimer = null
  let lastHapticCallId = ''

  $: pushSupported = isPushSupported()

  $: {
    const root = document?.documentElement
    if (root) {
      if (theme === 'auto') {
        root.removeAttribute('data-theme')
      } else {
        root.setAttribute('data-theme', theme)
      }
    }
  }

  let isNearBottom = true
  let showNewMessages = false
  let renderedTimelineCount = 0

  $: timeline = $events.filter((event) =>
    event.type === 'assistant' || event.type === 'user_message' || event.type === 'tool_call',
  )
  $: latestState = [...$events].reverse().find((event) => event.type === 'state') || null

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

  function formatRelative(value) {
    const ms = parseIsoMs(value)
    if (!ms) {
      return ''
    }

    const deltaSeconds = Math.max(0, Math.floor((Date.now() - ms) / 1000))
    if (deltaSeconds < 60) {
      return `${deltaSeconds}s ago`
    }
    const minutes = Math.floor(deltaSeconds / 60)
    if (minutes < 60) {
      return `${minutes}m ago`
    }
    const hours = Math.floor(minutes / 60)
    if (hours < 24) {
      return `${hours}h ago`
    }
    const days = Math.floor(hours / 24)
    return `${days}d ago`
  }

  function statusBadge(session) {
    const status = session?.status || ''
    if (status === 'waiting_approval' || status === 'waiting_input') {
      return 'waiting'
    }
    if (status === 'running') {
      return 'running'
    }
    if (status === 'idle') {
      return 'idle'
    }
    return status || 'unknown'
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

  function sessionIdPreview(id) {
    if (typeof id !== 'string') {
      return ''
    }
    const trimmed = id.trim()
    if (trimmed.length <= 10) {
      return trimmed
    }
    return `${trimmed.slice(0, 8)}…`
  }

  function cacheKey(sessionId) {
    return `${EVENT_CACHE_PREFIX}${sessionId}`
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

  async function handleNotificationAction(action, url, callIdHint) {
    const normalized = typeof action === 'string' ? action.trim().toLowerCase() : ''
    if (normalized !== 'approve' && normalized !== 'deny') {
      return
    }

    if (!psk || notificationActionBusy) {
      return
    }

    const targetSessionId = sessionIdFromUrl(url) || sessionId
    if (!targetSessionId) {
      return
    }

    notificationActionBusy = true
    try {
      if (targetSessionId !== sessionId) {
        sessionId = targetSessionId
        storeSessionId(targetSessionId)
        connectSocket()
      }

      // Prefer the call_id bound to the notification; fall back to current pending only if absent
      let callId = (typeof callIdHint === 'string' && callIdHint) || callIdFromUrl(url) || ''
      if (!callId) {
        const state = await apiJson(`/api/sessions/${encodeURIComponent(targetSessionId)}/state`)
        callId = state?.pending_approval?.call_id || ''
      }
      if (!callId) {
        return
      }

      const approved = normalized === 'approve'
      await apiJson(`/api/sessions/${encodeURIComponent(targetSessionId)}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ call_id: callId, approved }),
      })

      handleApprovalResolved(callId, approved)

      if (typeof url === 'string' && url && url.includes('action=')) {
        try {
          const parsed = new URL(url, window.location.origin)
          parsed.searchParams.delete('action')
          parsed.searchParams.delete('call_id')
          window.history.replaceState({}, '', parsed.pathname + parsed.search)
        } catch {
          // no-op
        }
      }
    } catch {
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

      if (!sessionId && sessions.length > 0) {
        const active = [...sessions]
          .filter((session) => session?.status && session.status !== 'disconnected' && session.controllable)
          .sort((a, b) => parseIsoMs(b.started_at || b.last_activity) - parseIsoMs(a.started_at || a.last_activity))
        if (active.length > 0) {
          sessionId = active[0].id
        }
      }

      if (sessionId) {
        storeSessionId(sessionId)
      }
    } catch (error) {
      sessionError = error instanceof Error ? error.message : 'Failed to load sessions'
    } finally {
      sessionsLoading = false
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

  function toggleAutoTranslate() {
    autoTranslateEnabled = !autoTranslateEnabled
    storeAutoTranslateEnabled(autoTranslateEnabled)
  }

  function cycleTheme() {
    if (theme === 'auto') {
      theme = 'dark'
    } else if (theme === 'dark') {
      theme = 'light'
    } else {
      theme = 'auto'
    }
    storeThemePreference(theme)
  }

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

  function handleApprovalResolved(callId, approved) {
    appendEvent({
      type: 'approval_resolution',
      id: buildEventId('approval-resolution-local'),
      timestamp: Date.now() / 1000,
      call_id: callId,
      approved,
      edited_args: null,
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
    const messageHandler = (event) => {
      const payload = event?.data
      if (!payload || payload.type !== 'notification_action') {
        return
      }
      handleNotificationAction(payload.action, payload.url, payload.call_id)
    }

    const serviceWorkerTarget = navigator?.serviceWorker
    if (serviceWorkerTarget?.addEventListener) {
      serviceWorkerTarget.addEventListener('message', messageHandler)
    }
    window.addEventListener('message', messageHandler)

    if (psk) {
      ;(async () => {
        try {
          await handleNotificationAction(initialAction, window.location.href, initialCallId)
          await refreshSessions()
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
    }
  })

  onDestroy(() => {
    stopRefreshTimer()
    disconnectSocket()
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
    <header class="app-header">
      <h1>vibecheck</h1>
      <ConnectionStatus status={$connection.status} reconnectAttempts={$connection.reconnectAttempts} />
    </header>

    <section class="session-controls">
      <div class="session-header">
        <h2>Sessions</h2>
        <button type="button" class="secondary" on:click={refreshSessions} disabled={sessionsLoading}>
          {sessionsLoading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {#if activeSessions.length > 0}
        <p class="section-label">Active</p>
        <ul class="session-list" aria-label="Active sessions">
          {#each activeSessions as session}
            <li>
              <button
                type="button"
                class="session-item"
                class:selected={session.id === sessionId}
                on:click={() => switchSession(session.id)}
              >
                <div class="row">
                  <span class="session-title">{sessionTitle(session)}</span>
                  <span class="status {statusBadge(session)}">{statusBadge(session)}</span>
                </div>
                <div class="row meta-line">
                  <span class="meta">started {formatRelative(session.started_at || session.last_activity)}</span>
                  {#if session.last_activity}
                    <span class="meta">active {formatRelative(session.last_activity)}</span>
                  {/if}
                  <span class="meta">{session.message_count || 0} msgs</span>
                  <span class="meta mono" title={session.id}>{sessionIdPreview(session.id)}</span>
                </div>
              </button>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="meta">No active sessions detected.</p>
      {/if}

      <details class="older-sessions">
        <summary>Browse older sessions</summary>
        {#if olderSessions.length === 0}
          <p class="meta">No older sessions found.</p>
        {:else}
          <ul class="session-list" aria-label="Older sessions">
            {#each olderSessions as session}
              <li class="session-old">
                <div class="session-old-meta">
                  <p class="session-old-title">{sessionTitle(session)}</p>
                  <p class="meta">
                    started {formatRelative(session.started_at || session.last_activity)}
                    {#if session.last_activity}
                      · active {formatRelative(session.last_activity)}
                    {/if}
                    · {session.message_count || 0} msgs
                  </p>
                  <p class="meta mono" title={session.id}>{sessionIdPreview(session.id)}</p>
                </div>
                <button
                  type="button"
                  class="secondary"
                  on:click={() => resumeSession(session.id)}
                  disabled={resumeBusy === session.id}
                >
                  {resumeBusy === session.id ? 'Resuming…' : 'Resume'}
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </details>

      <details class="advanced">
        <summary>Advanced</summary>
        <label for="session-id">Session ID</label>
        <input
          id="session-id"
          value={sessionId}
          placeholder="Session ID"
          on:change={handleSessionInput}
        />

        <div class="control-actions">
          <button
            type="button"
            on:click={connectSocket}
            disabled={!sessionId || !isConnectableSession(sessionId)}
          >
            Connect
          </button>
          <button type="button" class="secondary" on:click={disconnectSocket}>Disconnect</button>
        </div>
      </details>

      <SettingsPanel
        {voiceLanguage}
        {autoTranslateEnabled}
        {notificationsEnabled}
        {pushSupported}
        {notificationsBusy}
        {notificationsError}
        {theme}
        on:voiceLanguageChange={handleVoiceLanguageChange}
        on:toggleTranslate={toggleAutoTranslate}
        on:toggleNotifications={toggleNotifications}
        on:cycleTheme={cycleTheme}
        on:forgetKey={clearPsk}
      />

      <p class="meta">state: {latestState?.state || 'unknown'}</p>
      {#if sessionError}
        <p class="error">{sessionError}</p>
      {/if}
    </section>

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
              <ChatMessage {event} {psk} autoTranslate={autoTranslateEnabled} />
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
        pendingInput={$pendingInput}
        connectionStatus={$connection.status}
        onSubmitted={handleSubmitted}
      />
    </footer>
  </div>
{/if}

<style>
  :global(html) {
    --bg:
      radial-gradient(circle at 15% 10%, #20304f, transparent 35%),
      radial-gradient(circle at 90% 5%, #4f2d19, transparent 28%),
      #0d111b;
    --fg: #eef3ff;
    --card-border: #334766;
    --card-border-strong: #43557a;
    --card-bg: linear-gradient(165deg, #1c2438, #111a2a);
    --card-bg-alt: linear-gradient(160deg, #1b2438, #12192a);
    --text-muted: #bbc7e2;
    --label: #9eb0d5;
    --input-border: #405475;
    --input-bg: #0f1727;
    --input-fg: #dce8ff;
    --primary-border: #8a6346;
    --primary-bg: #362416;
    --primary-fg: #ffe1c6;
    --secondary-border: #48628c;
    --secondary-bg: #1a2740;
    --secondary-fg: #d3e5ff;
    --danger-border: #8b4a4a;
    --danger-bg: #351819;
    --danger-fg: #ffd1d1;
    --meta: #9eb0d5;
    --error: #ffbbbb;
    --empty: #afbdd9;
    --session-bg: rgb(8 12 22 / 0.25);
    --session-border: #2d3852;
    --session-selected: #3b6ea7;
    --session-status-waiting: #cb6c29;
    --session-status-running: #4f6a9d;
    --session-status-idle: #48628c;
  }

  @media (prefers-color-scheme: light) {
    :global(html:not([data-theme])) {
      --bg: #f6f8ff;
      --fg: #111827;
      --card-border: #c7d3eb;
      --card-border-strong: #c7d3eb;
      --card-bg: #ffffff;
      --card-bg-alt: #ffffff;
      --text-muted: #475569;
      --label: #475569;
      --input-border: #c7d3eb;
      --input-bg: #ffffff;
      --input-fg: #111827;
      --primary-border: #2563eb;
      --primary-bg: #2563eb;
      --primary-fg: #ffffff;
      --secondary-border: #cbd5e1;
      --secondary-bg: #e2e8f0;
      --secondary-fg: #0f172a;
      --danger-border: #fecaca;
      --danger-bg: #fee2e2;
      --danger-fg: #7f1d1d;
      --meta: #475569;
      --error: #b91c1c;
      --empty: #475569;
      --session-bg: rgb(15 23 42 / 0.04);
      --session-border: #cbd5e1;
      --session-selected: #2563eb;
      --session-status-waiting: #b45309;
      --session-status-running: #2563eb;
      --session-status-idle: #64748b;
    }
  }

  :global(html[data-theme='light']) {
    --bg: #f6f8ff;
    --fg: #111827;
    --card-border: #c7d3eb;
    --card-border-strong: #c7d3eb;
    --card-bg: #ffffff;
    --card-bg-alt: #ffffff;
    --text-muted: #475569;
    --label: #475569;
    --input-border: #c7d3eb;
    --input-bg: #ffffff;
    --input-fg: #111827;
    --primary-border: #2563eb;
    --primary-bg: #2563eb;
    --primary-fg: #ffffff;
    --secondary-border: #cbd5e1;
    --secondary-bg: #e2e8f0;
    --secondary-fg: #0f172a;
    --danger-border: #fecaca;
    --danger-bg: #fee2e2;
    --danger-fg: #7f1d1d;
    --meta: #475569;
    --error: #b91c1c;
    --empty: #475569;
    --session-bg: rgb(15 23 42 / 0.04);
    --session-border: #cbd5e1;
    --session-selected: #2563eb;
    --session-status-waiting: #b45309;
    --session-status-running: #2563eb;
    --session-status-idle: #64748b;
  }

  :global(body) {
    margin: 0;
    min-height: 100%;
    background: var(--bg);
    color: var(--fg);
    font-family: 'Space Grotesk', 'Avenir Next', 'Segoe UI', sans-serif;
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
    border-radius: 16px;
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

  .shell {
    display: grid;
    grid-template-rows: auto auto 1fr auto;
    gap: 0.75rem;
    min-height: 100dvh;
    margin: 0 auto;
    width: min(100%, 460px);
    padding:
      calc(0.8rem + env(safe-area-inset-top))
      calc(0.8rem + env(safe-area-inset-right))
      calc(0.8rem + env(safe-area-inset-bottom))
      calc(0.8rem + env(safe-area-inset-left));
  }

  .app-header,
  .session-controls,
  .timeline,
  .composer {
    border: 1px solid var(--card-border);
    border-radius: 16px;
    background: var(--card-bg);
  }

  .app-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
  }

  .app-header h1 {
    margin: 0;
    font-size: 1.08rem;
    letter-spacing: 0.02em;
  }

  .session-controls {
    padding: 0.75rem;
    display: grid;
    gap: 0.45rem;
  }

  .session-controls label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--label);
  }

  .session-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
  }

  .session-header h2 {
    margin: 0;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .section-label {
    margin: 0.35rem 0 0;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--label);
  }

  .session-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.45rem;
  }

  .session-item {
    width: 100%;
    text-align: left;
    padding: 0.65rem;
    border: 1px solid var(--session-border);
    background: var(--session-bg);
    color: inherit;
    border-radius: 12px;
    display: grid;
    gap: 0.35rem;
    cursor: pointer;
  }

  .session-item.selected {
    border-color: var(--session-selected);
    box-shadow: 0 0 0 1px var(--session-selected);
  }

  .row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
  }

  .meta-line {
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .session-title {
    font-weight: 700;
    font-size: 0.88rem;
  }

  .status {
    border: 1px solid var(--session-status-idle);
    background: color-mix(in srgb, var(--session-status-idle) 18%, transparent);
    color: var(--fg);
    border-radius: 999px;
    padding: 0.1rem 0.55rem;
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    flex: 0 0 auto;
  }

  .status.waiting {
    border-color: var(--session-status-waiting);
    background: color-mix(in srgb, var(--session-status-waiting) 18%, transparent);
  }

  .status.running {
    border-color: var(--session-status-running);
    background: color-mix(in srgb, var(--session-status-running) 18%, transparent);
  }

  .status.idle {
    border-color: var(--session-status-idle);
    background: color-mix(in srgb, var(--session-status-idle) 18%, transparent);
  }

  .mono {
    font-family: 'IBM Plex Mono', 'Fira Code', monospace;
    font-size: 0.72rem;
    word-break: break-all;
  }

  .session-controls details {
    border: 1px solid var(--session-border);
    background: var(--session-bg);
    border-radius: 12px;
    padding: 0.6rem;
  }

  .session-controls summary {
    cursor: pointer;
    list-style: none;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--label);
  }

  .session-controls summary::-webkit-details-marker {
    display: none;
  }

  .session-old {
    display: flex;
    gap: 0.6rem;
    justify-content: space-between;
    align-items: flex-start;
  }

  .session-old-meta {
    display: grid;
    gap: 0.2rem;
    min-width: 0;
  }

  .session-old-title {
    margin: 0;
    font-weight: 800;
    font-size: 0.85rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  input,
  button {
    font: inherit;
  }

  input {
    min-height: 40px;
    border-radius: 10px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    color: var(--input-fg);
    padding: 0 0.7rem;
  }

  .control-actions {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.45rem;
    margin-top: 0.3rem;
  }

  button {
    min-height: 40px;
    border-radius: 10px;
    border: 1px solid var(--primary-border);
    background: var(--primary-bg);
    color: var(--primary-fg);
    font-weight: 700;
  }

  button.secondary {
    border-color: var(--secondary-border);
    background: var(--secondary-bg);
    color: var(--secondary-fg);
  }

  button:disabled {
    opacity: 0.58;
  }

  .meta,
  .error {
    margin: 0;
    font-size: 0.76rem;
  }

  .meta {
    color: var(--meta);
  }

  .error {
    color: var(--error);
  }

  .timeline-wrap {
    position: relative;
    min-height: 0;
  }

  .timeline {
    height: 100%;
    max-height: calc(100dvh - 350px);
    min-height: 220px;
    overflow-y: auto;
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
    border-radius: 999px;
    border-color: #3b6ea7;
    background: #16335a;
    color: #d0e9ff;
    box-shadow: 0 10px 25px rgb(7 12 24 / 0.35);
  }

  .composer {
    padding: 0.65rem;
    display: grid;
    gap: 0.55rem;
  }

  @media (min-width: 700px) {
    .shell {
      width: min(100%, 760px);
      grid-template-columns: 260px 1fr;
      grid-template-rows: auto 1fr auto;
      grid-template-areas:
        'header header'
        'controls stream'
        'composer composer';
    }

    .app-header {
      grid-area: header;
    }

    .session-controls {
      grid-area: controls;
      align-self: start;
      position: sticky;
      top: 0;
    }

    .timeline-wrap {
      grid-area: stream;
    }

    .timeline {
      max-height: calc(100dvh - 210px);
    }

    .composer {
      grid-area: composer;
    }
  }
</style>
