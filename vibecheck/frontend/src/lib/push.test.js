import { afterEach, describe, expect, it, vi } from 'vitest'
import { __test__, unsubscribeFromPush } from './push'

describe('push', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('decodes base64url VAPID keys into a Uint8Array', () => {
    const bytes = __test__.urlBase64ToUint8Array('SGVsbG8')
    const text = new TextDecoder().decode(bytes)
    expect(text).toBe('Hello')
  })

  function stubPushSupport(registration) {
    vi.stubGlobal('Notification', { permission: 'granted' })
    vi.stubGlobal('PushManager', function PushManager() {})
    vi.stubGlobal('navigator', { serviceWorker: { ready: Promise.resolve(registration) } })
  }

  it('unsubscribes on the backend before unsubscribing locally', async () => {
    const unsubscribeSpy = vi.fn(() => Promise.resolve(true))
    const subscription = { endpoint: 'https://example.com/endpoint', unsubscribe: unsubscribeSpy }
    const registration = {
      pushManager: {
        getSubscription: vi.fn(() => Promise.resolve(subscription)),
      },
    }
    stubPushSupport(registration)

    const fetchSpy = vi.fn(() => {
      expect(unsubscribeSpy).not.toHaveBeenCalled()
      return Promise.resolve(new Response('', { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchSpy)

    await expect(unsubscribeFromPush('dev-psk')).resolves.toBe(true)
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(unsubscribeSpy).toHaveBeenCalledTimes(1)
  })

  it('does not unsubscribe locally when backend unsubscribe fails', async () => {
    const unsubscribeSpy = vi.fn(() => Promise.resolve(true))
    const subscription = { endpoint: 'https://example.com/endpoint', unsubscribe: unsubscribeSpy }
    const registration = {
      pushManager: {
        getSubscription: vi.fn(() => Promise.resolve(subscription)),
      },
    }
    stubPushSupport(registration)

    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response('', { status: 500, statusText: 'Server Error' }))),
    )

    await expect(unsubscribeFromPush('dev-psk')).rejects.toThrow()
    expect(unsubscribeSpy).not.toHaveBeenCalled()
  })
})
