import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.svelte'
import { setConnection } from './stores/connection'
import { appendEvent, resetEvents } from './stores/events'

function installWebSocketStub() {
  class StubWebSocket {
    static OPEN = 1
    static instances = []

    constructor(url) {
      this.url = url
      StubWebSocket.instances.push(this)
      this.readyState = StubWebSocket.OPEN
      this.onopen = null
      this.onclose = null
      this.onmessage = null
      this.onerror = null
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

describe('App YOLO mode', () => {
  beforeEach(() => {
    localStorage.clear()
    window.history.pushState({}, '', '/')
    setConnection('disconnected', 0)
    resetEvents()
    installWebSocketStub()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    resetEvents()
  })

  it('toggles auto-approve from settings and hides approval cards', async () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')
    window.history.pushState({}, '', '/?sid=s-1')

    const fetchSpy = vi.fn((resource, options = {}) => {
      if (resource === '/api/sessions') {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: 's-1',
                status: 'running',
                last_activity: '2026-02-28T00:00:00Z',
                message_count: 3,
                title: 'First session',
                attach_mode: 'live',
                controllable: true,
              },
            ]),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        )
      }

      if (resource === '/api/sessions/s-1/auto-approve' && options.method === 'POST') {
        return Promise.resolve(
          new Response(JSON.stringify({ status: 'ok', auto_approve: true }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }

      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    })
    vi.stubGlobal('fetch', fetchSpy)

    render(App)

    await waitFor(() => {
      expect(screen.getByTestId('status-line')).toBeInTheDocument()
    })
    await fireEvent.click(screen.getByTestId('status-line'))
    await fireEvent.click(screen.getByRole('button', { name: 'Enable YOLO mode' }))

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/sessions/s-1/auto-approve',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    const toggleCall = fetchSpy.mock.calls.find((call) => call[0] === '/api/sessions/s-1/auto-approve')
    const body = toggleCall?.[1]?.body ? JSON.parse(toggleCall[1].body) : null
    expect(body).toEqual({ enabled: true })

    appendEvent({
      type: 'approval_request',
      id: 'approval-yolo-1',
      timestamp: Date.now() / 1000,
      call_id: 'tc-yolo-1',
      tool_name: 'bash',
      args: { command: 'ls' },
    })

    expect(screen.queryByText('Approval Needed')).not.toBeInTheDocument()
    expect(screen.getByTestId('status-line')).toHaveClass('yolo-active')
    expect(screen.getByText('YOLO')).toBeInTheDocument()
  })
})
