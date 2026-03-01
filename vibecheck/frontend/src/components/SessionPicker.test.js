import { fireEvent, render, screen } from '@testing-library/svelte'
import { describe, expect, it, vi } from 'vitest'
import SessionPicker from './SessionPicker.svelte'

const activeSessions = [
  {
    id: 's-1',
    status: 'running',
    last_activity: '2026-02-28T00:00:00Z',
    message_count: 3,
    title: 'First session',
    controllable: true,
  },
]

const olderSessions = [
  {
    id: 's-old',
    status: 'disconnected',
    last_activity: '2026-02-27T00:00:00Z',
    message_count: 1,
    title: 'Old session',
    controllable: false,
  },
]

describe('SessionPicker', () => {
  it('is hidden when open is false', () => {
    const { container } = render(SessionPicker, {
      props: {
        sessions: [],
        activeSessions: [],
        olderSessions: [],
        sessionId: '',
        sessionsLoading: false,
        sessionError: '',
        resumeBusy: '',
        open: false,
      },
    })

    const picker = container.querySelector('.session-picker')
    expect(picker).not.toHaveClass('open')
  })

  it('shows active sessions when open', () => {
    render(SessionPicker, {
      props: {
        sessions: activeSessions,
        activeSessions,
        olderSessions: [],
        sessionId: 's-1',
        sessionsLoading: false,
        sessionError: '',
        resumeBusy: '',
        open: true,
      },
    })

    expect(screen.getByText('First session')).toBeInTheDocument()
  })

  it('calls onSwitchSession when a session is clicked', async () => {
    const switchFn = vi.fn()
    render(SessionPicker, {
      props: {
        sessions: activeSessions,
        activeSessions,
        olderSessions: [],
        sessionId: '',
        sessionsLoading: false,
        sessionError: '',
        resumeBusy: '',
        open: true,
        onSwitchSession: switchFn,
      },
    })

    await fireEvent.click(screen.getByText('First session'))
    expect(switchFn).toHaveBeenCalledWith('s-1')
  })

  it('shows session error when present', () => {
    render(SessionPicker, {
      props: {
        sessions: [],
        activeSessions: [],
        olderSessions: [],
        sessionId: '',
        sessionsLoading: false,
        sessionError: 'Network error',
        resumeBusy: '',
        open: true,
      },
    })

    expect(screen.getByText('Network error')).toBeInTheDocument()
  })
})
