import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import Dashboard from './Dashboard'
import type { User } from '@auth0/auth0-react'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

// Mock useRoutes hook
vi.mock('@/hooks/useRoutes', () => ({
  useRoutes: vi.fn(),
}))

import { useAuth } from '@/hooks/useAuth'
import { useRoutes } from '@/hooks/useRoutes'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockUseRoutes = useRoutes as ReturnType<typeof vi.fn>

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock for useRoutes
    mockUseRoutes.mockReturnValue({
      routes: [],
      loading: false,
      error: null,
      createRoute: vi.fn(),
      updateRoute: vi.fn(),
      deleteRoute: vi.fn(),
      getRoute: vi.fn(),
      refresh: vi.fn(),
    })
  })

  it('should render welcome message with user first name', () => {
    mockUseAuth.mockReturnValue({
      user: {
        name: 'John Doe',
        email: 'john@example.com',
      } as User,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    expect(screen.getByText(/Welcome back, John!/i)).toBeInTheDocument()
  })

  it('should render welcome message without name when user has no name', () => {
    mockUseAuth.mockReturnValue({
      user: {
        email: 'john@example.com',
      } as User,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    expect(screen.getByText('Welcome back!')).toBeInTheDocument()
  })

  it('should render welcome message when user is null', () => {
    mockUseAuth.mockReturnValue({
      user: null,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    expect(screen.getByText('Welcome back!')).toBeInTheDocument()
  })

  it('should display all stats cards with zero values', () => {
    mockUseAuth.mockReturnValue({
      user: {
        name: 'Test User',
        email: 'test@example.com',
      } as User,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    // Routes card
    expect(screen.getByText('Routes')).toBeInTheDocument()
    expect(screen.getByText('No routes configured yet')).toBeInTheDocument()

    // Contacts card
    expect(screen.getByText('Contacts')).toBeInTheDocument()
    expect(screen.getByText('No contacts added yet')).toBeInTheDocument()

    // Active Alerts card
    expect(screen.getByText('Active Alerts')).toBeInTheDocument()
    expect(screen.getByText('No active alerts')).toBeInTheDocument()
  })

  it('should display Getting Started section with all steps', () => {
    mockUseAuth.mockReturnValue({
      user: {
        name: 'Test User',
        email: 'test@example.com',
      } as User,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    // Getting Started card
    expect(screen.getByText('Getting Started')).toBeInTheDocument()
    expect(screen.getByText('Follow these steps to set up your alert system')).toBeInTheDocument()

    // Step 1
    expect(screen.getByText('Add your contacts')).toBeInTheDocument()
    expect(
      screen.getByText('Add and verify your email addresses and phone numbers to receive alerts')
    ).toBeInTheDocument()

    // Step 2
    expect(screen.getByText('Create your routes')).toBeInTheDocument()
    expect(
      screen.getByText('Define your commute routes with stations and interchanges')
    ).toBeInTheDocument()

    // Step 3
    expect(screen.getByText('Configure notifications')).toBeInTheDocument()
    expect(
      screen.getByText('Set up when and how you want to be notified about disruptions')
    ).toBeInTheDocument()
  })

  it('should render subtitle with correct text', () => {
    mockUseAuth.mockReturnValue({
      user: {
        name: 'Test User',
        email: 'test@example.com',
      } as User,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    expect(
      screen.getByText('Manage your routes and stay informed about tube disruptions')
    ).toBeInTheDocument()
  })

  it('should display icons for each stats card', () => {
    mockUseAuth.mockReturnValue({
      user: {
        name: 'Test User',
        email: 'test@example.com',
      } as User,
    })

    const { container } = render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    // Check that lucide icons are rendered (they use SVG)
    const icons = container.querySelectorAll('svg')
    expect(icons.length).toBeGreaterThan(0)
  })

  it('should extract only first name from full name', () => {
    mockUseAuth.mockReturnValue({
      user: {
        name: 'Mary Jane Watson',
        email: 'mj@example.com',
      } as User,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    // Should only show first name "Mary"
    expect(screen.getByText(/Welcome back, Mary!/i)).toBeInTheDocument()
  })

  it('should handle single-word name correctly', () => {
    mockUseAuth.mockReturnValue({
      user: {
        name: 'Madonna',
        email: 'madonna@example.com',
      } as User,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    expect(screen.getByText(/Welcome back, Madonna!/i)).toBeInTheDocument()
  })

  it('should display all numeric values as 0', () => {
    mockUseAuth.mockReturnValue({
      user: {
        name: 'Test User',
        email: 'test@example.com',
      } as User,
    })

    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    )

    // Get all elements with text "0"
    const zeroElements = screen.getAllByText('0')
    expect(zeroElements).toHaveLength(3) // Routes, Contacts, Active Alerts
  })
})
