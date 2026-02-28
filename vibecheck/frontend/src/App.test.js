import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.svelte'
import { setConnection } from './stores/connection'
import { appendEvent, resetEvents } from './stores/events'

function installWebSocketStub() {
  class StubWebSocket {
    static OPEN = 1

    constructor() {
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
}

describe('App phase 4 shell', () => {
  beforeEach(() => {
    localStorage.clear()
    window.location.hash = ''
    setConnection('disconnected', 0)
    resetEvents()
    installWebSocketStub()
    vi.stubGlobal(
      'fetch',
      vi.fn((resource, options = {}) => {
        if (resource === '/api/sessions') {
          return Promise.resolve(
            new Response(
              JSON.stringify([
                { id: 's-1', status: 'running' },
                { id: 's-2', status: 'running' },
              ]),
              { status: 200, headers: { 'Content-Type': 'application/json' } },
            ),
          )
        }

        if (options.method === 'POST') {
          return Promise.resolve(
            new Response(JSON.stringify({ status: 'ok' }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          )
        }

        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    resetEvents()
  })

  it('shows a psk entry screen when key is not configured', () => {
    render(App)

    expect(screen.getByRole('heading', { name: 'Enter PSK' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save Key' })).toBeInTheDocument()
  })

  it('renders chat shell after psk is stored', () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')

    render(App)

    expect(screen.getByRole('heading', { name: 'vibecheck' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Message input' })).toHaveAttribute('placeholder', 'Send a message...')
  })

  it('persists the auto-translate toggle', async () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')

    render(App)

    const button = screen.getByRole('button', { name: 'Auto-translate' })
    expect(button).toHaveTextContent('Enable auto-translate')

    await fireEvent.click(button)
    expect(localStorage.getItem('vibecheck_auto_translate')).toBe('true')
    expect(button).toHaveTextContent('Disable auto-translate')
  })

  it('handles push approve action by resolving the pending approval via REST', async () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')
    window.history.pushState({}, '', '/?sid=s-1&action=approve')

    const fetchSpy = vi.fn((resource, options = {}) => {
      if (resource === '/api/sessions') {
        return Promise.resolve(
          new Response(JSON.stringify([{ id: 's-1', status: 'running' }]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }

      if (resource === '/api/sessions/s-1/state') {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              state: 'waiting_approval',
              attach_mode: 'observe_only',
              controllable: false,
              pending_approval: { call_id: 'tc-1', tool_name: 'bash', args: {} },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        )
      }

      if (resource === '/api/sessions/s-1/approve' && options.method === 'POST') {
        return Promise.resolve(
          new Response(JSON.stringify({ status: 'ok' }), {
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
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/sessions/s-1/approve',
        expect.objectContaining({ method: 'POST' }),
      )
    })

    const approveCall = fetchSpy.mock.calls.find((call) => call[0] === '/api/sessions/s-1/approve')
    expect(approveCall).toBeTruthy()
    const body = approveCall[1]?.body ? JSON.parse(approveCall[1].body) : null
    expect(body).toMatchObject({ call_id: 'tc-1', approved: true })
  })

  it('handles push approve action sent via service worker message', async () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')
    window.history.pushState({}, '', '/?sid=s-1')

    const serviceWorker = new EventTarget()
    const originalServiceWorker = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker')
    Object.defineProperty(navigator, 'serviceWorker', { value: serviceWorker, configurable: true })

    try {
      const fetchSpy = vi.fn((resource, options = {}) => {
        if (resource === '/api/sessions') {
          return Promise.resolve(
            new Response(JSON.stringify([{ id: 's-1', status: 'running' }]), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          )
        }

        if (resource === '/api/sessions/s-1/approve' && options.method === 'POST') {
          return Promise.resolve(
            new Response(JSON.stringify({ status: 'ok' }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          )
        }

        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
      })

      vi.stubGlobal('fetch', fetchSpy)

      render(App)

      await new Promise((resolve) => setTimeout(resolve, 0))

      serviceWorker.dispatchEvent(
        new window.MessageEvent('message', {
          data: { type: 'notification_action', action: 'approve', url: '/?sid=s-1', call_id: 'tc-1' },
        }),
      )

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          '/api/sessions/s-1/approve',
          expect.objectContaining({ method: 'POST' }),
        )
      })

      const approveCall = fetchSpy.mock.calls.find((call) => call[0] === '/api/sessions/s-1/approve')
      expect(approveCall).toBeTruthy()
      const body = approveCall[1]?.body ? JSON.parse(approveCall[1].body) : null
      expect(body).toMatchObject({ call_id: 'tc-1', approved: true })
      expect(fetchSpy).not.toHaveBeenCalledWith('/api/sessions/s-1/state', expect.anything())
    } finally {
      if (originalServiceWorker) {
        Object.defineProperty(navigator, 'serviceWorker', originalServiceWorker)
      } else {
        delete navigator.serviceWorker
      }
    }
  })

  it('shows new message button when user is scrolled up', async () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')
    localStorage.setItem('vibecheck_sid', 's-1')

    render(App)
    await screen.findByRole('combobox', { name: 'Known Sessions' })

    const stream = screen.getByTestId('chat-scroll')
    Object.defineProperty(stream, 'scrollHeight', { configurable: true, value: 1000 })
    Object.defineProperty(stream, 'clientHeight', { configurable: true, value: 500 })
    Object.defineProperty(stream, 'scrollTop', { configurable: true, writable: true, value: 0 })

    await fireEvent.scroll(stream)
    appendEvent({ type: 'assistant', id: 'msg-1', content: 'hello from ws' })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'New messages ↓' })).toBeInTheDocument()
    })
  })

  it('does not optimistically append a user bubble before websocket echo', async () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')
    localStorage.setItem('vibecheck_sid', 's-1')
    setConnection('connected', 0)

    render(App)

    const textbox = screen.getByRole('textbox', { name: 'Message input' })
    await fireEvent.input(textbox, { target: { value: 'hello over post' } })
    await fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(screen.queryByText('hello over post')).not.toBeInTheDocument()
  })

  it('clears timeline when switching sessions', async () => {
    localStorage.setItem('vibecheck_psk', 'dev-psk')
    localStorage.setItem('vibecheck_sid', 's-1')

    render(App)

    appendEvent({ type: 'assistant', id: 'msg-switch-1', content: 'from session s-1' })
    expect(await screen.findByText('from session s-1')).toBeInTheDocument()

    const picker = await screen.findByRole('combobox', { name: 'Known Sessions' })
    await fireEvent.change(picker, { target: { value: 's-2' } })

    await waitFor(() => {
      expect(screen.queryByText('from session s-1')).not.toBeInTheDocument()
    })
  })
})
