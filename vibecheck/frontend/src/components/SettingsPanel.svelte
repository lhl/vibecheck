<script>
  import { createEventDispatcher } from 'svelte'

  export let voiceLanguage = 'ja'
  export let autoTranslateEnabled = false
  export let notificationsEnabled = false
  export let pushSupported = false
  export let notificationsBusy = false
  export let notificationsError = ''
  export let theme = 'auto'

  const dispatch = createEventDispatcher()

  function handleVoiceChange(event) {
    dispatch('voiceLanguageChange', { value: event.currentTarget.value })
  }

  function toggleTranslate() {
    dispatch('toggleTranslate')
  }

  function toggleNotifications() {
    dispatch('toggleNotifications')
  }

  function cycleTheme() {
    dispatch('cycleTheme')
  }

  function forgetKey() {
    dispatch('forgetKey')
  }
</script>

<div class="settings-panel">
  <label for="voice-lang">Voice language</label>
  <select id="voice-lang" value={voiceLanguage} on:change={handleVoiceChange}>
    <option value="ja">JA</option>
    <option value="en">EN</option>
  </select>

  <label for="translate-toggle">Auto-translate</label>
  <button id="translate-toggle" type="button" class="secondary" on:click={toggleTranslate}>
    {autoTranslateEnabled ? 'Disable auto-translate' : 'Enable auto-translate'}
  </button>

  <label for="theme-toggle">Theme</label>
  <button id="theme-toggle" type="button" class="secondary" on:click={cycleTheme}>
    Theme: {theme}
  </button>

  <label for="notify-toggle">Notifications</label>
  <button
    id="notify-toggle"
    type="button"
    class="secondary"
    disabled={!pushSupported || notificationsBusy}
    on:click={toggleNotifications}
  >
    {notificationsEnabled ? 'Disable notifications' : 'Enable notifications'}
  </button>
  {#if !pushSupported}
    <p class="meta">Push not supported in this browser.</p>
  {/if}
  {#if notificationsError}
    <p class="error">{notificationsError}</p>
  {/if}

  <button type="button" class="danger" on:click={forgetKey}>Forget Key</button>
</div>

<style>
  .settings-panel {
    padding: 0.6rem;
    display: grid;
    gap: 0.45rem;
  }

  label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--label);
  }

  select,
  button {
    font: inherit;
  }

  select {
    min-height: 40px;
    border-radius: 2px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    color: var(--input-fg);
    padding: 0 0.7rem;
  }

  button {
    min-height: 40px;
    border-radius: 2px;
    border: 1px solid var(--primary-border);
    background: var(--primary-bg);
    color: var(--primary-fg);
    font-weight: 700;
  }

  button.secondary {
    border-color: var(--secondary-border);
    background: var(--secondary-bg);
    color: var(--secondary-fg);
  }

  button.danger {
    border-color: var(--danger-border);
    background: var(--danger-bg);
    color: var(--danger-fg);
  }

  button:disabled {
    opacity: 0.58;
  }

  .meta,
  .error {
    margin: 0;
    font-size: 0.76rem;
  }

  .meta {
    color: var(--meta);
  }

  .error {
    color: var(--error);
  }
</style>
