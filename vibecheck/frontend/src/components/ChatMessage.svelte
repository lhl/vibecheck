<script>
  import { onDestroy } from 'svelte'
  import { renderBasicMarkdown } from '../lib/markdown'
  import { getCachedTranslation, setCachedTranslation, shouldSkipTranslation } from '../lib/translate'

  export let event
  export let psk = ''
  export let autoTranslate = false
  export let targetLanguage = 'ja'

  $: roleClass = event?.type === 'user_message' ? 'user' : 'assistant'
  $: originalText = event?.content || ''
  $: targetLanguageCode = targetLanguage === 'en' ? 'en' : 'ja'
  $: translationCacheKey = event?.id ? `${event.id}:${targetLanguageCode}` : ''
  $: canTranslate = Boolean(
    event?.id &&
      originalText &&
      !(targetLanguageCode === 'ja' && shouldSkipTranslation(originalText)),
  )
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
  let previousTargetLanguage = targetLanguageCode

  $: if (targetLanguageCode !== previousTargetLanguage) {
    previousTargetLanguage = targetLanguageCode
    showTranslated = false
    translatedText = ''
    translateError = ''
    if (abortController) {
      try {
        abortController.abort()
      } catch {
        // no-op
      }
      abortController = null
    }
    isTranslating = false
  }

  async function ensureTranslated() {
    if (!event?.id || !originalText) {
      return ''
    }

    const cached = getCachedTranslation(translationCacheKey)
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
      body: JSON.stringify({ text: originalText, target_lang: targetLanguageCode }),
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

    setCachedTranslation(translationCacheKey, text)
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

<!-- svelte-ignore a11y-no-noninteractive-tabindex -->
<article
  data-testid="chat-message"
  class="chat-message {roleClass}"
  class:translatable={canTranslate}
  role={canTranslate ? 'button' : undefined}
  tabindex={canTranslate ? 0 : undefined}
  aria-label={canTranslate ? (showTranslated ? 'Show original' : 'Translate') : undefined}
  on:click={canTranslate ? toggleTranslate : undefined}
  on:keydown={canTranslate ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleTranslate(); } } : undefined}
>
  <p class="message-body">{@html body}</p>
  <div class="meta">
    {#if isTranslating}
      <span class="translating-indicator">translating…</span>
    {:else if showTranslated}
      <span class="translated-badge">🌐</span>
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
    max-width: 100%;
    min-width: 0;
    border-radius: 0;
    padding: 0.7rem 0.85rem;
    display: grid;
    gap: 0.35rem;
  }

  .chat-message.assistant {
    justify-self: start;
    background: transparent;
    border: none;
    color: var(--fg);
  }

  .chat-message.user {
    justify-self: start;
    background: transparent;
    border: none;
    border-left: 3px solid #EF7D31;
    color: var(--fg);
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
    border-radius: 2px;
    padding: 0.55rem;
    overflow-x: auto;
  }

  .message-body :global(code) {
    font-family: 'JetBrains Mono', monospace;
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

  .chat-message.translatable {
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }

  .chat-message.translatable:active {
    opacity: 0.75;
  }

  .translating-indicator {
    font-size: 0.7rem;
    color: var(--text-muted);
    font-style: italic;
  }

  .translated-badge {
    font-size: 0.7rem;
    opacity: 0.6;
  }

  .translate-error {
    margin: 0;
    font-size: 0.72rem;
    color: var(--error);
  }
</style>
