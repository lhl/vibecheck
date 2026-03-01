import { render, waitFor } from '@testing-library/svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.svelte'
import { setConnection } from './stores/connection'
import { resetEvents } from './stores/events'

function installWebSocketStub() {
  class StubWebSocket {
    static OPEN = 1
    static instances = []

    constructor(url) {
      this.url = url
      this.readyState = StubWebSocket.OPEN
      this.onopen = null
      this.onclose = null
      this.onmessage = null
      this.onerror = null
      StubWebSocket.instances.push(this)
    }

    close() {
      if (this.onclose) {
        this.onclose({ code: 1000 })
      }
    }

    send() {
      return undefined
    }
  }

  vi.stubGlobal('WebSocket', StubWebSocket)
  return StubWebSocket
}

describe('notification session routing', () => {
  beforeEach(() => {
    localStorage.clear()
    window.location.hash = ''
    setConnection('disconnected', 0)
    resetEvents()
    installWebSocketStub()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    resetEvents()
  })

  it('resumes notification target session when it is initially not connectable', async () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')
    window.history.pushState({}, '', '/?sid=s-notif&notif_source=sw_notificationclick')

    let listCalls = 0
    const fetchSpy = vi.fn((resource, options = {}) => {
      if (resource === '/api/sessions') {
        listCalls += 1
        const sessions =
          listCalls === 1
            ? [
                {
                  id: 's-notif',
                  status: 'disconnected',
                  attach_mode: 'observe_only',
                  controllable: false,
                },
              ]
            : [
                {
                  id: 's-notif',
                  status: 'running',
                  attach_mode: 'live',
                  controllable: true,
                },
              ]

        return Promise.resolve(
          new Response(JSON.stringify(sessions), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }

      if (resource === '/api/sessions/s-notif/resume' && options.method === 'POST') {
        return Promise.resolve(
          new Response(JSON.stringify({ id: 's-notif', backlog: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }

      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    })

    vi.stubGlobal('fetch', fetchSpy)

    const StubWebSocket = window.WebSocket
    render(App)

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/sessions/s-notif/resume',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    await waitFor(() => {
      expect(
        StubWebSocket.instances.some((socket) => socket.url.includes('/ws/events/s-notif')),
      ).toBe(true)
    })
  })
})

