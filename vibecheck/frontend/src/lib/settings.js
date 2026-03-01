const VOICE_LANGUAGE_KEY = 'vibecheck_voice_language'
const NOTIFICATIONS_ENABLED_KEY = 'vibecheck_notifications_enabled'
const YOLO_ENABLED_KEY = 'vibecheck_yolo_enabled'
const AUTO_TRANSLATE_KEY = 'vibecheck_auto_translate'
const THEME_KEY = 'vibecheck_theme'

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

export function loadYoloEnabled() {
  return safeLocalStorageGet(YOLO_ENABLED_KEY) === 'true'
}

export function storeYoloEnabled(value) {
  safeLocalStorageSet(YOLO_ENABLED_KEY, value ? 'true' : 'false')
}

export function loadAutoTranslateEnabled() {
  return safeLocalStorageGet(AUTO_TRANSLATE_KEY) === 'true'
}

export function storeAutoTranslateEnabled(value) {
  safeLocalStorageSet(AUTO_TRANSLATE_KEY, value ? 'true' : 'false')
}

export function loadThemePreference() {
  const stored = safeLocalStorageGet(THEME_KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'auto') {
    return stored
  }
  return 'auto'
}

export function storeThemePreference(value) {
  const trimmed = typeof value === 'string' ? value.trim().toLowerCase() : ''
  if (trimmed !== 'light' && trimmed !== 'dark' && trimmed !== 'auto') {
    return
  }
  safeLocalStorageSet(THEME_KEY, trimmed)
}
