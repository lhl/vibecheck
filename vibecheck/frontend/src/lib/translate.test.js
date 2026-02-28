import { describe, expect, it, vi } from 'vitest'

describe('translate helpers', () => {
  async function loadTranslate() {
    vi.resetModules()
    return import('./translate')
  }

  it('computes cjk ratios and skip decisions', async () => {
    const { cjkRatio, shouldSkipTranslation } = await loadTranslate()
    expect(cjkRatio('Hello world')).toBe(0)
    expect(shouldSkipTranslation('こんにちは')).toBe(true)
    expect(shouldSkipTranslation('Hello こんにちは', 0.8)).toBe(false)
  })

  it('stores and returns cached translations', async () => {
    const { getCachedTranslation, setCachedTranslation } = await loadTranslate()

    expect(getCachedTranslation('missing')).toBe('')
    setCachedTranslation('', 'こんにちは')
    expect(getCachedTranslation('')).toBe('')

    setCachedTranslation('evt-1', '  こんにちは  ')
    expect(getCachedTranslation('evt-1')).toBe('こんにちは')
  })

  it('evicts oldest cache entries when the cache grows too large', async () => {
    const { getCachedTranslation, setCachedTranslation } = await loadTranslate()

    for (let i = 0; i < 205; i += 1) {
      setCachedTranslation(`evt-${i}`, `value-${i}`)
    }

    expect(getCachedTranslation('evt-0')).toBe('')
    expect(getCachedTranslation('evt-204')).toBe('value-204')
  })
})
