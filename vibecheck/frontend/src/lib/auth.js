const PSK_KEY = 'vibecheck_psk'
const SESSION_KEY = 'vibecheck_sid'

function safeLocalStorageGet(key) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeLocalStorageSet(key, value) {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // no-op
  }
}

function safeLocalStorageRemove(key) {
  try {
    window.localStorage.removeItem(key)
  } catch {
    // no-op
  }
}

export function extractPskFromHash(hash) {
  if (!hash) {
    return ''
  }

  const normalized = hash.startsWith('#') ? hash.slice(1) : hash
  if (!normalized) {
    return ''
  }

  if (normalized.includes('=')) {
    const params = new URLSearchParams(normalized)
    return params.get('psk') || ''
  }

  if (normalized.startsWith('psk:')) {
    return decodeURIComponent(normalized.slice(4))
  }

  return ''
}

export function storePsk(psk) {
  const trimmed = typeof psk === 'string' ? psk.trim() : ''
  if (!trimmed) {
    return
  }
  safeLocalStorageSet(PSK_KEY, trimmed)
}

export function clearStoredPsk() {
  safeLocalStorageRemove(PSK_KEY)
}

export function loadInitialPsk() {
  const fromHash = extractPskFromHash(window.location.hash)
  if (fromHash) {
    storePsk(fromHash)
    try {
      const cleanUrl = `${window.location.pathname}${window.location.search}`
      window.history.replaceState(null, '', cleanUrl)
    } catch {
      // no-op
    }
    return fromHash
  }

  return safeLocalStorageGet(PSK_KEY) || ''
}

export function loadStoredSessionId() {
  return safeLocalStorageGet(SESSION_KEY) || ''
}

export function storeSessionId(sessionId) {
  const trimmed = typeof sessionId === 'string' ? sessionId.trim() : ''
  if (!trimmed) {
    return
  }
  safeLocalStorageSet(SESSION_KEY, trimmed)
}

export function clearStoredSessionId() {
  safeLocalStorageRemove(SESSION_KEY)
}
