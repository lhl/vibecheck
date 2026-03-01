import { fireEvent, render, screen } from '@testing-library/svelte'
import { describe, expect, it, vi } from 'vitest'
import StatusLine from './StatusLine.svelte'

describe('StatusLine', () => {
  it('renders agent state and cost placeholder', () => {
    render(StatusLine, {
      props: {
        agentState: 'idle',
        sessionError: '',
        onSettingsToggle: vi.fn(),
        settingsOpen: false,
        costDisplay: '--',
      },
    })

    expect(screen.getByText('idle')).toBeInTheDocument()
    expect(screen.getByText('--')).toBeInTheDocument()
  })

  it('shows error hint when sessionError is present', () => {
    render(StatusLine, {
      props: {
        agentState: 'idle',
        sessionError: 'Connection lost',
        onSettingsToggle: vi.fn(),
        settingsOpen: false,
      },
    })

    expect(screen.getByText('!')).toBeInTheDocument()
  })

  it('calls onSettingsToggle when clicked', async () => {
    const toggle = vi.fn()
    render(StatusLine, {
      props: {
        agentState: 'running',
        sessionError: '',
        onSettingsToggle: toggle,
        settingsOpen: false,
      },
    })

    await fireEvent.click(screen.getByTestId('status-line'))
    expect(toggle).toHaveBeenCalledTimes(1)
  })

  it('formats state label with spaces instead of underscores', () => {
    render(StatusLine, {
      props: {
        agentState: 'waiting_approval',
        sessionError: '',
        onSettingsToggle: vi.fn(),
        settingsOpen: false,
      },
    })

    expect(screen.getByText('waiting approval')).toBeInTheDocument()
  })

  it('renders a high-visibility yolo marker when enabled', () => {
    render(StatusLine, {
      props: {
        agentState: 'running',
        sessionError: '',
        onSettingsToggle: vi.fn(),
        settingsOpen: false,
        yoloEnabled: true,
      },
    })

    const line = screen.getByTestId('status-line')
    expect(line).toHaveClass('yolo-active')
    expect(screen.getByText('YOLO')).toBeInTheDocument()
  })
})
