import { render, screen } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'
import ChatMessage from './ChatMessage.svelte'

describe('ChatMessage', () => {
  it('renders assistant bubble and markdown formatting', () => {
    render(ChatMessage, {
      event: {
        id: 'a-1',
        type: 'assistant',
        content: '**bold** and `inline` and [link](https://example.com)',
        timestamp: 1700000000,
      },
    })

    expect(screen.getByText('bold')).toBeInTheDocument()
    expect(screen.getByText('inline')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'link' })).toHaveAttribute('href', 'https://example.com')
    expect(screen.getByTestId('chat-message')).toHaveClass('assistant')
  })

  it('renders user bubble alignment and code block', () => {
    render(ChatMessage, {
      event: {
        id: 'u-1',
        type: 'user_message',
        content: '```\nconst ok = true\n```',
        timestamp: 1700000000,
      },
    })

    expect(screen.getByText('const ok = true')).toBeInTheDocument()
    expect(screen.getByTestId('chat-message')).toHaveClass('user')
  })
})
