const SHELL_CACHE = 'vibecheck-shell-v3'
const APP_SHELL = ['/']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => {
      return cache.addAll(APP_SHELL)
    }),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL_CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  if (event.request.mode !== 'navigate') {
    return
  }

  event.respondWith(
    fetch(event.request).then((response) => {
      const clone = response.clone()
      caches.open(SHELL_CACHE).then((cache) => cache.put('/', clone))
      return response
    }).catch(async () => {
      const cache = await caches.open(SHELL_CACHE)
      return cache.match('/') || Response.error()
    }),
  )
})

self.addEventListener('push', (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = {}
  }

  const title = typeof payload.title === 'string' && payload.title.trim() ? payload.title : 'vibecheck'
  const options = {
    body: typeof payload.body === 'string' ? payload.body : '',
    tag: typeof payload.tag === 'string' ? payload.tag : undefined,
    requireInteraction: Boolean(payload.requireInteraction),
    data: {
      url: typeof payload.url === 'string' ? payload.url : '/',
      call_id: typeof payload.call_id === 'string' ? payload.call_id : null,
      default_action: Array.isArray(payload.actions) && payload.actions.length > 0
        ? payload.actions[0].action || null
        : null,
    },
    actions: Array.isArray(payload.actions) ? payload.actions : [],
  }

  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  // event.action is the button ID ("approve"/"deny") when an action button is clicked,
  // or empty string when the notification body is tapped. On some Android Chrome versions,
  // event.action may be empty even for button clicks — fall back to the first action
  // (approve) when there's a call_id, since the user tapped an approval notification.
  let action = event.action || ''
  const url = event.notification?.data?.url || '/'
  const callId = event.notification?.data?.call_id || null
  if (!action && callId) {
    action = event.notification?.data?.default_action || ''
  }
  const source = 'sw_notificationclick'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      // Match any app window on the same origin — don't require ?sid= in the URL,
      // since the PWA may have been opened fresh without a session in the URL.
      for (const client of clients) {
        try {
          if (client.url && new URL(client.url).origin === self.location.origin) {
            client.postMessage({
              type: 'notification_action',
              action,
              url,
              call_id: callId,
              source,
            })
            return client.focus()
          }
        } catch {
          // invalid URL, skip
        }
      }

      let decorated = url
      if (action) {
        decorated += `${url.includes('?') ? '&' : '?'}action=${encodeURIComponent(action)}`
      }
      if (callId) {
        decorated += `${decorated.includes('?') ? '&' : '?'}call_id=${encodeURIComponent(callId)}`
      }
      decorated += `${decorated.includes('?') ? '&' : '?'}notif_source=${encodeURIComponent(source)}`
      return self.clients.openWindow(decorated)
    }),
  )
})
