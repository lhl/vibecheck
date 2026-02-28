function urlBase64ToUint8Array(base64UrlString) {
  const trimmed = typeof base64UrlString === 'string' ? base64UrlString.trim() : ''
  if (!trimmed) {
    throw new Error('VAPID public key is missing.')
  }

  const padding = '='.repeat((4 - (trimmed.length % 4)) % 4)
  const base64 = (trimmed + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const bytes = new Uint8Array(raw.length)
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index)
  }
  return bytes
}

export function isPushSupported() {
  return Boolean(
    typeof window !== 'undefined' &&
      'Notification' in window &&
      'serviceWorker' in navigator &&
      'PushManager' in window,
  )
}

async function requestPermission() {
  if (Notification.permission === 'granted') {
    return 'granted'
  }
  if (Notification.permission === 'denied') {
    return 'denied'
  }
  return Notification.requestPermission()
}

async function fetchVapidKey(psk) {
  const response = await fetch('/api/push/vapid-key', {
    headers: {
      ...(psk ? { 'X-PSK': psk } : {}),
    },
  })
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`.trim())
  }
  const payload = await response.json()
  const key = typeof payload?.public_key === 'string' ? payload.public_key.trim() : ''
  if (!key) {
    throw new Error('Server returned an empty VAPID key.')
  }
  return key
}

async function sendSubscription(psk, subscription) {
  const payload = typeof subscription?.toJSON === 'function' ? subscription.toJSON() : subscription
  const response = await fetch('/api/push/subscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(psk ? { 'X-PSK': psk } : {}),
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`.trim())
  }
}

export async function subscribeToPush(psk) {
  if (!isPushSupported()) {
    throw new Error('Push notifications are not supported in this browser.')
  }

  const permission = await requestPermission()
  if (permission !== 'granted') {
    throw new Error('Notifications permission was not granted.')
  }

  const registration = await navigator.serviceWorker.ready
  const publicKey = await fetchVapidKey(psk)
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  })
  await sendSubscription(psk, subscription)
  return subscription
}

export async function unsubscribeFromPush(psk) {
  if (!isPushSupported()) {
    return false
  }

  const registration = await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.getSubscription()
  if (!subscription) {
    return true
  }

  const endpoint = subscription.endpoint
  await subscription.unsubscribe()

  const response = await fetch('/api/push/unsubscribe', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(psk ? { 'X-PSK': psk } : {}),
    },
    body: JSON.stringify({ endpoint }),
  })
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`.trim())
  }

  return true
}

export const __test__ = {
  urlBase64ToUint8Array,
}

