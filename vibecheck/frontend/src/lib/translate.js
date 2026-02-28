const cache = new Map()

export function getCachedTranslation(eventId) {
  return cache.get(eventId) || ''
}

export function setCachedTranslation(eventId, translatedText) {
  if (!eventId) {
    return
  }
  const trimmed = typeof translatedText === 'string' ? translatedText.trim() : ''
  if (!trimmed) {
    return
  }
  cache.set(eventId, trimmed)
}

export function cjkRatio(text) {
  const value = typeof text === 'string' ? text : ''
  const chars = [...value].filter((ch) => ch.trim() !== '')
  if (chars.length === 0) {
    return 0
  }

  let cjk = 0
  for (const ch of chars) {
    const code = ch.codePointAt(0) || 0
    const isCjk =
      (code >= 0x3040 && code <= 0x30ff) || // hiragana/katakana
      (code >= 0x31f0 && code <= 0x31ff) || // katakana phonetic extensions
      (code >= 0x3400 && code <= 0x4dbf) || // cjk extension A
      (code >= 0x4e00 && code <= 0x9fff) || // cjk unified ideographs
      (code >= 0xac00 && code <= 0xd7af) // hangul syllables
    if (isCjk) {
      cjk += 1
    }
  }

  return cjk / chars.length
}

export function shouldSkipTranslation(text, threshold = 0.3) {
  return cjkRatio(text) > threshold
}

