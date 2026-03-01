import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
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

  it('surfaces request errors without clearing the draft', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: 'network unavailable' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
      ),
    )

    render(InputBar, {
      sessionId: 's-1',
      psk: 'dev-psk',
      pendingInput: null,
      connectionStatus: 'connected',
    })

    const textbox = screen.getByRole('textbox')
    await fireEvent.input(textbox, { target: { value: 'hello world' } })
    await fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => {
      expect(screen.getByText(/503/i)).toBeInTheDocument()
    })
    expect(textbox).toHaveValue('hello world')
  })

  it('shows camera and upload controls only while the message input is focused', async () => {
    render(InputBar, {
      sessionId: 's-1',
      psk: 'dev-psk',
      pendingInput: null,
      connectionStatus: 'connected',
    })

    const textbox = screen.getByRole('textbox', { name: 'Message input' })
    expect(screen.queryByRole('button', { name: 'Take photo' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Upload image' })).not.toBeInTheDocument()

    await fireEvent.focus(textbox)
    expect(screen.getByRole('button', { name: 'Take photo' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upload image' })).toBeInTheDocument()

    await fireEvent.blur(textbox)
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Take photo' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Upload image' })).not.toBeInTheDocument()
    })
  })

  it('wires upload button to hidden image input and sends image to /api/vision', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((resource) => {
        if (resource === '/api/vision') {
          return Promise.resolve(
            new Response(JSON.stringify({ text: 'A notebook and a cup of coffee.' }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          )
        }

        return Promise.resolve(
          new Response(JSON.stringify({ status: 'ok' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }),
    )

    render(InputBar, {
      sessionId: 's-1',
      psk: 'dev-psk',
      pendingInput: null,
      connectionStatus: 'connected',
    })

    const textbox = screen.getByRole('textbox', { name: 'Message input' })
    await fireEvent.focus(textbox)

    const uploadInput = screen.getByTestId('upload-image-input')
    const clickSpy = vi.spyOn(uploadInput, 'click')

    await fireEvent.click(screen.getByRole('button', { name: 'Upload image' }))
    expect(clickSpy).toHaveBeenCalledTimes(1)

    const selectedFile = new File([new Uint8Array([255, 216, 255, 224])], 'photo.jpg', {
      type: 'image/jpeg',
    })
    await fireEvent.change(uploadInput, { target: { files: [selectedFile] } })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/vision', expect.any(Object))
    })

    const visionCall = fetch.mock.calls.find(([resource]) => resource === '/api/vision')
    expect(visionCall).toBeTruthy()
    const [, options] = visionCall
    expect(options.method).toBe('POST')
    expect(options.headers['X-PSK']).toBe('dev-psk')
    expect(options.body).toBeInstanceOf(FormData)
    expect(options.body.get('image').name).toBe('photo.jpg')

    expect(textbox).toHaveValue('Image context: A notebook and a cup of coffee.')
  })
})
