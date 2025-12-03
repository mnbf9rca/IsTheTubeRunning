import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DisruptionCard } from './DisruptionCard'
import { type DisruptionResponse } from '@/types'
import * as tflColors from '@/lib/tfl-colors'

// Mock the TfL colors module
vi.mock('@/lib/tfl-colors', () => ({
  getLineColor: vi.fn((lineId: string) => {
    const colors: Record<string, string> = {
      piccadilly: '#003688',
      northern: '#000000',
      victoria: '#0098D4',
      dlr: '#00A4A7',
    }
    return colors[lineId] || '#666666'
  }),
}))

// Helper to create test disruption data
const createDisruption = (overrides: Partial<DisruptionResponse> = {}): DisruptionResponse => ({
  line_id: 'piccadilly',
  line_name: 'Piccadilly',
  mode: 'tube',
  status_severity: 10,
  status_severity_description: 'Minor Delays',
  reason: "Signal failure at King's Cross",
  created_at: '2025-01-01T10:00:00Z',
  affected_routes: null,
  ...overrides,
})

describe('DisruptionCard', () => {
  it('renders disruption card with all information', () => {
    const disruption = createDisruption()
    render(<DisruptionCard disruption={disruption} />)

    expect(screen.getByText('Piccadilly')).toBeInTheDocument()
    expect(screen.getByText('Minor Delays')).toBeInTheDocument()
    expect(screen.getByText("Signal failure at King's Cross")).toBeInTheDocument()
  })

  it('displays line name prominently', () => {
    const disruption = createDisruption({ line_name: 'Northern' })
    render(<DisruptionCard disruption={disruption} />)

    const lineName = screen.getByRole('heading', { name: 'Northern' })
    expect(lineName).toBeInTheDocument()
    expect(lineName.tagName).toBe('H3')
  })

  it('renders severity badge with correct props', () => {
    const disruption = createDisruption({
      status_severity: 15,
      status_severity_description: 'Severe Delays',
    })
    render(<DisruptionCard disruption={disruption} />)

    // DisruptionBadge component should be rendered with the severity
    expect(screen.getByText('Severe Delays')).toBeInTheDocument()
  })

  it('displays reason text when provided', () => {
    const disruption = createDisruption({
      reason: 'Delays due to earlier incident',
    })
    render(<DisruptionCard disruption={disruption} />)

    expect(screen.getByText('Delays due to earlier incident')).toBeInTheDocument()
  })

  it('does not display reason section when reason is null', () => {
    const disruption = createDisruption({ reason: null })
    const { container } = render(<DisruptionCard disruption={disruption} />)

    // Check that there's no paragraph with reason text
    const reasonText = container.querySelector('p.text-sm')
    expect(reasonText).not.toBeInTheDocument()
  })

  it('does not display reason section when reason is undefined', () => {
    const disruption = createDisruption({ reason: undefined })
    const { container } = render(<DisruptionCard disruption={disruption} />)

    // Check that there's no paragraph with reason text
    const reasonText = container.querySelector('p.text-sm')
    expect(reasonText).not.toBeInTheDocument()
  })

  it('applies line color to vertical strip', () => {
    const disruption = createDisruption({ line_id: 'piccadilly' })
    const { container } = render(<DisruptionCard disruption={disruption} />)

    expect(tflColors.getLineColor).toHaveBeenCalledWith('piccadilly')

    // Find the color strip element
    const colorStrip = container.querySelector('.absolute.left-0')
    expect(colorStrip).toHaveStyle({ backgroundColor: '#003688' })
  })

  it('renders with correct line color for different lines', () => {
    const lines = [
      { id: 'northern', expectedColor: '#000000' },
      { id: 'victoria', expectedColor: '#0098D4' },
      { id: 'dlr', expectedColor: '#00A4A7' },
    ]

    lines.forEach(({ id, expectedColor }) => {
      const disruption = createDisruption({ line_id: id })
      const { container } = render(<DisruptionCard disruption={disruption} />)

      const colorStrip = container.querySelector('.absolute.left-0')
      expect(colorStrip).toHaveStyle({ backgroundColor: expectedColor })
    })
  })

  it('has proper ARIA role for article', () => {
    const disruption = createDisruption()
    const { container } = render(<DisruptionCard disruption={disruption} />)

    const article = container.querySelector('[role="article"]')
    expect(article).toBeInTheDocument()
  })

  it('has accessible ARIA label with disruption details', () => {
    const disruption = createDisruption({
      line_name: 'Victoria',
      status_severity_description: 'Severe Delays',
      reason: 'Signal failure',
    })
    render(<DisruptionCard disruption={disruption} />)

    const article = screen.getByRole('article')
    expect(article).toHaveAttribute('aria-label', 'Victoria: Severe Delays. Signal failure')
  })

  it('has accessible ARIA label without reason when not provided', () => {
    const disruption = createDisruption({
      line_name: 'Jubilee',
      status_severity_description: 'Good Service',
      reason: null,
    })
    render(<DisruptionCard disruption={disruption} />)

    const article = screen.getByRole('article')
    expect(article).toHaveAttribute('aria-label', 'Jubilee: Good Service')
  })

  it('color strip is marked as aria-hidden', () => {
    const disruption = createDisruption()
    const { container } = render(<DisruptionCard disruption={disruption} />)

    const colorStrip = container.querySelector('.absolute.left-0')
    expect(colorStrip).toHaveAttribute('aria-hidden', 'true')
  })

  it('renders with custom className', () => {
    const disruption = createDisruption()
    const { container } = render(
      <DisruptionCard disruption={disruption} className="custom-class" />
    )

    const card = container.querySelector('.custom-class')
    expect(card).toBeInTheDocument()
  })

  it('renders correctly with all fields populated', () => {
    const disruption: DisruptionResponse = {
      line_id: 'central',
      line_name: 'Central',
      mode: 'tube',
      status_severity: 10,
      status_severity_description: 'Minor Delays',
      reason: 'Delays due to planned engineering works',
      created_at: '2025-01-01T10:00:00Z',
      affected_routes: [
        {
          name: 'Central',
          direction: 'Eastbound',
          affected_stations: ['Bank', 'Liverpool Street'],
        },
      ],
    }

    render(<DisruptionCard disruption={disruption} />)

    expect(screen.getByText('Central')).toBeInTheDocument()
    expect(screen.getByText('Minor Delays')).toBeInTheDocument()
    expect(screen.getByText('Delays due to planned engineering works')).toBeInTheDocument()
  })

  it('handles missing optional fields gracefully', () => {
    const disruption: DisruptionResponse = {
      line_id: 'elizabeth',
      line_name: 'Elizabeth Line',
      mode: 'elizabeth-line',
      status_severity: 10,
      status_severity_description: 'Good Service',
      reason: null,
      created_at: null,
      affected_routes: null,
    }

    render(<DisruptionCard disruption={disruption} />)

    expect(screen.getByText('Elizabeth Line')).toBeInTheDocument()
    expect(screen.getByText('Good Service')).toBeInTheDocument()
  })

  it('renders with default className when not provided', () => {
    const disruption = createDisruption()
    const { container } = render(<DisruptionCard disruption={disruption} />)

    // Should still render the Card component
    expect(container.firstChild).toBeInTheDocument()
  })
})
