import { useState, useEffect } from 'react'
import { Plus, Save, X, AlertCircle } from 'lucide-react'
import { Button } from '../ui/button'
import { Alert, AlertDescription } from '../ui/alert'
import { Label } from '../ui/label'
import { Card } from '../ui/card'
import { StationCombobox } from './StationCombobox'
import { LineSelect } from './LineSelect'
import { SegmentList } from './SegmentList'
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
 * Provides a sequential UX for building routes:
 * 1. Select start station (any station)
 * 2. Select line at that station
 * 3. Select next station (any station on current line)
 * 4. Continue adding stations
 * 5. Validate and save
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

  // State for adding a new segment
  const [selectedStationId, setSelectedStationId] = useState<string | undefined>(undefined)
  const [selectedLineId, setSelectedLineId] = useState<string | undefined>(undefined)

  // UI state
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Determine available stations for next segment
  const getAvailableStations = (): StationResponse[] => {
    if (localSegments.length === 0) {
      // First segment: all stations available
      return stations
    }

    // Get last segment's line
    const lastSegment = localSegments[localSegments.length - 1]
    const lastLine = lines.find((l) => l.id === lastSegment.line_id)

    if (!lastLine) return []

    // Return ALL stations on the last line (not just adjacent ones)
    // The user can select any station on the current line to build their journey
    return stations.filter((station) => station.lines.includes(lastLine.tfl_id))
  }

  // Determine available lines for selected station
  const getAvailableLinesForNewSegment = (): LineResponse[] => {
    if (!selectedStationId) return []

    const station = stations.find((s) => s.id === selectedStationId)
    if (!station) return []

    // Show all lines serving the selected station
    // The backend will validate if the route is physically possible
    return getLinesForStation(station.tfl_id)
  }

  const availableStations = getAvailableStations()
  const availableLines = getAvailableLinesForNewSegment()

  // Auto-select line when only one option is available
  // OR auto-fill from previous segment (current travel line)
  useEffect(() => {
    if (!selectedStationId) return

    // If only one line available, auto-select it
    if (availableLines.length === 1 && !selectedLineId) {
      setSelectedLineId(availableLines[0].id)
      return
    }

    // If this is not the first segment, auto-fill with the previous segment's line
    // (the line we're currently traveling on)
    if (localSegments.length > 0 && !selectedLineId) {
      const lastSegment = localSegments[localSegments.length - 1]
      // Only auto-fill if previous segment has a line_id (it might be null if it was a destination)
      if (lastSegment.line_id) {
        setSelectedLineId(lastSegment.line_id)
      }
    }
  }, [selectedStationId, availableLines, selectedLineId, localSegments])

  const handleAddSegment = () => {
    if (!selectedStationId) return

    // Auto-fill line_id from previous segment if not explicitly selected
    let finalLineId = selectedLineId
    if (!finalLineId && localSegments.length > 0) {
      const lastSegmentLine = localSegments[localSegments.length - 1].line_id
      // Only use last segment's line if it's not null
      if (lastSegmentLine) {
        finalLineId = lastSegmentLine
      }
    }

    if (!finalLineId) {
      setError('Please select a line for the first station')
      return
    }

    // Check for duplicate stations (acyclic enforcement)
    const isDuplicate = localSegments.some((seg) => seg.station_id === selectedStationId)
    if (isDuplicate) {
      const station = stations.find((s) => s.id === selectedStationId)
      setError(
        `This station (${station?.name || 'Unknown'}) is already in your route. Routes cannot visit the same station twice.`
      )
      return
    }

    // Check max segments limit
    if (localSegments.length >= MAX_ROUTE_SEGMENTS) {
      setError(`Maximum ${MAX_ROUTE_SEGMENTS} segments allowed per route.`)
      return
    }

    const newSegment: SegmentRequest = {
      sequence: localSegments.length,
      station_id: selectedStationId,
      line_id: finalLineId,
    }

    setLocalSegments([...localSegments, newSegment])
    setSelectedStationId(undefined)
    setSelectedLineId(undefined)
    setError(null)
  }

  const handleDeleteSegment = (sequence: number) => {
    // Remove segment and resequence
    const updatedSegments = localSegments
      .filter((seg) => seg.sequence !== sequence)
      .map((seg, index) => ({ ...seg, sequence: index }))

    setLocalSegments(updatedSegments)
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

      // Set last segment's line_id to null (destination has no outgoing line)
      const segmentsToSave = localSegments.map((seg, index) =>
        index === localSegments.length - 1 ? { ...seg, line_id: null } : seg
      )

      // Validate route
      const validation = await onValidate(segmentsToSave)
      if (!validation.valid) {
        setError(validation.message)
        return
      }

      // Save segments
      await onSave(segmentsToSave)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save segments')
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
    setSelectedStationId(undefined)
    setSelectedLineId(undefined)
    setError(null)
    onCancel()
  }

  // Can add segment if station is selected
  // Line will auto-fill from previous segment or be auto-selected if only one option
  const canAddSegment = selectedStationId && localSegments.length < MAX_ROUTE_SEGMENTS
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

  return (
    <div className="space-y-6">
      {/* Instructions */}
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {localSegments.length === 0
            ? 'Select your starting station and line to begin your route.'
            : hasMaxSegments
              ? `Maximum ${MAX_ROUTE_SEGMENTS} segments reached. Save your route or remove segments to continue.`
              : 'Add the next station. The line will auto-fill from your current travel line. Change it only if you need to switch lines at this station.'}
        </AlertDescription>
      </Alert>

      {/* Segment List */}
      <div>
        <h3 className="mb-3 text-sm font-medium">Route Path</h3>
        <SegmentList
          segments={displaySegments}
          lines={lines}
          stations={stations}
          onDeleteSegment={handleDeleteSegment}
        />
      </div>

      {/* Add Segment Form */}
      <Card className="p-4">
        <h3 className="mb-4 text-sm font-medium">
          Add {localSegments.length === 0 ? 'Start' : 'Next'} Station
        </h3>
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="station-select">Station</Label>
              <StationCombobox
                stations={availableStations}
                value={selectedStationId}
                onChange={(stationId) => {
                  setSelectedStationId(stationId)
                  setSelectedLineId(undefined) // Reset line when station changes
                }}
                placeholder={
                  hasMaxSegments
                    ? 'Maximum segments reached'
                    : availableStations.length === 0
                      ? 'No stations available'
                      : 'Select station...'
                }
                disabled={hasMaxSegments || availableStations.length === 0}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="line-select">
                Line{localSegments.length > 0 ? ' (optional - auto-fills from current line)' : ''}
              </Label>
              <LineSelect
                lines={availableLines}
                value={selectedLineId}
                onChange={setSelectedLineId}
                placeholder={
                  hasMaxSegments
                    ? 'Maximum segments reached'
                    : availableLines.length === 0
                      ? 'Select station first'
                      : localSegments.length > 0
                        ? 'Auto-filled (change if needed)'
                        : 'Select line...'
                }
                disabled={hasMaxSegments || !selectedStationId || availableLines.length === 0}
              />
            </div>
          </div>

          <Button onClick={handleAddSegment} disabled={!canAddSegment} className="w-full">
            <Plus className="mr-2 h-4 w-4" />
            Add Segment
          </Button>
        </div>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
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
