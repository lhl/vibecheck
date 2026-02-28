import { describe, expect, it } from 'vitest'
import { __test__ } from './push'

describe('push', () => {
  it('decodes base64url VAPID keys into a Uint8Array', () => {
    const bytes = __test__.urlBase64ToUint8Array('SGVsbG8')
    const text = new TextDecoder().decode(bytes)
    expect(text).toBe('Hello')
  })
})

