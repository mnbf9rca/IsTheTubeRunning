import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { NetworkDisruptionsList } from './NetworkDisruptionsList'
import { type DisruptionResponse } from '@/types'
import * as useDisruptionsHook from '@/hooks/useDisruptions'

// Mock the hooks
vi.mock('@/hooks/useDisruptions')

// Helper to create test disruption data
const createDisruption = (overrides: Partial<DisruptionResponse> = {}): DisruptionResponse => ({
  line_id: 'piccadilly',
  line_name: 'Piccadilly',
  mode: 'tube',
  status_severity: 6,
  status_severity_description: 'Minor Delays',
  reason: "Signal failure at King's Cross",
  created_at: '2025-01-01T10:00:00Z',
  affected_routes: null,
  ...overrides,
})

describe('NetworkDisruptionsList', () => {
  const mockRefresh = vi.fn()

  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows loading skeleton during initial load', () => {
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: null,
      loading: true,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    const { container } = render(<NetworkDisruptionsList />)

    expect(screen.getByText('Current TfL Service Status')).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Loading disruptions' })).toBeInTheDocument()

    // Should show 3 skeleton cards
    const skeletonCards = container.querySelectorAll('.animate-pulse')
    expect(skeletonCards).toHaveLength(3)
  })

  it('shows error state with retry button', () => {
    const mockError = { message: 'Network error' }
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: null,
      loading: false,
      isRefreshing: false,
      error: mockError,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    expect(screen.getByText('Unable to load service status')).toBeInTheDocument()
    expect(screen.getByText(/Network error/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('calls refresh when retry button is clicked', () => {
    const mockError = { message: 'Network error' }
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: null,
      loading: false,
      isRefreshing: false,
      error: mockError,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    const retryButton = screen.getByRole('button', { name: /retry/i })
    fireEvent.click(retryButton)

    expect(mockRefresh).toHaveBeenCalledTimes(1)
  })

  it('shows default error message when error has no message', () => {
    const mockError = { message: '' }
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: null,
      loading: false,
      isRefreshing: false,
      error: mockError,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    expect(screen.getByText(/There was a problem fetching TfL disruptions/i)).toBeInTheDocument()
  })

  it('shows good service summary when no disruptions', () => {
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: [],
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    expect(screen.getByText('Current TfL Service Status')).toBeInTheDocument()
    // DisruptionSummary component should be rendered
    expect(screen.getByText(/Good service/i)).toBeInTheDocument()
  })

  it('displays disruptions correctly', () => {
    const disruptions = [
      createDisruption({
        line_name: 'Piccadilly',
        status_severity_description: 'Minor Delays',
      }),
      createDisruption({
        line_id: 'northern',
        line_name: 'Northern',
        status_severity_description: 'Severe Delays',
      }),
    ]

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions,
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    expect(screen.getByText('Piccadilly')).toBeInTheDocument()
    expect(screen.getByText('Northern')).toBeInTheDocument()
    expect(screen.getByText('Minor Delays')).toBeInTheDocument()
    expect(screen.getByText('Severe Delays')).toBeInTheDocument()
  })

  it('shows last updated timestamp', async () => {
    const disruptions = [createDisruption()]

    const now = new Date('2025-01-01T10:00:00Z')
    vi.setSystemTime(now)

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions,
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    await act(async () => {
      render(<NetworkDisruptionsList />)
    })

    expect(screen.getByText(/Last updated: just now/i)).toBeInTheDocument()
  })

  it('formats timestamp as "X minutes ago"', async () => {
    const disruptions = [createDisruption()]

    const now = new Date('2025-01-01T10:00:00Z')
    vi.setSystemTime(now)

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions,
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    let result: ReturnType<typeof render>

    await act(async () => {
      result = render(<NetworkDisruptionsList />)
    })

    // Check initial render
    expect(screen.getByText(/Last updated: just now/i)).toBeInTheDocument()

    // Advance time by 5 minutes
    vi.setSystemTime(new Date('2025-01-01T10:05:00Z'))

    await act(async () => {
      result.rerender(<NetworkDisruptionsList />)
    })

    expect(screen.getByText(/Last updated: 5 minutes ago/i)).toBeInTheDocument()
  })

  it('shows refresh indicator during background refresh', () => {
    const disruptions = [createDisruption()]

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions,
      loading: false,
      isRefreshing: true, // Background refresh in progress
      error: null,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    // Check for refresh icon with aria-label
    const refreshIcon = screen.getByLabelText('Refreshing')
    expect(refreshIcon).toBeInTheDocument()
  })

  it('configures useDisruptions with 10-second polling interval', () => {
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: [],
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    expect(useDisruptionsHook.useDisruptions).toHaveBeenCalledWith({
      pollInterval: 10000,
      enabled: true,
      filterGoodService: true,
    })
  })

  it('renders disruptions with good service summary', () => {
    const disruptions = [
      createDisruption({
        line_name: 'Piccadilly',
        status_severity_description: 'Minor Delays',
      }),
    ]

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions,
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    // Should show disruption card
    expect(screen.getByText('Piccadilly')).toBeInTheDocument()

    // Should also show good service summary (from DisruptionSummary component)
    expect(screen.getByText(/Good service/i)).toBeInTheDocument()
  })

  it('has proper section heading', () => {
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: [],
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    const heading = screen.getByRole('heading', { name: 'Current TfL Service Status' })
    expect(heading).toBeInTheDocument()
    expect(heading.tagName).toBe('H2')
  })

  it('renders with custom className', () => {
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: [],
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    const { container } = render(<NetworkDisruptionsList className="custom-class" />)

    const section = container.querySelector('section')
    expect(section).toHaveClass('custom-class')
  })

  it('shows last updated timestamp in empty state', async () => {
    const now = new Date('2025-01-01T10:00:00Z')
    vi.setSystemTime(now)

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: [],
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    await act(async () => {
      render(<NetworkDisruptionsList />)
    })

    expect(screen.getByText(/Last updated: just now/i)).toBeInTheDocument()
  })

  it('formats timestamp as "1 minute ago" singular', async () => {
    const disruptions = [createDisruption()]

    const now = new Date('2025-01-01T10:00:00Z')
    vi.setSystemTime(now)

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions,
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    let result: ReturnType<typeof render>

    await act(async () => {
      result = render(<NetworkDisruptionsList />)
    })

    // Check initial render
    expect(screen.getByText(/Last updated: just now/i)).toBeInTheDocument()

    // Advance time by exactly 1 minute
    vi.setSystemTime(new Date('2025-01-01T10:01:00Z'))

    await act(async () => {
      result.rerender(<NetworkDisruptionsList />)
    })

    expect(screen.getByText(/Last updated: 1 minute ago/i)).toBeInTheDocument()
  })

  it('formats timestamp with time when over 60 minutes', async () => {
    const disruptions = [createDisruption()]

    const now = new Date('2025-01-01T10:00:00Z')
    vi.setSystemTime(now)

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions,
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    let result: ReturnType<typeof render>

    await act(async () => {
      result = render(<NetworkDisruptionsList />)
    })

    // Check initial render
    expect(screen.getByText(/Last updated: just now/i)).toBeInTheDocument()

    // Advance time by over an hour
    vi.setSystemTime(new Date('2025-01-01T11:30:00Z'))

    await act(async () => {
      result.rerender(<NetworkDisruptionsList />)
    })

    // Should show time in HH:MM format
    expect(screen.getByText(/Last updated: 10:00/i)).toBeInTheDocument()
  })

  it('handles null disruptions same as empty array', () => {
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: null,
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    // Should show good service summary
    expect(screen.getByText(/Good service/i)).toBeInTheDocument()
  })

  it('loading state has aria-busy attribute', () => {
    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions: null,
      loading: true,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    const { container } = render(<NetworkDisruptionsList />)

    const section = container.querySelector('section')
    expect(section).toHaveAttribute('aria-busy', 'true')
  })

  it('disruptions list has role="list"', () => {
    const disruptions = [createDisruption()]

    vi.mocked(useDisruptionsHook.useDisruptions).mockReturnValue({
      disruptions,
      loading: false,
      isRefreshing: false,
      error: null,
      refresh: mockRefresh,
    })

    render(<NetworkDisruptionsList />)

    const list = screen.getByRole('list')
    expect(list).toBeInTheDocument()
  })
})
