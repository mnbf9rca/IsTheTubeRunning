import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { NotificationMethodBadge } from './NotificationMethodBadge'

describe('NotificationMethodBadge', () => {
  describe('rendering', () => {
    it('should render "Email" badge for email method', () => {
      render(<NotificationMethodBadge method="email" />)
      expect(screen.getByText('Email')).toBeInTheDocument()
    })

    it('should render "SMS" badge for sms method', () => {
      render(<NotificationMethodBadge method="sms" />)
      expect(screen.getByText('SMS')).toBeInTheDocument()
    })
  })
})
