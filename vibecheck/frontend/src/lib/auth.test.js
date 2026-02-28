import { beforeEach, describe, expect, it } from 'vitest'
import { clearStoredPsk, extractPskFromHash, loadInitialPsk, storePsk } from './auth'

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

    expect(loadInitialPsk()).toBe('hash-value')
    expect(localStorage.getItem('vibecheck_psk')).toBe('hash-value')
  })

  it('stores and clears psk', () => {
    storePsk('abc123')
    expect(localStorage.getItem('vibecheck_psk')).toBe('abc123')

    clearStoredPsk()
    expect(localStorage.getItem('vibecheck_psk')).toBeNull()
  })
})
