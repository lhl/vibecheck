<script>
  import { onDestroy, onMount, tick } from 'svelte'
  import ApprovalPanel from './components/ApprovalPanel.svelte'
  import ChatMessage from './components/ChatMessage.svelte'
  import ConnectionStatus from './components/ConnectionStatus.svelte'
  import InputBar from './components/InputBar.svelte'
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
    loadVoiceLanguage,
    storeAutoTranslateEnabled,
    storeNotificationsEnabled,
    storeVoiceLanguage,
  } from './lib/settings'
  import { createWebSocket } from './lib/ws'
  import { connection } from './stores/connection'
  import {
    appendEvent,
    events,
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

  $: pushSupported = isPushSupported()

  let isNearBottom = true
  let showNewMessages = false
  let renderedTimelineCount = 0

  $: timeline = $events.filter((event) =>
    event.type === 'assistant' || event.type === 'user_message' || event.type === 'tool_call',
  )
  $: latestState = [...$events].reverse().find((event) => event.type === 'state') || null

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

    try {
      const payload = await apiJson('/api/sessions')
      sessions = Array.isArray(payload) ? payload : []
      sessionError = ''

      if (!sessionId && sessions.length > 0) {
        sessionId = sessions[0].id
      }

      if (sessionId) {
        storeSessionId(sessionId)
      }
    } catch (error) {
      sessionError = error instanceof Error ? error.message : 'Failed to load sessions'
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

    const shouldResetTimeline = activeSessionId !== sessionId
    disconnectSocket()
    if (shouldResetTimeline) {
      resetEvents()
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
      if (sessionId) {
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

  function handleSessionSelect(event) {
    sessionId = event.currentTarget.value
    if (sessionId) {
      storeSessionId(sessionId)
      connectSocket()
    }
  }

  function handleVoiceLanguageSelect(event) {
    voiceLanguage = event.currentTarget.value
    storeVoiceLanguage(voiceLanguage)
  }

  function toggleAutoTranslate() {
    autoTranslateEnabled = !autoTranslateEnabled
    storeAutoTranslateEnabled(autoTranslateEnabled)
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

          if (sessionId) {
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
      <label for="session-id">Session</label>
      <input
        id="session-id"
        value={sessionId}
        placeholder="Session ID"
        on:change={handleSessionInput}
      />

      {#if sessions.length > 0}
        <label for="session-pick">Known Sessions</label>
        <select id="session-pick" value={sessionId} on:change={handleSessionSelect}>
          {#each sessions as session}
            <option value={session.id}>{session.id}</option>
          {/each}
        </select>
      {/if}

      <label for="voice-lang">Voice language</label>
      <select id="voice-lang" value={voiceLanguage} on:change={handleVoiceLanguageSelect}>
        <option value="ja">JA</option>
        <option value="en">EN</option>
      </select>

      <label for="translate-toggle">Auto-translate</label>
      <button id="translate-toggle" type="button" class="secondary" on:click={toggleAutoTranslate}>
        {autoTranslateEnabled ? 'Disable auto-translate' : 'Enable auto-translate'}
      </button>

      <label for="notify-toggle">Notifications</label>
      <button
        id="notify-toggle"
        type="button"
        class="secondary"
        disabled={!pushSupported || notificationsBusy}
        on:click={toggleNotifications}
      >
        {notificationsEnabled ? 'Disable notifications' : 'Enable notifications'}
      </button>
      {#if !pushSupported}
        <p class="meta">Push not supported in this browser.</p>
      {/if}
      {#if notificationsError}
        <p class="error">{notificationsError}</p>
      {/if}

      <div class="control-actions">
        <button type="button" on:click={connectSocket} disabled={!sessionId}>Connect</button>
        <button type="button" class="secondary" on:click={disconnectSocket}>Disconnect</button>
        <button type="button" class="secondary" on:click={refreshSessions}>Refresh</button>
        <button type="button" class="danger" on:click={clearPsk}>Forget Key</button>
      </div>

      <p class="meta">state: {latestState?.state || 'unknown'}</p>
      {#if sessionError}
        <p class="error">{sessionError}</p>
      {/if}
    </section>

    <section class="timeline-wrap">
      <div class="timeline" bind:this={streamElement} on:scroll={onStreamScroll} data-testid="chat-scroll">
        {#if timeline.length === 0}
          <p class="empty">No events yet. Connect to a session and trigger a turn.</p>
        {:else}
          {#each timeline as event, index (event.id || `${event.type}-${index}`)}
            {#if event.type === 'tool_call'}
              <ToolCallCard toolCall={event} result={$toolResultsByCall.get(event.call_id) || null} />
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
  :global(html),
  :global(body) {
    margin: 0;
    min-height: 100%;
    background:
      radial-gradient(circle at 15% 10%, #20304f, transparent 35%),
      radial-gradient(circle at 90% 5%, #4f2d19, transparent 28%),
      #0d111b;
    color: #eef3ff;
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
    border: 1px solid #43557a;
    border-radius: 16px;
    background: linear-gradient(160deg, #1b2438, #12192a);
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
    color: #bbc7e2;
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
    border: 1px solid #334766;
    border-radius: 16px;
    background: linear-gradient(165deg, #1c2438, #111a2a);
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
    color: #9eb0d5;
  }

  input,
  select,
  button {
    font: inherit;
  }

  input,
  select {
    min-height: 40px;
    border-radius: 10px;
    border: 1px solid #405475;
    background: #0f1727;
    color: #dce8ff;
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
    border: 1px solid #8a6346;
    background: #362416;
    color: #ffe1c6;
    font-weight: 700;
  }

  button.secondary {
    border-color: #48628c;
    background: #1a2740;
    color: #d3e5ff;
  }

  button.danger {
    border-color: #8b4a4a;
    background: #351819;
    color: #ffd1d1;
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
    color: #9eb0d5;
  }

  .error {
    color: #ffbbbb;
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
    color: #afbdd9;
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
