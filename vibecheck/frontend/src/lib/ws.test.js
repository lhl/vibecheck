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
    second.open()
    second.close(1006)

    vi.advanceTimersByTime(2000)
    expect(MockWebSocket.instances).toHaveLength(3)

    for (let index = 0; index < 8; index += 1) {
      const current = MockWebSocket.instances.at(-1)
      current.open()
      current.close(1006)
      vi.advanceTimersByTime(30000)
    }

    expect(get(connection).reconnectAttempts).toBeGreaterThanOrEqual(3)
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

  it('closes stale connection when heartbeat is missed', () => {
    const client = createWebSocket('/ws/events/s-1', 'dev-psk')
    client.connect()

    const socket = MockWebSocket.instances[0]
    socket.open()

    vi.advanceTimersByTime(46000)
    expect(get(connection).status).toBe('connecting')
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
