import { describe, expect, it } from 'vitest'
import { cjkRatio, shouldSkipTranslation } from './translate'

describe('translate helpers', () => {
  it('computes cjk ratios and skip decisions', () => {
    expect(cjkRatio('Hello world')).toBe(0)
    expect(shouldSkipTranslation('こんにちは')).toBe(true)
    expect(shouldSkipTranslation('Hello こんにちは', 0.8)).toBe(false)
  })
})

