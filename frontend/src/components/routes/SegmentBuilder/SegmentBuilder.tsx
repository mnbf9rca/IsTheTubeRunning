import { useState } from 'react'
import { X, AlertCircle, Check, Trash2 } from 'lucide-react'
import { Button } from '../../ui/button'
import { Alert, AlertDescription } from '../../ui/alert'
import { Label } from '../../ui/label'
import { Card } from '../../ui/card'
import { StationCombobox } from '../StationCombobox'
import { LineButton } from '../LineButton'
import { DestinationButton } from '../DestinationButton'
import { SegmentList } from '../SegmentList'
import type {
  SegmentResponse,
  LineResponse,
  StationResponse,
  SegmentRequest,
  RouteValidationResponse,
} from '../../../lib/api'
import { MAX_ROUTE_SEGMENTS } from './validation'
import { useSegmentBuilderState } from './hooks/useSegmentBuilderState'

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
  // ===== Custom Hook (All State Management) =====

  const {
    localSegments,
    currentStation,
    selectedLine,
    nextStation,
    step,
    error,
    setError,
    handleStationSelect,
    handleLineClick,
    handleNextStationSelect,
    handleContinueJourney,
    handleMarkAsDestination,
    handleBackFromChooseAction,
    handleEditRoute,
    handleDeleteSegment,
    handleCancel: hookHandleCancel,
    getCurrentStationLines,
    getNextStationLines,
    hasMaxSegments,
    isRouteComplete,
  } = useSegmentBuilderState({
    initialSegments,
    lines,
    stations,
    getLinesForStation,
  })

  // ===== Local State (Save Operation Only) =====

  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // ===== Handlers (Save Operation) =====

  /**
   * Handle mark as destination with save operation
   */
  const handleMarkAsDestinationAndSave = async () => {
    // Get final segments from hook (validation happens inside)
    const { segments: finalSegments, error: validationError } = handleMarkAsDestination()

    // If validation failed, error is already set by hook
    if (validationError) return

    // Auto-save the route
    try {
      setIsSaving(true)

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
   * Handle edit route and clear save success state
   */
  const handleEditRouteAndClearSuccess = () => {
    handleEditRoute()
    setSaveSuccess(false)
  }

  /**
   * Handle cancel and clear save success state
   */
  const handleCancelAndClearSuccess = () => {
    hookHandleCancel(onCancel)
    setSaveSuccess(false)
  }

  // ===== Derived Values (For Rendering) =====

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
      line_tfl_id: seg.line_tfl_id ?? null,
    }))

  // Get all available stations (for first segment, all stations; otherwise, only reachable stations)
  const availableStations = (() => {
    if (localSegments.length === 0 && step === 'select-station') {
      // First station: show all stations alphabetically
      return [...stations].sort((a, b) => a.name.localeCompare(b.name))
    }
    if (step === 'select-next-station' && currentTravelingLine && currentStation) {
      // Subsequent stations: show only reachable stations from current position on this line
      // This prevents selecting stations on different branches (e.g., Bank -> Charing Cross on Northern)
      return getNextStations(currentStation.tfl_id, currentTravelingLine.tfl_id)
    }
    return []
  })()

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

  // ===== Render =====

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
              <div className="rounded-md bg-muted p-3 flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-muted-foreground">To:</div>
                  <div className="text-base font-semibold">{nextStation.name}</div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleBackFromChooseAction}
                  aria-label="Remove selected station"
                  className="h-8 w-8"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
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
                  <DestinationButton onClick={handleMarkAsDestinationAndSave} />
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
        <Button variant="outline" onClick={handleEditRouteAndClearSuccess} disabled={isSaving}>
          Edit Route
        </Button>
      )}

      {/* Cancel Button (always shown during route building) */}
      {!isRouteComplete && (
        <Button variant="outline" onClick={handleCancelAndClearSuccess} disabled={isSaving}>
          <X className="mr-2 h-4 w-4" />
          Cancel
        </Button>
      )}
    </div>
  )
}
