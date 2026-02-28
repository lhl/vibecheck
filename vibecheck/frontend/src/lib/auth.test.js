import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearStoredPsk,
  clearStoredSessionId,
  extractPskFromHash,
  loadInitialPsk,
  loadStoredSessionId,
  storePsk,
  storeSessionId,
} from './auth'

describe('auth helpers', () => {
  beforeEach(() => {
    localStorage.clear()
    window.location.hash = ''
  })

  it('reads psk from url hash parameters', () => {
    window.location.hash = '#psk=hash-value&session_id=alpha'
    expect(extractPskFromHash(window.location.hash)).toBe('hash-value')
  })

  it('prefers hash psk over localStorage and persists it', () => {
    localStorage.setItem('vibecheck_psk', 'stored-value')
    window.location.hash = '#psk=hash-value'
    const replaceSpy = vi.spyOn(window.history, 'replaceState')

    expect(loadInitialPsk()).toBe('hash-value')
    expect(localStorage.getItem('vibecheck_psk')).toBe('hash-value')
    expect(replaceSpy).toHaveBeenCalled()
    expect(window.location.hash).toBe('')
  })

  it('stores and clears psk', () => {
    storePsk('abc123')
    expect(localStorage.getItem('vibecheck_psk')).toBe('abc123')

    clearStoredPsk()
    expect(localStorage.getItem('vibecheck_psk')).toBeNull()
  })

  it('stores and clears session id', () => {
    storeSessionId('session-1')
    expect(loadStoredSessionId()).toBe('session-1')

    clearStoredSessionId()
    expect(loadStoredSessionId()).toBe('')
  })
})
