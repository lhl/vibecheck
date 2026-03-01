import { render, screen } from '@testing-library/svelte'
import { describe, expect, it } from 'vitest'
import SettingsPanel from './SettingsPanel.svelte'

describe('SettingsPanel', () => {
  it('shows YOLO toggle copy and button', () => {
    render(SettingsPanel, {
      props: {
        yoloEnabled: false,
      },
    })

    const button = screen.getByRole('button', { name: 'Enable YOLO mode' })
    expect(button).toBeInTheDocument()
    expect(button).toHaveClass('yolo-toggle')
    expect(screen.getByText('YOLO mode')).toBeInTheDocument()
  })

  it('shows disable copy when YOLO is already enabled', () => {
    render(SettingsPanel, {
      props: {
        yoloEnabled: true,
      },
    })

    expect(screen.getByRole('button', { name: 'Disable YOLO mode' })).toBeInTheDocument()
  })
})
