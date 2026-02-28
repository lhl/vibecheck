import { fireEvent, render, screen, waitFor } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ChatMessage from './ChatMessage.svelte'

describe('ChatMessage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

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

  it('toggles translation and caches per event id', async () => {
    const fetchSpy = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ translated_text: 'こんにちは', source_lang: 'auto', target_lang: 'ja' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    vi.stubGlobal('fetch', fetchSpy)

    render(ChatMessage, {
      event: { id: 'a-translate-1', type: 'assistant', content: 'Hello', timestamp: 1700000000 },
      psk: 'dev-psk',
    })

    await fireEvent.click(screen.getByRole('button', { name: 'Translate' }))
    await waitFor(() => {
      expect(screen.getByText('こんにちは')).toBeInTheDocument()
    })
    expect(fetchSpy).toHaveBeenCalledTimes(1)

    await fireEvent.click(screen.getByRole('button', { name: 'Show original' }))
    expect(screen.getByText('Hello')).toBeInTheDocument()

    await fireEvent.click(screen.getByRole('button', { name: 'Translate' }))
    await waitFor(() => {
      expect(screen.getByText('こんにちは')).toBeInTheDocument()
    })
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('auto-translates assistant messages when enabled', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ translated_text: 'はい', source_lang: 'auto', target_lang: 'ja' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
      ),
    )

    render(ChatMessage, {
      event: { id: 'a-auto-1', type: 'assistant', content: 'Yes', timestamp: 1700000000 },
      psk: 'dev-psk',
      autoTranslate: true,
    })

    await waitFor(() => {
      expect(screen.getByText('はい')).toBeInTheDocument()
    })
  })

  it('skips translation toggles when content is already CJK-heavy', () => {
    render(ChatMessage, {
      event: { id: 'a-cjk-1', type: 'assistant', content: 'こんにちは', timestamp: 1700000000 },
      psk: 'dev-psk',
    })

    expect(screen.queryByRole('button', { name: 'Translate' })).not.toBeInTheDocument()
  })
})
