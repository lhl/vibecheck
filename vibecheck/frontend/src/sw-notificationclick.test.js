import { readFileSync } from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { describe, expect, it, vi } from 'vitest'

const SW_PATH = path.resolve(process.cwd(), 'public/sw.js')

function loadServiceWorkerHarness() {
  const listeners = new Map()
  const self = {
    location: { origin: 'https://vibecheck.shisa.ai' },
    addEventListener(type, handler) {
      listeners.set(type, handler)
    },
    skipWaiting: vi.fn(),
    clients: {
      claim: vi.fn().mockResolvedValue(undefined),
      matchAll: vi.fn(),
      openWindow: vi.fn(),
    },
    registration: {
      showNotification: vi.fn().mockResolvedValue(undefined),
    },
  }

  const caches = {
    open: vi.fn().mockResolvedValue({
      addAll: vi.fn().mockResolvedValue(undefined),
      put: vi.fn().mockResolvedValue(undefined),
      match: vi.fn().mockResolvedValue(null),
    }),
    keys: vi.fn().mockResolvedValue([]),
    delete: vi.fn().mockResolvedValue(true),
  }

  const source = readFileSync(SW_PATH, 'utf8')
  vm.runInNewContext(source, {
    self,
    caches,
    URL,
    Promise,
    Response,
    encodeURIComponent,
  })

  return { self, listeners }
}

describe('service worker notificationclick routing', () => {
  it('opens a deep-linked window when existing client navigation fails', async () => {
    const { self, listeners } = loadServiceWorkerHarness()
    const handler = listeners.get('notificationclick')
    expect(typeof handler).toBe('function')

    const existingClient = {
      url: 'https://vibecheck.shisa.ai/',
      focused: true,
      visibilityState: 'visible',
      navigate: vi.fn().mockRejectedValue(new Error('navigation_failed')),
      focus: vi.fn().mockResolvedValue(undefined),
    }

    self.clients.matchAll.mockResolvedValue([existingClient])
    self.clients.openWindow.mockResolvedValue(undefined)

    let completion = Promise.resolve()
    handler({
      notification: {
        data: { url: '/?sid=s-1' },
        close: vi.fn(),
      },
      waitUntil(promise) {
        completion = promise
      },
    })

    await completion

    expect(existingClient.navigate).toHaveBeenCalledWith('/?sid=s-1&notif_source=sw_notificationclick')
    expect(self.clients.openWindow).toHaveBeenCalledWith('/?sid=s-1&notif_source=sw_notificationclick')
    expect(existingClient.focus).not.toHaveBeenCalled()
  })
})
