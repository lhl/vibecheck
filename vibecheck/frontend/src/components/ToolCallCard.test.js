import { fireEvent, render, screen } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'
import ToolCallCard from './ToolCallCard.svelte'

describe('ToolCallCard', () => {
  const call = {
    id: 'tc-event-1',
    type: 'tool_call',
    call_id: 'call-1',
    tool_name: 'bash',
    args: { command: 'npm test -- -u' },
  }

  it('renders collapsed preview and toggles expanded json view', async () => {
    render(ToolCallCard, { toolCall: call, result: null })

    expect(screen.getByText('bash')).toBeInTheDocument()
    expect(screen.queryByText('"command": "npm test -- -u"')).not.toBeInTheDocument()

    await fireEvent.click(screen.getByRole('button', { name: /bash/i }))
    expect(screen.getAllByText(/"command":\s*"npm test -- -u"/).length).toBeGreaterThan(0)
  })

  it('shows error styling when matching result has is_error=true', () => {
    render(ToolCallCard, {
      toolCall: call,
      result: {
        id: 'tr-1',
        type: 'tool_result',
        call_id: 'call-1',
        output: 'denied',
        is_error: true,
      },
    })

    expect(screen.getByTestId('tool-call-card')).toHaveClass('error')
    expect(screen.getByText('denied')).toBeInTheDocument()
  })
})
