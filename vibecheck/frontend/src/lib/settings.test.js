import { beforeEach, describe, expect, it } from 'vitest'
import {
  loadAutoTranslateEnabled,
  loadNotificationsEnabled,
  loadVoiceLanguage,
  loadYoloEnabled,
  storeAutoTranslateEnabled,
  storeNotificationsEnabled,
  storeVoiceLanguage,
  storeYoloEnabled,
} from './settings'

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

    storeVoiceLanguage('fr')
    expect(loadVoiceLanguage()).toBe('fr')
  })

  it('ignores unsupported values', () => {
    storeVoiceLanguage('xx')
    expect(loadVoiceLanguage()).toBe('ja')
  })

  it('persists notifications enabled toggle', () => {
    expect(loadNotificationsEnabled()).toBe(false)
    storeNotificationsEnabled(true)
    expect(loadNotificationsEnabled()).toBe(true)
    storeNotificationsEnabled(false)
    expect(loadNotificationsEnabled()).toBe(false)
  })

  it('persists auto-translate toggle', () => {
    expect(loadAutoTranslateEnabled()).toBe(false)
    storeAutoTranslateEnabled(true)
    expect(loadAutoTranslateEnabled()).toBe(true)
    storeAutoTranslateEnabled(false)
    expect(loadAutoTranslateEnabled()).toBe(false)
  })

  it('persists yolo mode toggle', () => {
    expect(loadYoloEnabled()).toBe(false)
    storeYoloEnabled(true)
    expect(loadYoloEnabled()).toBe(true)
    storeYoloEnabled(false)
    expect(loadYoloEnabled()).toBe(false)
  })
})
