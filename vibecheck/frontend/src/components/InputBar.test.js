import { fireEvent, render, screen } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InputBar from './InputBar.svelte'

describe('InputBar', () => {
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

  it('sends message payload when there is no pending input', async () => {
    render(InputBar, {
      sessionId: 's-1',
      psk: 'dev-psk',
      pendingInput: null,
      connectionStatus: 'connected',
    })

    const textbox = screen.getByRole('textbox')
    await fireEvent.input(textbox, { target: { value: 'hello world' } })
    await fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(fetch).toHaveBeenCalledWith('/api/sessions/s-1/message', expect.any(Object))
  })

  it('sends input resolution when pending input exists', async () => {
    render(InputBar, {
      sessionId: 's-1',
      psk: 'dev-psk',
      pendingInput: {
        request_id: 'req-1',
        question: 'Pick one',
      },
      connectionStatus: 'connected',
    })

    const textbox = screen.getByRole('textbox')
    await fireEvent.input(textbox, { target: { value: 'option-a' } })
    await fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(fetch).toHaveBeenCalledWith('/api/sessions/s-1/input', expect.any(Object))
    expect(textbox).toHaveAttribute('placeholder', 'Answer the question...')
  })

  it('supports enter-to-send and shift-enter for newline', async () => {
    render(InputBar, {
      sessionId: 's-1',
      psk: 'dev-psk',
      pendingInput: null,
      connectionStatus: 'connected',
    })

    const textbox = screen.getByRole('textbox')
    await fireEvent.input(textbox, { target: { value: 'line' } })

    await fireEvent.keyDown(textbox, { key: 'Enter', shiftKey: true })
    expect(fetch).not.toHaveBeenCalled()

    await fireEvent.keyDown(textbox, { key: 'Enter', shiftKey: false })
    expect(fetch).toHaveBeenCalledWith('/api/sessions/s-1/message', expect.any(Object))
  })

  it('disables controls when disconnected', () => {
    render(InputBar, {
      sessionId: 's-1',
      psk: 'dev-psk',
      pendingInput: null,
      connectionStatus: 'disconnected',
    })

    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
  })
})
