import { useState, useEffect, useCallback } from 'react'
import { X, AlertCircle, Check } from 'lucide-react'
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
   * Helper function to get reachable stations from current position
   */
  getNextStations: (currentStationTflId: string, currentLineTflId: string) => StationResponse[]

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
  getNextStations,
  onValidate,
  onSave,
  onCancel,
}: SegmentBuilderProps) {
  // Local state for segments being built
  const [localSegments, setLocalSegments] = useState<SegmentRequest[]>(
    initialSegments.map((seg) => ({
      sequence: seg.sequence,
      station_tfl_id: seg.station_tfl_id,
      line_tfl_id: seg.line_tfl_id,
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
  const getCurrentStationLines = useCallback((): LineResponse[] => {
    if (!currentStation) return []
    const stationLines = getLinesForStation(currentStation.tfl_id)
    return sortLines(stationLines)
  }, [currentStation, getLinesForStation])

  // Get available lines for next station (for action buttons)
  const getNextStationLines = useCallback((): LineResponse[] => {
    if (!nextStation) return []
    const stationLines = getLinesForStation(nextStation.tfl_id)
    return sortLines(stationLines)
  }, [nextStation, getLinesForStation])

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
  }, [currentStation, step, getCurrentStationLines])

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
    // Allow currentStation if it's the last segment (junction we're continuing from)
    const lastSegment = localSegments[localSegments.length - 1]
    const isCurrentStationLastInRoute = lastSegment?.station_tfl_id === currentStation.tfl_id
    const isDuplicate =
      !isCurrentStationLastInRoute &&
      localSegments.some((seg) => seg.station_tfl_id === currentStation.tfl_id)
    if (isDuplicate) {
      setError(
        `This station (${currentStation.name}) is already in your route. Routes cannot visit the same station twice.`
      )
      return
    }

    // Add segment for current station if not already in route
    let updatedSegments: SegmentRequest[]

    if (isCurrentStationLastInRoute) {
      // Current station is already the last segment (junction from previous line change)
      // Don't add it again, just continue from here
      updatedSegments = [...localSegments]
    } else {
      // Check max segments limit
      if (localSegments.length >= MAX_ROUTE_SEGMENTS) {
        setError(`Maximum ${MAX_ROUTE_SEGMENTS} segments allowed per route.`)
        return
      }

      // Add segment for current station with selected line
      const newSegment: SegmentRequest = {
        sequence: localSegments.length,
        station_tfl_id: currentStation.tfl_id,
        line_tfl_id: selectedLine.tfl_id,
      }

      updatedSegments = [...localSegments, newSegment]
    }

    // If user is switching to a different line, also add the nextStation segment
    // This shows the station where the line change occurs
    if (line.id !== selectedLine.id) {
      // Check if nextStation is a duplicate
      const isNextDuplicate = updatedSegments.some(
        (seg) => seg.station_tfl_id === nextStation.tfl_id
      )
      if (isNextDuplicate) {
        setError(
          `This station (${nextStation.name}) is already in your route. Routes cannot visit the same station twice.`
        )
        return
      }

      // Check max segments limit after adding both segments
      if (updatedSegments.length >= MAX_ROUTE_SEGMENTS) {
        setError(`Maximum ${MAX_ROUTE_SEGMENTS} segments allowed per route.`)
        return
      }

      // Add nextStation with the line used to DEPART from it (the new line we're switching to)
      const nextSegment: SegmentRequest = {
        sequence: updatedSegments.length,
        station_tfl_id: nextStation.tfl_id,
        line_tfl_id: line.tfl_id, // FIX: Use the line we're switching TO, not the line we arrived on
      }
      updatedSegments = [...updatedSegments, nextSegment]
    }

    setLocalSegments(updatedSegments)

    // Set up for next segment
    setCurrentStation(nextStation)
    setSelectedLine(line) // Continue on selected line
    setNextStation(null)
    setStep('select-next-station')
    setError(null)
  }

  const handleMarkAsDestination = async () => {
    if (!currentStation || !selectedLine || !nextStation) return

    // Check for duplicate stations
    // Allow currentStation if it's the last segment (junction we're continuing from)
    const lastSegment = localSegments[localSegments.length - 1]
    const isCurrentStationLastInRoute = lastSegment?.station_tfl_id === currentStation.tfl_id
    const isDuplicateCurrent =
      !isCurrentStationLastInRoute &&
      localSegments.some((seg) => seg.station_tfl_id === currentStation.tfl_id)
    if (isDuplicateCurrent) {
      setError(
        `This station (${currentStation.name}) is already in your route. Routes cannot visit the same station twice.`
      )
      return
    }

    const isDuplicateNext = localSegments.some((seg) => seg.station_tfl_id === nextStation.tfl_id)
    if (isDuplicateNext) {
      setError(
        `This station (${nextStation.name}) is already in your route. Routes cannot visit the same station twice.`
      )
      return
    }

    // Build final segments
    let finalSegments: SegmentRequest[]

    if (isCurrentStationLastInRoute) {
      // Current station is already in route (junction from line change)
      // Only add the destination station
      if (localSegments.length + 1 > MAX_ROUTE_SEGMENTS) {
        setError(`Maximum ${MAX_ROUTE_SEGMENTS} segments allowed per route.`)
        return
      }

      const destinationSegment: SegmentRequest = {
        sequence: localSegments.length,
        station_tfl_id: nextStation.tfl_id,
        line_tfl_id: null, // Destination has no outgoing line
      }

      finalSegments = [...localSegments, destinationSegment]
    } else {
      // Current station not in route yet - add both current and destination
      if (localSegments.length + 2 > MAX_ROUTE_SEGMENTS) {
        setError(`Maximum ${MAX_ROUTE_SEGMENTS} segments allowed per route.`)
        return
      }

      const currentSegment: SegmentRequest = {
        sequence: localSegments.length,
        station_tfl_id: currentStation.tfl_id,
        line_tfl_id: selectedLine.tfl_id,
      }

      const destinationSegment: SegmentRequest = {
        sequence: localSegments.length + 1,
        station_tfl_id: nextStation.tfl_id,
        line_tfl_id: null, // Destination has no outgoing line
      }

      finalSegments = [...localSegments, currentSegment, destinationSegment]
    }

    // Reset UI state
    setCurrentStation(null)
    setSelectedLine(null)
    setNextStation(null)
    setStep('select-station')
    setError(null)

    // Auto-save the route
    try {
      setIsSaving(true)
      setLocalSegments(finalSegments)

      // Validate route (backend checks connections)
      const validation = await onValidate(finalSegments)
      if (!validation.valid) {
        setError(validation.message)
        setIsSaving(false)
        return
      }

      // Save segments
      await onSave(finalSegments)

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
      setError(err instanceof Error ? err.message : 'Failed to save route')
      setSaveSuccess(false)
    } finally {
      setIsSaving(false)
    }
  }

  /**
   * Resume building from the last segment in the list
   * Sets state as if user just selected that last station
   * @param segments - The current list of segments to resume from
   * @param targetStep - The step to set ('select-next-station' or 'choose-action')
   */
  const resumeFromLastSegment = (
    segments: SegmentRequest[],
    targetStep: 'select-next-station' | 'choose-action' = 'select-next-station'
  ) => {
    if (segments.length === 0) {
      // No segments - start fresh
      setCurrentStation(null)
      setSelectedLine(null)
      setNextStation(null)
      setStep('select-station')
    } else {
      // Resume from last segment
      const lastSegment = segments[segments.length - 1]
      const lastStation = stations.find((s) => s.tfl_id === lastSegment.station_tfl_id)
      const lastLine = lastSegment.line_tfl_id
        ? lines.find((l) => l.tfl_id === lastSegment.line_tfl_id)
        : null

      if (lastStation && lastLine) {
        // Ready to continue from this station
        setCurrentStation(lastStation)
        setSelectedLine(lastLine)
        setNextStation(null)
        setStep(targetStep)
      } else {
        // Fallback to initial state
        setCurrentStation(null)
        setSelectedLine(null)
        setNextStation(null)
        setStep('select-station')
      }
    }
  }

  /**
   * Enter edit mode for a completed route
   * Sets state to show the destination station with action buttons (line selection + mark as destination)
   */
  const handleEditRoute = () => {
    // Find the destination segment (line_tfl_id === null) to get the destination station
    const destinationSegment = localSegments.find((seg) => seg.line_tfl_id === null)
    if (!destinationSegment || localSegments.length < 2) {
      return
    }

    // Get the segment before the destination to find the line we arrived on
    const segmentBeforeDestination = localSegments[localSegments.length - 2]
    const prevStation = stations.find((s) => s.tfl_id === segmentBeforeDestination.station_tfl_id)
    const destinationStation = stations.find((s) => s.tfl_id === destinationSegment.station_tfl_id)
    const arrivalLine = lines.find((l) => l.tfl_id === segmentBeforeDestination.line_tfl_id)

    if (prevStation && destinationStation && arrivalLine) {
      // Set up state as if we just selected the destination as the "next station"
      // This shows line buttons for interchanges + "Mark as Destination" button
      setCurrentStation(prevStation)
      setSelectedLine(arrivalLine)
      setNextStation(destinationStation)
      setStep('choose-action')
    }

    setSaveSuccess(false)
    setError(null)
  }

  const handleDeleteSegment = (sequence: number) => {
    // Prevent deletion of destination station (last segment with line_tfl_id === null)
    const isDestination =
      sequence === localSegments.length - 1 && localSegments[sequence].line_tfl_id === null

    if (isDestination) {
      setError(
        'Cannot delete the destination station. Delete an earlier station to shorten your route.'
      )
      return
    }

    // When deleting intermediate station, delete it and all subsequent stations
    // to avoid invalid routes (A->B->C, delete B would leave A->C which may be invalid)
    const updatedSegments = localSegments
      .filter((seg) => seg.sequence < sequence)
      .map((seg, index) => ({ ...seg, sequence: index }))

    setLocalSegments(updatedSegments)

    // Resume from the last remaining segment
    resumeFromLastSegment(updatedSegments, 'select-next-station')

    setError(null)
  }

  const handleCancel = () => {
    setLocalSegments(
      initialSegments.map((seg) => ({
        sequence: seg.sequence,
        station_tfl_id: seg.station_tfl_id,
        line_tfl_id: seg.line_tfl_id,
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

  // Check if route is complete (has destination segment with line_tfl_id: null)
  // When in choose-action mode, we're editing the route, so it's not "complete" for UI purposes
  const isRouteComplete =
    localSegments.length >= 2 &&
    localSegments[localSegments.length - 1].line_tfl_id === null &&
    step !== 'choose-action'

  // Convert local segments to SegmentResponse format for display
  // When in choose-action step with a complete route, hide the destination marker
  // to show action buttons for the last actual station
  const displaySegments: SegmentResponse[] = localSegments
    .filter((seg) => {
      // In choose-action mode, hide the destination so we can show action buttons
      if (step === 'choose-action' && seg.line_tfl_id === null) {
        return false
      }
      return true
    })
    .map((seg) => ({
      id: `temp-${seg.sequence}`, // Temporary ID for display
      ...seg,
    }))

  // Instructions based on current step
  const getInstructions = () => {
    if (localSegments.length === 0 && !currentStation) {
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

  // Get the current traveling line (for display purposes)
  const currentTravelingLine = (() => {
    if (selectedLine) return selectedLine
    // Fallback: Get line from last segment when selectedLine is null (e.g., after Edit Route)
    const lastSegment = localSegments[localSegments.length - 1]
    if (lastSegment?.line_tfl_id) {
      return lines.find((l) => l.tfl_id === lastSegment.line_tfl_id)
    }
    return null
  })()

  // Get all available stations (for first segment, all stations; otherwise, only reachable stations)
  const availableStations = (() => {
    if (localSegments.length === 0 && step === 'select-station') {
      // First station: show all stations alphabetically
      return [...stations].sort((a, b) => a.name.localeCompare(b.name))
    }
    if (step === 'select-next-station') {
      if (currentTravelingLine && currentStation) {
        // Subsequent stations: show only reachable stations from current position on this line
        // This prevents selecting stations on different branches (e.g., Bank -> Charing Cross on Northern)
        return getNextStations(currentStation.tfl_id, currentTravelingLine.tfl_id)
      }
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
            isRouteComplete={isRouteComplete}
            onDeleteSegment={handleDeleteSegment}
          />
        </div>
      )}

      {/* Build Segment Form */}
      {!hasMaxSegments && !isRouteComplete && (
        <Card className="p-4">
          <h3 className="mb-4 text-sm font-medium">
            {localSegments.length === 0 && !currentStation
              ? 'Add Starting Station'
              : 'Continue Your Journey'}
          </h3>

          <div className="space-y-4">
            {/* Show selected starting station when building route */}
            {currentStation &&
              (step === 'select-line' ||
                step === 'select-next-station' ||
                step === 'choose-action') && (
                <div className="rounded-md bg-muted p-3">
                  <div className="text-sm font-medium text-muted-foreground">From:</div>
                  <div className="text-base font-semibold">{currentStation.name}</div>
                </div>
              )}

            {/* Step 1: Select Station (starting or next) */}
            {step === 'select-station' && (
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
                  Traveling on: {currentTravelingLine?.name || 'Unknown'} line
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

            {/* Show selected next station before action buttons */}
            {step === 'choose-action' && nextStation && (
              <div className="rounded-md bg-muted p-3">
                <div className="text-sm font-medium text-muted-foreground">To:</div>
                <div className="text-base font-semibold">{nextStation.name}</div>
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

      {/* Edit Route Button (shown when route is complete) */}
      {isRouteComplete && (
        <Button variant="outline" onClick={handleEditRoute} disabled={isSaving}>
          Edit Route
        </Button>
      )}

      {/* Cancel Button (always shown during route building) */}
      {!isRouteComplete && (
        <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
          <X className="mr-2 h-4 w-4" />
          Cancel
        </Button>
      )}
    </div>
  )
}
