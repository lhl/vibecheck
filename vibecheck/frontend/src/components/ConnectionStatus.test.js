import { render, screen } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'
import ConnectionStatus from './ConnectionStatus.svelte'

describe('ConnectionStatus', () => {
  it('renders connected state with green indicator', () => {
    render(ConnectionStatus, {
      status: 'connected',
      reconnectAttempts: 0,
    })

    expect(screen.getByText('Connected')).toBeInTheDocument()
    expect(screen.getByTestId('connection-dot')).toHaveClass('connected')
  })

  it('shows reconnect attempt count while connecting', () => {
    render(ConnectionStatus, {
      status: 'connecting',
      reconnectAttempts: 3,
    })

    expect(screen.getByText(/Reconnecting/)).toHaveTextContent('Reconnecting (3)')
  })
})
