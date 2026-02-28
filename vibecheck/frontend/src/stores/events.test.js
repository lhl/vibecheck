import { get } from 'svelte/store'
import { beforeEach, describe, expect, it } from 'vitest'
import {
  appendEvent,
  events,
  messages,
  pendingApproval,
  pendingInput,
  resetEvents,
} from './events'

describe('events store', () => {
  beforeEach(() => {
    resetEvents()
  })

  it('caps event list at 500 items (fifo)', () => {
    for (let index = 0; index < 505; index += 1) {
      appendEvent({ type: 'assistant', id: `evt-${index}`, content: `message-${index}` })
    }

    const current = get(events)
    expect(current).toHaveLength(500)
    expect(current[0].id).toBe('evt-5')
    expect(current.at(-1)?.id).toBe('evt-504')
  })

  it('derives chat messages from assistant and user events', () => {
    appendEvent({ type: 'state', id: 's-1', state: 'running' })
    appendEvent({ type: 'assistant', id: 'a-1', content: 'hello' })
    appendEvent({ type: 'user_message', id: 'u-1', content: 'hey' })

    expect(get(messages).map((entry) => entry.id)).toEqual(['a-1', 'u-1'])
  })

  it('tracks latest unresolved approval and clears when resolved', () => {
    appendEvent({
      type: 'approval_request',
      id: 'apr-1',
      call_id: 'call-1',
      tool_name: 'bash',
      args: { command: 'ls' },
    })
    expect(get(pendingApproval)?.call_id).toBe('call-1')

    appendEvent({
      type: 'approval_resolution',
      id: 'ares-1',
      call_id: 'call-1',
      approved: true,
      edited_args: null,
    })
    expect(get(pendingApproval)).toBeNull()
  })

  it('tracks latest unresolved input and clears when resolved', () => {
    appendEvent({
      type: 'input_request',
      id: 'ir-1',
      request_id: 'req-1',
      question: 'choose',
      options: ['a', 'b'],
    })
    expect(get(pendingInput)?.request_id).toBe('req-1')

    appendEvent({
      type: 'input_resolution',
      id: 'ires-1',
      request_id: 'req-1',
      response: 'a',
    })
    expect(get(pendingInput)).toBeNull()
  })
})
