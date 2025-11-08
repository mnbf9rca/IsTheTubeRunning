import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DestinationButton } from './DestinationButton'

describe('DestinationButton', () => {
  it('renders with correct text', () => {
    render(<DestinationButton onClick={vi.fn()} />)

    expect(screen.getByRole('button', { name: /Mark this as my destination/i })).toBeInTheDocument()
    expect(screen.getByText('This is my destination')).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()

    render(<DestinationButton onClick={handleClick} />)

    const button = screen.getByRole('button', {
      name: /Mark this as my destination/i,
    })
    await user.click(button)

    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when disabled prop is true', () => {
    render(<DestinationButton onClick={vi.fn()} disabled={true} />)

    const button = screen.getByRole('button', {
      name: /Mark this as my destination/i,
    })
    expect(button).toBeDisabled()
  })

  it('is not disabled by default', () => {
    render(<DestinationButton onClick={vi.fn()} />)

    const button = screen.getByRole('button', {
      name: /Mark this as my destination/i,
    })
    expect(button).not.toBeDisabled()
  })

  it('includes check icon', () => {
    render(<DestinationButton onClick={vi.fn()} />)

    const button = screen.getByRole('button', {
      name: /Mark this as my destination/i,
    })
    const icon = button.querySelector('svg')
    expect(icon).toBeInTheDocument()
  })

  it('does not call onClick when disabled and clicked', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()

    render(<DestinationButton onClick={handleClick} disabled={true} />)

    const button = screen.getByRole('button', {
      name: /Mark this as my destination/i,
    })
    await user.click(button)

    expect(handleClick).not.toHaveBeenCalled()
  })
})
