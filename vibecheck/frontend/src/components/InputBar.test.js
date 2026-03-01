import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InputBar from './InputBar.svelte'

function createDeferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

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

  it('shows only the camera control while the message input is focused', async () => {
    render(InputBar, {
      sessionId: 's-1',
      psk: 'dev-psk',
      pendingInput: null,
      connectionStatus: 'connected',
    })

    const textbox = screen.getByRole('textbox', { name: 'Message input' })
    expect(screen.queryByRole('button', { name: 'Take photo' })).not.toBeInTheDocument()

    await fireEvent.focus(textbox)
    expect(screen.getByRole('button', { name: 'Take photo' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Upload image' })).not.toBeInTheDocument()

    await fireEvent.blur(textbox)
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Take photo' })).not.toBeInTheDocument()
    })
  })

  it('shows camera processing states and appends attached image caption at send time', async () => {
    const visionDeferred = createDeferred()
    vi.stubGlobal(
      'fetch',
      vi.fn((resource, options = {}) => {
        if (resource === '/api/vision') {
          return visionDeferred.promise
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

    const cameraInput = screen.getByTestId('take-photo-input')
    const clickSpy = vi.spyOn(cameraInput, 'click')

    await fireEvent.click(screen.getByRole('button', { name: 'Take photo' }))
    expect(clickSpy).toHaveBeenCalledTimes(1)

    const selectedFile = new File([new Uint8Array([255, 216, 255, 224])], 'photo.jpg', {
      type: 'image/jpeg',
    })
    await fireEvent.change(cameraInput, { target: { files: [selectedFile] } })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/vision', expect.any(Object))
    })
    expect(screen.getByTestId('camera-spinner')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Processing image' })).toHaveAttribute('data-state', 'processing')

    visionDeferred.resolve(
      new Response(JSON.stringify({ text: 'A notebook and a cup of coffee.' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Attached image ready' })).toHaveAttribute('data-state', 'ready')
    })
    expect(screen.queryByTestId('camera-spinner')).not.toBeInTheDocument()
    expect(textbox).toHaveValue('')

    const visionCall = fetch.mock.calls.find(([resource]) => resource === '/api/vision')
    expect(visionCall).toBeTruthy()
    const [, visionOptions] = visionCall
    expect(visionOptions.method).toBe('POST')
    expect(visionOptions.headers['X-PSK']).toBe('dev-psk')
    expect(visionOptions.body).toBeInstanceOf(FormData)
    expect(visionOptions.body.get('image').name).toBe('photo.jpg')

    await fireEvent.input(textbox, { target: { value: 'please summarize this' } })
    await fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    const sendCall = fetch.mock.calls.find(([resource]) => resource === '/api/sessions/s-1/message')
    expect(sendCall).toBeTruthy()
    const [, sendOptions] = sendCall
    const payload = JSON.parse(sendOptions.body)
    expect(payload.content).toContain('please summarize this')
    expect(payload.content).toContain('ATTACHED IMAGE:')
    expect(payload.content).toContain('A notebook and a cup of coffee.')
  })
})
