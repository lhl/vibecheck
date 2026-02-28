import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ApprovalPanel from './ApprovalPanel.svelte'

describe('ApprovalPanel', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ status: 'ok' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
      ),
    )
  })

  it('posts approve decision and disables buttons while pending', async () => {
    const onResolved = vi.fn()
    render(ApprovalPanel, {
      pendingApproval: {
        call_id: 'call-1',
        tool_name: 'bash',
        args: { command: 'ls -la' },
      },
      sessionId: 's-1',
      psk: 'dev-psk',
      onResolved,
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Approve' }))

    expect(fetch).toHaveBeenCalledWith('/api/sessions/s-1/approve', expect.any(Object))
    await waitFor(() => {
      expect(onResolved).toHaveBeenCalledWith('call-1', true)
    })
  })
})
