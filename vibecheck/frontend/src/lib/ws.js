import { appendEvent, mergeEvents } from '../stores/events'
import { CONNECTION_STATES, setConnection } from '../stores/connection'

const HEARTBEAT_TIMEOUT_MS = 45_000
const RECONNECT_BASE_MS = 1_000
const RECONNECT_CAP_MS = 30_000
const TERMINAL_CLOSE_CODES = new Set([4401, 4404])

function withPsk(url, psk) {
  if (!psk) {
    return url
  }

  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}psk=${encodeURIComponent(psk)}`
}

function reconnectDelay(attempt) {
  return Math.min(RECONNECT_BASE_MS * 2 ** Math.max(0, attempt - 1), RECONNECT_CAP_MS)
}

export function createWebSocket(url, psk) {
  let socket = null
  let reconnectTimer = null
  let heartbeatTimer = null
  let reconnectAttempts = 0
  let shouldReconnect = true

  const clearReconnectTimer = () => {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  const clearHeartbeatTimer = () => {
    if (heartbeatTimer !== null) {
      clearTimeout(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  const armHeartbeatTimer = () => {
    clearHeartbeatTimer()
    heartbeatTimer = setTimeout(() => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close(4000)
      }
    }, HEARTBEAT_TIMEOUT_MS)
  }

  const scheduleReconnect = () => {
    if (!shouldReconnect) {
      return
    }

    reconnectAttempts += 1
    const delay = reconnectDelay(reconnectAttempts)
    setConnection(CONNECTION_STATES.CONNECTING, reconnectAttempts)

    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  const handleOpen = () => {
    reconnectAttempts = 0
    setConnection(CONNECTION_STATES.CONNECTED, 0)
    armHeartbeatTimer()
  }

  const handleMessage = (raw) => {
    armHeartbeatTimer()
    try {
      const payload = JSON.parse(raw.data)
      if (Array.isArray(payload)) {
        mergeEvents(payload.filter((event) => event?.type !== 'heartbeat'))
        return
      }

      if (payload?.type === 'heartbeat') {
        return
      }

      appendEvent(payload)
    } catch {
      // ignore malformed payloads
    }
  }

  const handleClose = (event) => {
    clearHeartbeatTimer()
    socket = null

    if (TERMINAL_CLOSE_CODES.has(Number(event?.code))) {
      clearReconnectTimer()
      reconnectAttempts = 0
      shouldReconnect = false
      setConnection(CONNECTION_STATES.DISCONNECTED, 0)
      return
    }

    if (!shouldReconnect) {
      setConnection(CONNECTION_STATES.DISCONNECTED, reconnectAttempts)
      return
    }

    scheduleReconnect()
  }

  const connect = () => {
    if (!shouldReconnect) {
      shouldReconnect = true
    }

    if (socket && socket.readyState === WebSocket.OPEN) {
      return
    }

    clearReconnectTimer()
    setConnection(CONNECTION_STATES.CONNECTING, reconnectAttempts)

    socket = new WebSocket(withPsk(url, psk))
    socket.onopen = handleOpen
    socket.onmessage = handleMessage
    socket.onerror = () => {
      // noop; onclose drives state transitions
    }
    socket.onclose = handleClose
  }

  const disconnect = () => {
    shouldReconnect = false
    clearReconnectTimer()
    clearHeartbeatTimer()

    if (socket) {
      const activeSocket = socket
      socket = null
      activeSocket.onclose = null
      activeSocket.close(1000)
    }

    reconnectAttempts = 0
    setConnection(CONNECTION_STATES.DISCONNECTED, reconnectAttempts)
  }

  const send = (payload) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return false
    }

    const serialized = typeof payload === 'string' ? payload : JSON.stringify(payload)
    socket.send(serialized)
    return true
  }

  return {
    connect,
    disconnect,
    send,
    state: {
      get reconnectAttempts() {
        return reconnectAttempts
      },
      get isConnected() {
        return Boolean(socket && socket.readyState === WebSocket.OPEN)
      },
    },
  }
}
