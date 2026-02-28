<script>
  import { onDestroy } from 'svelte'
  import { renderBasicMarkdown } from '../lib/markdown'
  import { getCachedTranslation, setCachedTranslation, shouldSkipTranslation } from '../lib/translate'

  export let event
  export let psk = ''
  export let autoTranslate = false

  $: roleClass = event?.type === 'user_message' ? 'user' : 'assistant'
  $: originalText = event?.content || ''
  $: canTranslate = Boolean(event?.id && originalText && !shouldSkipTranslation(originalText))
  $: body = renderBasicMarkdown(showTranslated && translatedText ? translatedText : originalText)
  $: timestamp = Number.isFinite(event?.timestamp)
    ? new Date(event.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''

  let showTranslated = false
  let translatedText = ''
  let isTranslating = false
  let translateError = ''
  let destroyed = false
  let abortController = null

  async function ensureTranslated() {
    if (!event?.id || !originalText) {
      return ''
    }

    const cached = getCachedTranslation(event.id)
    if (cached) {
      if (!destroyed) {
        translatedText = cached
      }
      return cached
    }

    if (!psk) {
      throw new Error('Missing PSK.')
    }

    if (abortController) {
      try {
        abortController.abort()
      } catch {
        // no-op
      }
    }
    abortController = new AbortController()

    const response = await fetch('/api/translate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-PSK': psk,
      },
      body: JSON.stringify({ text: originalText, target_lang: 'ja' }),
      signal: abortController.signal,
    })

    if (!response.ok) {
      let detail = ''
      try {
        const errBody = await response.json()
        detail = typeof errBody?.detail === 'string' ? errBody.detail : ''
      } catch {
        // no-op
      }
      throw new Error(
        detail
          ? `${response.status} ${detail}`
          : `${response.status} ${response.statusText}`.trim(),
      )
    }

    const payload = await response.json()
    const text = typeof payload?.translated_text === 'string' ? payload.translated_text.trim() : ''
    if (!text) {
      throw new Error('Translation returned empty text.')
    }

    setCachedTranslation(event.id, text)
    if (!destroyed) {
      translatedText = text
    }
    return text
  }

  async function toggleTranslate() {
    if (!canTranslate || isTranslating) {
      return
    }

    translateError = ''

    if (showTranslated) {
      showTranslated = false
      return
    }

    isTranslating = true
    try {
      await ensureTranslated()
      if (!destroyed) {
        showTranslated = true
      }
    } catch (error) {
      if (!destroyed) {
        translateError = error instanceof Error ? error.message : 'Translation failed'
      }
    } finally {
      if (!destroyed) {
        isTranslating = false
      }
    }
  }

  $: if (
    autoTranslate &&
    roleClass === 'assistant' &&
    canTranslate &&
    !showTranslated &&
    !translatedText &&
    !isTranslating &&
    !translateError &&
    !destroyed
  ) {
    isTranslating = true
    ensureTranslated()
      .then(() => {
        if (!destroyed) {
          showTranslated = true
        }
      })
      .catch((error) => {
        if (!destroyed) {
          translateError = error instanceof Error ? error.message : 'Translation failed'
        }
      })
      .finally(() => {
        if (!destroyed) {
          isTranslating = false
        }
      })
  }

  onDestroy(() => {
    destroyed = true
    if (abortController) {
      try {
        abortController.abort()
      } catch {
        // no-op
      }
      abortController = null
    }
  })
</script>

<article data-testid="chat-message" class="chat-message {roleClass}">
  <p class="message-body">{@html body}</p>
  <div class="meta">
    {#if canTranslate}
      <button
        type="button"
        class="translate"
        aria-label={showTranslated ? 'Show original' : 'Translate'}
        disabled={isTranslating}
        on:click={toggleTranslate}
      >
        🌐
      </button>
    {/if}
    {#if timestamp}
      <p class="timestamp">{timestamp}</p>
    {/if}
  </div>
  {#if translateError}
    <p class="translate-error">{translateError}</p>
  {/if}
</article>

<style>
  .chat-message {
    max-width: min(85%, 30rem);
    border-radius: 14px;
    padding: 0.7rem 0.85rem;
    display: grid;
    gap: 0.35rem;
  }

  .chat-message.assistant {
    justify-self: start;
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    color: var(--fg);
  }

  .chat-message.user {
    justify-self: end;
    background: var(--primary-bg);
    border: 1px solid var(--primary-border);
    color: var(--primary-fg);
  }

  .message-body {
    margin: 0;
    line-height: 1.4;
    font-size: 0.92rem;
    word-break: break-word;
  }

  .message-body :global(pre) {
    margin: 0;
    background: var(--input-bg);
    border: 1px solid var(--input-border);
    border-radius: 10px;
    padding: 0.55rem;
    overflow-x: auto;
  }

  .message-body :global(code) {
    font-family: 'IBM Plex Mono', 'Fira Code', monospace;
    font-size: 0.83rem;
  }

  .message-body :global(a) {
    color: var(--session-selected);
  }

  .timestamp {
    margin: 0;
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  .meta {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 0.4rem;
  }

  .translate {
    border: 1px solid var(--card-border);
    background: transparent;
    color: inherit;
    border-radius: 999px;
    width: 34px;
    height: 28px;
    display: grid;
    place-items: center;
    font-size: 0.95rem;
  }

  .translate:disabled {
    opacity: 0.55;
  }

  .translate-error {
    margin: 0;
    font-size: 0.72rem;
    color: var(--error);
  }
</style>
