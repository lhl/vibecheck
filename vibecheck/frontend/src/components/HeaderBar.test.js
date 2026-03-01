import { fireEvent, render, screen } from '@testing-library/svelte'
import { describe, expect, it, vi } from 'vitest'
import HeaderBar from './HeaderBar.svelte'

describe('HeaderBar', () => {
  it('renders logo, session title, and connection status', () => {
    render(HeaderBar, {
      props: {
        connectionStatus: 'connected',
        reconnectAttempts: 0,
        activeSessionTitle: 'My session',
        pickerOpen: false,
        onTogglePicker: vi.fn(),
      },
    })

    expect(screen.getByText('vibecheck')).toBeInTheDocument()
    expect(screen.getByText('My session')).toBeInTheDocument()
    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('shows No session when activeSessionTitle is empty', () => {
    render(HeaderBar, {
      props: {
        connectionStatus: 'disconnected',
        reconnectAttempts: 0,
        activeSessionTitle: '',
        pickerOpen: false,
        onTogglePicker: vi.fn(),
      },
    })

    expect(screen.getByText('No session')).toBeInTheDocument()
  })

  it('calls onTogglePicker when clicked', async () => {
    const toggle = vi.fn()
    render(HeaderBar, {
      props: {
        connectionStatus: 'disconnected',
        reconnectAttempts: 0,
        activeSessionTitle: '',
        pickerOpen: false,
        onTogglePicker: toggle,
      },
    })

    await fireEvent.click(screen.getByText('vibecheck'))
    expect(toggle).toHaveBeenCalledTimes(1)
  })
})
