const SHELL_CACHE = 'vibecheck-shell-v4'
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
    },
  }

  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification?.data?.url || '/'
  const source = 'sw_notificationclick'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (clients) => {
      const targetUrl = new URL(url, self.location.origin)
      const decorated = `${targetUrl.pathname}${targetUrl.search}${targetUrl.search ? '&' : '?'}notif_source=${encodeURIComponent(source)}`
      const candidates = []

      for (const client of clients) {
        try {
          const clientUrl = new URL(client.url)
          // Match by app origin + path. Ignore query params so fresh app URLs still match.
          if (clientUrl.origin === targetUrl.origin && clientUrl.pathname === targetUrl.pathname) {
            candidates.push(client)
          }
        } catch {
          // invalid URL, skip
        }
      }

      if (candidates.length > 0) {
        const active = candidates.find((client) => client.focused || client.visibilityState === 'visible')
        const targetClient = active || candidates[0]
        if (typeof targetClient.navigate === 'function') {
          try {
            await targetClient.navigate(decorated)
          } catch {
            // navigation can fail if client no longer exists; open a fresh window on the target session
            return self.clients.openWindow(decorated)
          }
        }
        return targetClient.focus()
      }
      return self.clients.openWindow(decorated)
    }),
  )
})
