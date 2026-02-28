import { beforeEach, describe, expect, it } from 'vitest'
import { loadVoiceLanguage, storeVoiceLanguage } from './settings'

describe('settings', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('defaults to ja when unset', () => {
    expect(loadVoiceLanguage()).toBe('ja')
  })

  it('stores and loads supported voice languages', () => {
    storeVoiceLanguage('en')
    expect(loadVoiceLanguage()).toBe('en')

    storeVoiceLanguage('ja')
    expect(loadVoiceLanguage()).toBe('ja')
  })

  it('ignores unsupported values', () => {
    storeVoiceLanguage('fr')
    expect(loadVoiceLanguage()).toBe('ja')
  })
})

