import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { get } from 'svelte/store'
import { connection, resetConnection } from '../stores/connection'
import { events, resetEvents } from '../stores/events'
import { createWebSocket } from './ws'

class MockWebSocket {
  static OPEN = 1
  static CLOSED = 3
  static instances = []

  constructor(url) {
    this.url = url
    this.readyState = MockWebSocket.CLOSED
    this.onopen = null
    this.onclose = null
    this.onmessage = null
    this.onerror = null
    this.sent = []
    MockWebSocket.instances.push(this)
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    if (this.onopen) {
      this.onopen({ type: 'open' })
    }
  }

  emitJson(payload) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(payload) })
    }
  }

  close(code = 1000) {
    this.readyState = MockWebSocket.CLOSED
    if (this.onclose) {
      this.onclose({ code })
    }
  }

  send(payload) {
    this.sent.push(payload)
  }
}

describe('createWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    resetConnection()
    resetEvents()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('connects and appends incoming events', () => {
    const client = createWebSocket('/ws/events/s-1', 'dev-psk')
    client.connect()

    expect(MockWebSocket.instances).toHaveLength(1)
    const socket = MockWebSocket.instances[0]

    socket.open()
    socket.emitJson({ type: 'assistant', id: 'evt-1', content: 'hello' })

    expect(get(connection).status).toBe('connected')
    expect(get(events).map((event) => event.id)).toContain('evt-1')
  })

  it('uses exponential reconnect backoff capped at 30s', () => {
    const client = createWebSocket('/ws/events/s-1', 'dev-psk')
    client.connect()

    const first = MockWebSocket.instances[0]
    first.open()
    first.close(1006)

    expect(get(connection).status).toBe('connecting')
    expect(get(connection).reconnectAttempts).toBe(1)

    vi.advanceTimersByTime(1000)
    expect(MockWebSocket.instances).toHaveLength(2)

    const second = MockWebSocket.instances[1]
    second.close(1006)
    expect(get(connection).reconnectAttempts).toBe(2)

    vi.advanceTimersByTime(2000)
    expect(MockWebSocket.instances).toHaveLength(3)

    for (let index = 0; index < 8; index += 1) {
      const current = MockWebSocket.instances.at(-1)
      current.close(1006)
      vi.advanceTimersByTime(30000)
    }

    expect(get(connection).reconnectAttempts).toBeGreaterThanOrEqual(3)
  })

  it('resets reconnect attempts after a successful reconnect', () => {
    const client = createWebSocket('/ws/events/s-1', 'dev-psk')
    client.connect()

    const first = MockWebSocket.instances[0]
    first.open()
    first.close(1006)

    expect(get(connection).reconnectAttempts).toBe(1)

    vi.advanceTimersByTime(1000)
    const second = MockWebSocket.instances[1]
    second.open()

    expect(get(connection).status).toBe('connected')
    expect(get(connection).reconnectAttempts).toBe(0)

    second.close(1006)
    expect(get(connection).status).toBe('connecting')
    expect(get(connection).reconnectAttempts).toBe(1)
  })

  it('disconnect prevents future reconnect attempts', () => {
    const client = createWebSocket('/ws/events/s-1', 'dev-psk')
    client.connect()

    const socket = MockWebSocket.instances[0]
    socket.open()

    client.disconnect()
    socket.close(1006)

    vi.advanceTimersByTime(60000)
    expect(MockWebSocket.instances).toHaveLength(1)
    expect(get(connection).status).toBe('disconnected')
  })

  it.each([4401, 4404])(
    'does not reconnect on terminal websocket close code %s',
    (terminalCloseCode) => {
      const client = createWebSocket('/ws/events/s-1', 'dev-psk')
      client.connect()

      const socket = MockWebSocket.instances[0]
      socket.open()
      socket.close(terminalCloseCode)

      expect(get(connection).status).toBe('disconnected')
      expect(get(connection).reconnectAttempts).toBe(0)

      vi.advanceTimersByTime(60000)
      expect(MockWebSocket.instances).toHaveLength(1)
    },
  )

  it('closes stale connection when heartbeat is missed', () => {
    const client = createWebSocket('/ws/events/s-1', 'dev-psk')
    client.connect()

    const socket = MockWebSocket.instances[0]
    socket.open()

    vi.advanceTimersByTime(46000)
    expect(get(connection).status).toBe('connecting')
  })

  it('ignores heartbeat events so they do not consume event backlog', () => {
    const client = createWebSocket('/ws/events/s-1', 'dev-psk')
    client.connect()

    const socket = MockWebSocket.instances[0]
    socket.open()
    socket.emitJson({ type: 'heartbeat', id: 'hb-1' })
    socket.emitJson({ type: 'assistant', id: 'a-1', content: 'real event' })

    const current = get(events)
    expect(current).toHaveLength(1)
    expect(current[0].id).toBe('a-1')
  })

  it('merges reconnect backlog payloads sent as arrays', () => {
    const client = createWebSocket('/ws/events/s-1', 'dev-psk')
    client.connect()

    const socket = MockWebSocket.instances[0]
    socket.open()
    socket.emitJson([
      { type: 'assistant', id: 'a-1', content: 'first' },
      { type: 'heartbeat', id: 'hb-1' },
      { type: 'assistant', id: 'a-2', content: 'second' },
    ])

    expect(get(events).map((event) => event.id)).toEqual(['a-1', 'a-2'])
  })

  it('includes psk in url query and sends serialized payloads', () => {
    const client = createWebSocket('/ws/events/s-1', 'abc')
    client.connect()

    const socket = MockWebSocket.instances[0]
    expect(socket.url).toContain('psk=abc')

    socket.open()
    expect(client.send({ hello: 'world' })).toBe(true)
    expect(socket.sent).toEqual(['{"hello":"world"}'])
  })
})
