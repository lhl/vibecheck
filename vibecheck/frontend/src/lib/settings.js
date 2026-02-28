const VOICE_LANGUAGE_KEY = 'vibecheck_voice_language'
const NOTIFICATIONS_ENABLED_KEY = 'vibecheck_notifications_enabled'
const AUTO_TRANSLATE_KEY = 'vibecheck_auto_translate'

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

export function loadVoiceLanguage() {
  const stored = safeLocalStorageGet(VOICE_LANGUAGE_KEY)
  if (stored === 'en' || stored === 'ja') {
    return stored
  }
  return 'ja'
}

export function storeVoiceLanguage(value) {
  const trimmed = typeof value === 'string' ? value.trim().toLowerCase() : ''
  if (trimmed !== 'en' && trimmed !== 'ja') {
    return
  }
  safeLocalStorageSet(VOICE_LANGUAGE_KEY, trimmed)
}

export function loadNotificationsEnabled() {
  return safeLocalStorageGet(NOTIFICATIONS_ENABLED_KEY) === 'true'
}

export function storeNotificationsEnabled(value) {
  safeLocalStorageSet(NOTIFICATIONS_ENABLED_KEY, value ? 'true' : 'false')
}

export function loadAutoTranslateEnabled() {
  return safeLocalStorageGet(AUTO_TRANSLATE_KEY) === 'true'
}

export function storeAutoTranslateEnabled(value) {
  safeLocalStorageSet(AUTO_TRANSLATE_KEY, value ? 'true' : 'false')
}
