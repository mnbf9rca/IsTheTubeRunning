import { useState, useEffect } from 'react'
import { Save, X, AlertCircle, Check } from 'lucide-react'
import { Button } from '../ui/button'
import { Alert, AlertDescription } from '../ui/alert'
import { Label } from '../ui/label'
import { Card } from '../ui/card'
import { StationCombobox } from './StationCombobox'
import { LineButton } from './LineButton'
import { DestinationButton } from './DestinationButton'
import { SegmentList } from './SegmentList'
import { sortLines } from '../../lib/tfl-colors'
import type {
  SegmentResponse,
  LineResponse,
  StationResponse,
  SegmentRequest,
  RouteValidationResponse,
} from '../../lib/api'

// Maximum number of segments allowed per route
const MAX_ROUTE_SEGMENTS = 20

export interface SegmentBuilderProps {
  /**
   * Route ID being edited
   */
  routeId: string

  /**
   * Current segments (from server)
   */
  initialSegments: SegmentResponse[]

  /**
   * All available lines
   */
  lines: LineResponse[]

  /**
   * All available stations
   */
  stations: StationResponse[]

  /**
   * Helper function to get lines for a station
   */
  getLinesForStation: (stationTflId: string) => LineResponse[]

  /**
   * Callback to validate route before saving
   */
  onValidate: (segments: SegmentRequest[]) => Promise<RouteValidationResponse>

  /**
   * Callback to save segments
   */
  onSave: (segments: SegmentRequest[]) => Promise<void>

  /**
   * Callback when cancel is clicked
   */
  onCancel: () => void
}

/**
 * Segment builder component for creating/editing route segments
 *
 * Uses button-based interface following STATION→LINE→STATION model:
 * 1. Select starting station
 * 2. If station has only 1 line: auto-advance to next station selector
 * 3. If station has 2+ lines: show line buttons (sorted alphabetically)
 * 4. Click line button to select line and show next station selector
 * 5. Select next station, then choose: continue journey OR mark as destination
 * 6. Repeat until route is complete
 * 7. Save with confirmation and auto-scroll to Active Times section
 *
 * @example
 * <SegmentBuilder
 *   routeId={route.id}
 *   initialSegments={route.segments}
 *   lines={lines}
 *   stations={stations}
 *   getLinesForStation={getLinesForStation}
 *   onValidate={validateRoute}
 *   onSave={upsertSegments}
 *   onCancel={() => setEditing(false)}
 * />
 */
export function SegmentBuilder({
  initialSegments,
  lines,
  stations,
  getLinesForStation,
  onValidate,
  onSave,
  onCancel,
}: SegmentBuilderProps) {
  // Local state for segments being built
  const [localSegments, setLocalSegments] = useState<SegmentRequest[]>(
    initialSegments.map((seg) => ({
      sequence: seg.sequence,
      station_id: seg.station_id,
      line_id: seg.line_id,
    }))
  )

  // State for building current segment
  const [currentStation, setCurrentStation] = useState<StationResponse | null>(null)
  const [selectedLine, setSelectedLine] = useState<LineResponse | null>(null)
  const [nextStation, setNextStation] = useState<StationResponse | null>(null)

  // UI state
  const [step, setStep] = useState<
    'select-station' | 'select-line' | 'select-next-station' | 'choose-action'
  >('select-station')
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Get available lines for current station
  const getCurrentStationLines = (): LineResponse[] => {
    if (!currentStation) return []
    const stationLines = getLinesForStation(currentStation.tfl_id)
    return sortLines(stationLines)
  }

  // Get available lines for next station (for action buttons)
  const getNextStationLines = (): LineResponse[] => {
    if (!nextStation) return []
    const stationLines = getLinesForStation(nextStation.tfl_id)
    return sortLines(stationLines)
  }

  // Auto-advance logic when station selected
  useEffect(() => {
    if (step === 'select-station' && currentStation) {
      const stationLines = getCurrentStationLines()

      // If only 1 line available, auto-select it and advance to next station
      if (stationLines.length === 1) {
        setSelectedLine(stationLines[0])
        setStep('select-next-station')
      } else if (stationLines.length > 1) {
        // Multiple lines: show line selection buttons
        setStep('select-line')
      } else {
        // No lines (shouldn't happen with valid TfL data)
        setError('This station has no lines available')
      }
    }
  }, [currentStation, step])

  const handleStationSelect = (stationId: string | undefined) => {
    if (!stationId) {
      setCurrentStation(null)
      setStep('select-station')
      return
    }

    const station = stations.find((s) => s.id === stationId)
    if (station) {
      setCurrentStation(station)
      setError(null)
      // Auto-advance logic will trigger in useEffect
    }
  }

  const handleLineClick = (line: LineResponse) => {
    setSelectedLine(line)
    setStep('select-next-station')
    setError(null)
  }

  const handleNextStationSelect = (stationId: string | undefined) => {
    if (!stationId) {
      setNextStation(null)
      setStep('select-next-station')
      return
    }

    const station = stations.find((s) => s.id === stationId)
    if (station) {
      setNextStation(station)
      setStep('choose-action')
      setError(null)
    }
  }

  const handleContinueJourney = (line: LineResponse) => {
    if (!currentStation || !selectedLine || !nextStation) return

    // Check for duplicate stations (acyclic enforcement)
    const isDuplicate = localSegments.some((seg) => seg.station_id === currentStation.id)
    if (isDuplicate) {
      setError(
        `This station (${currentStation.name}) is already in your route. Routes cannot visit the same station twice.`
      )
      return
    }

    // Check max segments limit
    if (localSegments.length >= MAX_ROUTE_SEGMENTS) {
      setError(`Maximum ${MAX_ROUTE_SEGMENTS} segments allowed per route.`)
      return
    }

    // Add segment for current station with selected line
    const newSegment: SegmentRequest = {
      sequence: localSegments.length,
      station_id: currentStation.id,
      line_id: selectedLine.id,
    }

    setLocalSegments([...localSegments, newSegment])

    // Set up for next segment
    setCurrentStation(nextStation)
    setSelectedLine(line) // Continue on selected line
    setNextStation(null)
    setStep('select-next-station')
    setError(null)
  }

  const handleMarkAsDestination = () => {
    if (!currentStation || !selectedLine || !nextStation) return

    // Check for duplicate stations
    const isDuplicateCurrent = localSegments.some((seg) => seg.station_id === currentStation.id)
    if (isDuplicateCurrent) {
      setError(
        `This station (${currentStation.name}) is already in your route. Routes cannot visit the same station twice.`
      )
      return
    }

    const isDuplicateNext = localSegments.some((seg) => seg.station_id === nextStation.id)
    if (isDuplicateNext) {
      setError(
        `This station (${nextStation.name}) is already in your route. Routes cannot visit the same station twice.`
      )
      return
    }

    // Check max segments limit (we're adding 2 segments)
    if (localSegments.length + 2 > MAX_ROUTE_SEGMENTS) {
      setError(`Maximum ${MAX_ROUTE_SEGMENTS} segments allowed per route.`)
      return
    }

    // Add segment for current station with selected line
    const currentSegment: SegmentRequest = {
      sequence: localSegments.length,
      station_id: currentStation.id,
      line_id: selectedLine.id,
    }

    // Add segment for destination with null line_id
    const destinationSegment: SegmentRequest = {
      sequence: localSegments.length + 1,
      station_id: nextStation.id,
      line_id: null, // Destination has no outgoing line
    }

    setLocalSegments([...localSegments, currentSegment, destinationSegment])

    // Reset for potential new route
    setCurrentStation(null)
    setSelectedLine(null)
    setNextStation(null)
    setStep('select-station')
    setError(null)
  }

  const handleDeleteSegment = (sequence: number) => {
    // Remove segment and resequence
    const updatedSegments = localSegments
      .filter((seg) => seg.sequence !== sequence)
      .map((seg, index) => ({ ...seg, sequence: index }))

    setLocalSegments(updatedSegments)

    // Reset building state if we deleted segments
    setCurrentStation(null)
    setSelectedLine(null)
    setNextStation(null)
    setStep('select-station')
    setError(null)
  }

  const handleSave = async () => {
    if (localSegments.length < 2) {
      setError('Route must have at least 2 segments')
      return
    }

    try {
      setIsSaving(true)
      setError(null)
      setSaveSuccess(false)

      // Validate route (backend checks connections)
      const validation = await onValidate(localSegments)
      if (!validation.valid) {
        setError(validation.message)
        return
      }

      // Save segments
      await onSave(localSegments)

      // Show success confirmation
      setSaveSuccess(true)

      // Auto-scroll to Active Times section after 1 second
      setTimeout(() => {
        const activeTimesSection = document.getElementById('active-times-section')
        if (activeTimesSection) {
          activeTimesSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }, 1000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save segments')
      setSaveSuccess(false)
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    setLocalSegments(
      initialSegments.map((seg) => ({
        sequence: seg.sequence,
        station_id: seg.station_id,
        line_id: seg.line_id,
      }))
    )
    setCurrentStation(null)
    setSelectedLine(null)
    setNextStation(null)
    setStep('select-station')
    setError(null)
    setSaveSuccess(false)
    onCancel()
  }

  const hasMaxSegments = localSegments.length >= MAX_ROUTE_SEGMENTS
  const hasChanges =
    JSON.stringify(localSegments) !==
    JSON.stringify(
      initialSegments.map((seg) => ({
        sequence: seg.sequence,
        station_id: seg.station_id,
        line_id: seg.line_id,
      }))
    )

  // Convert local segments to SegmentResponse format for display
  const displaySegments: SegmentResponse[] = localSegments.map((seg) => ({
    id: `temp-${seg.sequence}`, // Temporary ID for display
    ...seg,
  }))

  // Instructions based on current step
  const getInstructions = () => {
    if (localSegments.length === 0) {
      return 'Select your starting station to begin your route.'
    }
    if (hasMaxSegments) {
      return `Maximum ${MAX_ROUTE_SEGMENTS} segments reached. Save your route or remove segments to continue.`
    }
    if (step === 'select-station') {
      return 'Select the next station to continue your journey.'
    }
    if (step === 'select-line') {
      return 'Select which line you want to travel on.'
    }
    if (step === 'select-next-station') {
      return `Traveling on ${selectedLine?.name || 'selected'} line. Select your destination.`
    }
    if (step === 'choose-action') {
      return 'Continue your journey or mark this as your final destination.'
    }
    return 'Build your route by selecting stations and lines.'
  }

  const currentStationLines = getCurrentStationLines()
  const nextStationLines = getNextStationLines()

  // Get all available stations (for first segment, all stations; otherwise, stations on selected line)
  const availableStations = (() => {
    if (localSegments.length === 0 && step === 'select-station') {
      return stations
    }
    if (step === 'select-next-station' && selectedLine) {
      return stations.filter((s) => s.lines.includes(selectedLine.tfl_id))
    }
    return []
  })()

  return (
    <div className="space-y-6">
      {/* Instructions */}
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{getInstructions()}</AlertDescription>
      </Alert>

      {/* Segment List */}
      {localSegments.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium">Route Path</h3>
          <SegmentList
            segments={displaySegments}
            lines={lines}
            stations={stations}
            onDeleteSegment={handleDeleteSegment}
          />
        </div>
      )}

      {/* Build Segment Form */}
      {!hasMaxSegments && (
        <Card className="p-4">
          <h3 className="mb-4 text-sm font-medium">
            {localSegments.length === 0 ? 'Add Starting Station' : 'Continue Your Journey'}
          </h3>

          <div className="space-y-4">
            {/* Step 1: Select Station (starting or next) */}
            {(step === 'select-station' || step === 'select-line') && (
              <div className="space-y-2">
                <Label htmlFor="station-select">Station</Label>
                <StationCombobox
                  stations={availableStations}
                  value={currentStation?.id}
                  onChange={handleStationSelect}
                  placeholder="Select station..."
                />
              </div>
            )}

            {/* Step 2: Select Line (only if 2+ lines) */}
            {step === 'select-line' && currentStationLines.length > 0 && (
              <div className="space-y-2">
                <Label>Travel on line:</Label>
                <div className="flex flex-wrap gap-2">
                  {currentStationLines.map((line) => (
                    <LineButton
                      key={line.id}
                      line={line}
                      selected={selectedLine?.id === line.id}
                      onClick={() => handleLineClick(line)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Step 3: Select Next Station */}
            {step === 'select-next-station' && (
              <div className="space-y-2">
                <Label htmlFor="next-station-select">
                  Traveling on: {selectedLine?.name || 'Unknown'} line
                </Label>
                <Label htmlFor="next-station-select">To station:</Label>
                <StationCombobox
                  stations={availableStations}
                  value={nextStation?.id}
                  onChange={handleNextStationSelect}
                  placeholder="Select destination..."
                />
              </div>
            )}

            {/* Step 4: Choose Action (Continue or Destination) */}
            {step === 'choose-action' && (
              <div className="space-y-2">
                <Label>What next?</Label>
                <div className="flex flex-wrap gap-2">
                  {nextStationLines.map((line) => (
                    <LineButton
                      key={line.id}
                      line={line}
                      onClick={() => handleContinueJourney(line)}
                    />
                  ))}
                  <DestinationButton onClick={handleMarkAsDestination} />
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Save Success */}
      {saveSuccess && (
        <Alert className="border-green-600 bg-green-50">
          <Check className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-600">
            ✓ Segments saved successfully!
          </AlertDescription>
        </Alert>
      )}

      {/* Save/Cancel Buttons */}
      <div className="flex gap-2">
        <Button onClick={handleSave} disabled={isSaving || localSegments.length < 2 || !hasChanges}>
          <Save className="mr-2 h-4 w-4" />
          {isSaving ? 'Saving...' : 'Save Segments'}
        </Button>
        <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
          <X className="mr-2 h-4 w-4" />
          Cancel
        </Button>
      </div>
    </div>
  )
}
