# Reference: Web Push Notifications with VAPID

> **Context:** vibecheck uses Web Push to notify the user's phone when Vibe needs approval or input — even when the browser is closed.
> **Relevant WUs:** WU-05 (prototype), WU-19 (backend), WU-20 (frontend), WU-22 (Ministral smart copy)
> **Libraries:** `pywebpush` (server), Push API + Notification API (browser)

---

## Three parties

Every push notification involves three actors:

| Actor | Role | Example |
|-------|------|---------|
| **Your server** | Decides when to push, encrypts payload, signs the request | vibecheck FastAPI backend |
| **Push service** | Holds messages, wakes the device, delivers to the browser | Google FCM (Chrome), Mozilla autopush (Firefox), Apple (Safari) |
| **The browser** | Subscribes, receives pushes via service worker, shows notifications | Chrome on Android, Safari on iOS |

Your server never talks to the browser directly for push. It always goes through the push service. The push service is chosen by the browser — you don't pick it and you don't register with it.

---

## VAPID in one paragraph

VAPID (Voluntary Application Server Identification) is how your server identifies itself to the push service. You generate an ECDSA P-256 keypair. The public key goes in the browser's subscribe call. The private key signs a JWT that accompanies every push request. The push service verifies the JWT to confirm the push came from the same server that the browser subscribed to. No registration, no accounts, no API keys from Google/Mozilla/Apple.

---

## The full flow

### Step 0: Generate VAPID keys (one-time)

```python
from pywebpush import webpush
from py_vapid import Vapid

vapid = Vapid()
vapid.generate_keys()
vapid.save_key("vapid_private.pem")
vapid.save_public_key("vapid_public.pem")

# Or as raw bytes for the Push API:
import base64, json
private_key = vapid.private_pem()
public_key = base64.urlsafe_b64encode(
    vapid.public_key.public_bytes_raw()
).rstrip(b"=").decode()
```

For vibecheck, keys are generated on first run and stored in `~/.vibecheck/vapid_keys.json`:
```json
{
  "public_key": "BLn9M...<base64url, ~87 chars>",
  "private_key": "xV2f...<base64url, ~43 chars>"
}
```

The public key is served at `GET /api/push/vapid-key` so the frontend can fetch it.

Implementation notes (vibecheck):
- Storage dir: `~/.vibecheck/`
  - `vapid_keys.json` and `push_subscriptions.json` are written with best-effort `chmod 0600`.
- VAPID contact `sub` claim is configurable via `VIBECHECK_VAPID_SUB` (defaults to `mailto:vibecheck@localhost`).
- Dead subscriptions are pruned automatically when the push service returns `404/410`.

### Step 1: Browser subscribes

```
Phone browser                     Push service (FCM)              Your server
     │                                   │                             │
     │  PushManager.subscribe({          │                             │
     │    userVisibleOnly: true,         │                             │
     │    applicationServerKey: pubKey   │                             │
     │  })                               │                             │
     ├──────────────────────────────────>│                             │
     │                                   │                             │
     │  PushSubscription {               │                             │
     │    endpoint: "https://fcm.../send/abc123",                      │
     │    keys: {                        │                             │
     │      p256dh: "<browser public key>",                            │
     │      auth: "<shared auth secret>"  │                            │
     │    }                              │                             │
     │  }                                │                             │
     │<──────────────────────────────────┤                             │
     │                                   │                             │
     │  POST /api/push/subscribe                                       │
     │    { endpoint, keys: {p256dh, auth} }                           │
     ├─────────────────────────────────────────────────────────────────>│
     │                                   │                        (stores it)
```

The `PushSubscription` object contains:
- **`endpoint`** — a unique URL on the push service for this browser/device combo. You POST to this to send a push.
- **`keys.p256dh`** — the browser's public key for encrypting the payload (ECDH key agreement).
- **`keys.auth`** — a shared secret for additional encryption (128-bit).

The subscription is sent to `POST /api/push/subscribe` and stored server-side.

### Step 2: Server sends a push

When Vibe enters a `waiting_approval` or `waiting_input` state:

```
Your server                       Push service                   Phone
     │                                  │                            │
     │  1. Encrypt payload with         │                            │
     │     p256dh + auth keys           │                            │
     │  2. Sign JWT with VAPID          │                            │
     │     private key                  │                            │
     │  3. POST to endpoint URL         │                            │
     │     Authorization: vapid t=JWT   │                            │
     │     Content-Encoding: aes128gcm  │                            │
     │     Body: <encrypted payload>    │                            │
     ├─────────────────────────────────>│                            │
     │                                  │                            │
     │  201 Created                     │  Wake service worker       │
     │<─────────────────────────────────┤───────────────────────────>│
     │                                  │                            │
     │                                  │                  sw.js 'push' event
     │                                  │                  → showNotification()
```

`pywebpush` handles encryption, JWT signing, and the HTTP POST:

```python
from pywebpush import webpush, WebPushException

try:
    webpush(
        subscription_info={
            "endpoint": sub["endpoint"],
            "keys": {
                "p256dh": sub["keys"]["p256dh"],
                "auth": sub["keys"]["auth"],
            },
        },
        data=json.dumps({
            "type": "approval",
            "title": "Vibe needs approval",
            "body": "bash: npm test",
            "session_id": "abc-123",
            "tool_call_id": "tc-001",
        }),
        vapid_private_key=private_key,
        vapid_claims={"sub": "mailto:admin@vibecheck.shisa.ai"},
    )
except WebPushException as e:
    if e.response and e.response.status_code == 410:
        # Subscription expired — delete it
        remove_subscription(sub["endpoint"])
```

### Step 3: Service worker receives and displays

```javascript
// sw.js
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
      action: null,
    },
    actions: Array.isArray(payload.actions) ? payload.actions : [],
  }

  event.waitUntil(self.registration.showNotification(title, options))
})
```

### Step 4: User taps the notification

```javascript
// sw.js
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const action = event.action || ''
  const url = event.notification?.data?.url || '/'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url && client.url.includes(url)) {
          client.postMessage({ type: 'notification_action', action, url })
          return client.focus()
        }
      }

      const decorated = action ? `${url}${url.includes('?') ? '&' : '?'}action=${encodeURIComponent(action)}` : url
      return self.clients.openWindow(decorated)
    }),
  )
})
```

In vibecheck, the service worker **does not store PSKs or call protected APIs directly**. Instead, it forwards the click/action to the
running app via `postMessage`, or opens the app with `?action=approve|deny`. The app then performs the REST approval call using the
user's stored PSK.

---

## Encryption details (for the curious)

You never implement this — `pywebpush` handles it. But understanding the layers helps with debugging.

| Layer | What | Why |
|-------|------|-----|
| **ECDH key agreement** | Server generates ephemeral keypair, combines with browser's `p256dh` public key to derive a shared secret | Encryption key negotiation without pre-shared secrets |
| **HKDF key derivation** | Shared secret + `auth` secret → content encryption key + nonce | Derives the actual AES key from the ECDH output |
| **AES-128-GCM encryption** | Payload encrypted with derived key | The push service cannot read the notification content |
| **VAPID JWT** | `Authorization: vapid t=<JWT>, k=<public_key>` | Push service verifies the sender's identity |

The `Content-Encoding: aes128gcm` header tells the push service the payload is encrypted. The push service stores and forwards the opaque blob — it never sees the plaintext.

---

## What vibecheck pushes and when

Defined in WU-19 and WU-22 (smart notifications with Ministral):

| Trigger | Priority | `requireInteraction` | Intensity threshold |
|---------|----------|---------------------|-------------------|
| `waiting_approval` — tool call needs approval | High | `true` | Always |
| `waiting_input` — agent has a question | High | `true` | Always |
| `error` — tool result error | Normal | `false` | Always |
| `idle` — waiting too long for you (escalation) | Low | `false` | Level 3+ (no UI/API yet) |

Approval and input pushes are **never suppressed by snooze** — they're agent-blocking.

---

## Platform support and caveats

### Android Chrome (primary target)

- Full Web Push support, works without PWA install
- Notification actions (Approve/Deny buttons) work
- `requireInteraction: true` keeps the notification visible until user acts
- Badge icon shown in status bar

### iOS Safari 16.4+ (secondary target)

- **Must be added to Home Screen first** — Push API is only available in standalone PWA mode
- User must grant notification permission via a user-gesture-triggered prompt
- Notification actions are **not supported** — tapping opens the app (no inline Approve/Deny)
- `requireInteraction` is ignored — notifications auto-dismiss after ~4 seconds
- Badge API not supported
- Push works while app is backgrounded but may be throttled by iOS

### Desktop Chrome/Firefox/Edge (dev testing)

- Full support, useful for testing the flow without a phone

### What doesn't work

- iOS Safari in-browser (not added to Home Screen) — no Push API at all
- Firefox on Android — Push works but action buttons may not display
- Incognito/private browsing — Push API generally unavailable

---

## Subscription lifecycle

```
    ┌─────────────┐
    │  No         │
    │  Permission │
    └──────┬──────┘
           │ Notification.requestPermission() → "granted"
           ▼
    ┌─────────────┐
    │  Permitted  │
    │  (no sub)   │
    └──────┬──────┘
           │ PushManager.subscribe(vapidPublicKey)
           ▼
    ┌─────────────┐
    │  Subscribed │◄──── Normal state. Server can push.
    └──────┬──────┘
           │
           ├── User clears browser data → subscription gone, server gets 410
           ├── User uninstalls PWA → subscription gone
           ├── Subscription expires (TTL varies by push service) → server gets 410
           └── User revokes permission → PushManager.subscribe() rejects
```

**Key rule:** if a push returns HTTP 404 or 410, delete that subscription server-side. The endpoint is dead.

Subscriptions are stored in `~/.vibecheck/push_subscriptions.json`:
```json
[
  {
    "endpoint": "https://fcm.googleapis.com/fcm/send/abc...",
    "keys": {
      "p256dh": "BLn9M...",
      "auth": "xV2f..."
    },
    "created_at": "2026-02-28T12:00:00Z"
  }
]
```

---

## Testing push locally

### Prototype (WU-05)

The standalone prototype at `prototypes/push-notifications/` tests the full flow without the vibecheck backend:

```bash
cd prototypes/push-notifications
python server.py           # starts on :8080
# Open http://localhost:8080 on phone (or use Vite proxy)
# Click "Request Permission" → "Subscribe" → "Send Test Push"
```

### Integration testing

Against the running vibecheck server:

```bash
# 1. Get VAPID public key
curl -H "X-PSK: $VIBECHECK_PSK" https://vibecheck.shisa.ai/api/push/vapid-key

# 2. Subscribe (with a subscription object from the browser)
curl -X POST -H "X-PSK: $VIBECHECK_PSK" -H "Content-Type: application/json" \
  -d '{"endpoint":"https://fcm.../abc","keys":{"p256dh":"...","auth":"..."}}' \
  https://vibecheck.shisa.ai/api/push/subscribe

# 3. Trigger an approval (run a tool call in Vibe) → phone should buzz
```

### Unit tests (WU-19)

Tests mock `pywebpush.webpush` and verify:
- Push is sent when bridge enters `waiting_approval`
- Push is sent when bridge enters `waiting_input`
- Subscribe/unsubscribe endpoints store/remove subscriptions
- Expired subscriptions (410 response) are cleaned up
- Intensity filtering: chill level suppresses progress but not approval

---

## Key code paths in vibecheck

| File | Responsibility |
|------|---------------|
| `vibecheck/routes/push.py` | `GET /api/push/vapid-key`, `POST /api/push/subscribe`, `POST /api/push/unsubscribe` |
| `vibecheck/notifications/manager.py` | IntensityManager — decides whether to push based on event type and intensity level |
| `vibecheck/notifications/ministral.py` | Generates human-friendly notification copy via Ministral 8B |
| `vibecheck/frontend/public/sw.js` | Service worker: `push` and `notificationclick` handlers |
| `vibecheck/frontend/src/lib/push.js` | Subscribe/unsubscribe logic, VAPID key fetch |
| `~/.vibecheck/vapid_keys.json` | Persisted VAPID keypair |
| `~/.vibecheck/push_subscriptions.json` | Persisted subscription list |

---

## Common pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| SW registered from wrong scope | `subscribe()` silently fails or returns null | Register SW from `/sw.js` (root scope), not `/static/sw.js` |
| VAPID public key format wrong | `InvalidCharacterError` on subscribe | Must be base64url without padding (no `=`), decoded to `Uint8Array` |
| `userVisibleOnly: false` | Chrome rejects the subscribe | Always set `userVisibleOnly: true` — Chrome requires it |
| Push payload too large | Push service rejects (413) | Keep payload under 4 KB. Send minimal data, fetch details from server |
| HTTPS required | Push API not available | Use `localhost` for dev (exempt) or deploy with TLS. Vite proxy works. |
| iOS not on Home Screen | `PushManager` is undefined | Detect and show "Add to Home Screen" prompt |
| Subscription endpoint 410 | `WebPushException` with 410 status | Delete the subscription, it's dead |
| Notification permission denied | `Notification.permission === "denied"` | Can't re-prompt. User must manually re-enable in browser settings. |

---

## Useful references

- [Web Push Protocol (RFC 8030)](https://datatracker.ietf.org/doc/html/rfc8030)
- [VAPID spec (RFC 8292)](https://datatracker.ietf.org/doc/html/rfc8292)
- [Message Encryption for Web Push (RFC 8291)](https://datatracker.ietf.org/doc/html/rfc8291)
- [pywebpush docs](https://github.com/web-push-libs/pywebpush)
- [MDN: Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [MDN: Notification API](https://developer.mozilla.org/en-US/docs/Web/API/Notification)
- [web.dev: Push notifications overview](https://web.dev/articles/push-notifications-overview)
- [Apple: Web Push for Safari](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)
