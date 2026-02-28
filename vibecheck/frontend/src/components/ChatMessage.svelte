<script>
  import { renderBasicMarkdown } from '../lib/markdown'

  export let event

  $: roleClass = event?.type === 'user_message' ? 'user' : 'assistant'
  $: body = renderBasicMarkdown(event?.content || '')
  $: timestamp = Number.isFinite(event?.timestamp)
    ? new Date(event.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''
</script>

<article data-testid="chat-message" class="chat-message {roleClass}">
  <p class="message-body">{@html body}</p>
  {#if timestamp}
    <p class="timestamp">{timestamp}</p>
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
    background: linear-gradient(160deg, #26304a, #1a2134);
    border: 1px solid #394866;
    color: #e7edff;
  }

  .chat-message.user {
    justify-self: end;
    background: linear-gradient(160deg, #5c2d07, #8b3f09);
    border: 1px solid #cb6c29;
    color: #ffe5d1;
  }

  .message-body {
    margin: 0;
    line-height: 1.4;
    font-size: 0.92rem;
    word-break: break-word;
  }

  .message-body :global(pre) {
    margin: 0;
    background: rgb(6 10 20 / 0.4);
    border: 1px solid rgb(95 113 150 / 0.5);
    border-radius: 10px;
    padding: 0.55rem;
    overflow-x: auto;
  }

  .message-body :global(code) {
    font-family: 'IBM Plex Mono', 'Fira Code', monospace;
    font-size: 0.83rem;
  }

  .message-body :global(a) {
    color: #9fd9ff;
  }

  .timestamp {
    margin: 0;
    justify-self: end;
    font-size: 0.7rem;
    color: rgb(235 241 255 / 0.64);
  }
</style>
