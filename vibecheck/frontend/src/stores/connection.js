import { writable } from 'svelte/store'

export const CONNECTION_STATES = {
  CONNECTED: 'connected',
  CONNECTING: 'connecting',
  DISCONNECTED: 'disconnected',
}

const INITIAL_CONNECTION = {
  status: CONNECTION_STATES.DISCONNECTED,
  reconnectAttempts: 0,
}

export const connection = writable({ ...INITIAL_CONNECTION })

export function setConnection(status, reconnectAttempts = 0) {
  connection.set({ status, reconnectAttempts })
}

export function resetConnection() {
  connection.set({ ...INITIAL_CONNECTION })
}
