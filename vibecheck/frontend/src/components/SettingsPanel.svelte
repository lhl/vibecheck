<script>
  import { createEventDispatcher } from 'svelte'

  export let voiceLanguage = 'ja'
  export let notificationsEnabled = false
  export let pushSupported = false
  export let notificationsBusy = false
  export let notificationsError = ''
  export let pskDraft = ''

  const dispatch = createEventDispatcher()

  function handleVoiceChange(event) {
    dispatch('voiceLanguageChange', { value: event.currentTarget.value })
  }

  function toggleNotifications() {
    dispatch('toggleNotifications')
  }

  function handlePskDraftInput(event) {
    dispatch('pskDraftChange', { value: event.currentTarget.value })
  }

  function saveKey() {
    dispatch('saveKey')
  }

  function forgetKey() {
    dispatch('forgetKey')
  }
</script>

<div class="settings-panel">
  <label for="voice-lang">Translate language</label>
  <select id="voice-lang" value={voiceLanguage} on:change={handleVoiceChange}>
    <option value="ja">JA / Japanese</option>
    <option value="en">EN / English</option>
  </select>

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

  <section class="psk-section">
    <label for="psk-update">PSK</label>
    <input
      id="psk-update"
      type="password"
      value={pskDraft}
      placeholder="PSK"
      autocomplete="current-password"
      on:input={handlePskDraftInput}
      on:change={saveKey}
    />
    <button type="button" class="danger" hidden on:click={forgetKey}>Forget Key</button>
  </section>
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
  input,
  button {
    font: inherit;
  }

  select,
  input {
    min-height: 44px;
    border-radius: 2px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    color: var(--input-fg);
    padding: 0 0.7rem;
  }

  button {
    min-height: 44px;
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
    min-height: 48px;
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

  .psk-section {
    margin-top: 0.8rem;
    padding-top: 0.8rem;
    border-top: 1px solid var(--card-border);
    display: grid;
    gap: 0.45rem;
  }

</style>
