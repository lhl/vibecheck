import { derived, writable } from 'svelte/store'

const MAX_EVENTS = 500

export const events = writable([])

function pushWithCap(list, event) {
  const next = [...list, event]
  if (next.length <= MAX_EVENTS) {
    return next
  }
  return next.slice(next.length - MAX_EVENTS)
}

function hasEventId(list, event) {
  if (!event || typeof event !== 'object' || !event.id) {
    return false
  }
  return list.some((entry) => entry.id === event.id)
}

export function appendEvent(event) {
  if (!event || typeof event !== 'object' || !event.type) {
    return
  }

  events.update((list) => {
    if (hasEventId(list, event)) {
      return list
    }
    return pushWithCap(list, event)
  })
}

export function mergeEvents(incoming) {
  if (!Array.isArray(incoming)) {
    return
  }
  for (const event of incoming) {
    appendEvent(event)
  }
}

export function resetEvents() {
  events.set([])
}

export const messages = derived(events, ($events) =>
  $events.filter((event) => event.type === 'assistant' || event.type === 'user_message'),
)

export const toolCalls = derived(events, ($events) =>
  $events.filter((event) => event.type === 'tool_call'),
)

export const toolResultsByCall = derived(events, ($events) => {
  const results = new Map()
  for (const event of $events) {
    if (event.type === 'tool_result' && event.call_id) {
      results.set(event.call_id, event)
    }
  }
  return results
})

export const pendingApproval = derived(events, ($events) => {
  const resolvedCallIds = new Set()

  for (let index = $events.length - 1; index >= 0; index -= 1) {
    const event = $events[index]
    if (event.type === 'approval_resolution' && event.call_id) {
      resolvedCallIds.add(event.call_id)
      continue
    }

    if (event.type === 'approval_request' && event.call_id && !resolvedCallIds.has(event.call_id)) {
      return event
    }
  }

  return null
})

export const latestStats = derived(events, ($events) => {
  for (let i = $events.length - 1; i >= 0; i--) {
    if ($events[i].type === 'stats') {
      return $events[i]
    }
  }
  return null
})

export const pendingInput = derived(events, ($events) => {
  const resolvedRequestIds = new Set()

  for (let index = $events.length - 1; index >= 0; index -= 1) {
    const event = $events[index]
    if (event.type === 'input_resolution' && event.request_id) {
      resolvedRequestIds.add(event.request_id)
      continue
    }

    if (event.type === 'input_request' && event.request_id && !resolvedRequestIds.has(event.request_id)) {
      return event
    }
  }

  return null
})
