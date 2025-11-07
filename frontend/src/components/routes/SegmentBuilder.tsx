import { useState } from 'react'
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
   * Helper function to get next reachable stations
   */
  getNextStations: (currentStationTflId: string, currentLineTflId: string) => StationResponse[]

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
 * 2. Select next station (constrained by network graph)
 * 3. Continue adding stations
 * 4. Validate and save
 *
 * @example
 * <SegmentBuilder
 *   routeId={route.id}
 *   initialSegments={route.segments}
 *   lines={lines}
 *   stations={stations}
 *   getNextStations={getNextStations}
 *   getLinesForStation={getLinesForStation}
 *   getStationByTflId={getStationByTflId}
 *   getLineById={getLineById}
 *   onValidate={validateRoute}
 *   onSave={upsertSegments}
 *   onCancel={() => setEditing(false)}
 * />
 */
export function SegmentBuilder({
  initialSegments,
  lines,
  stations,
  getNextStations,
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

    // Get last segment
    const lastSegment = localSegments[localSegments.length - 1]
    const lastStation = stations.find((s) => s.id === lastSegment.station_id)
    const lastLine = lines.find((l) => l.id === lastSegment.line_id)

    if (!lastStation || !lastLine) return []

    // Get next reachable stations on the last line
    return getNextStations(lastStation.tfl_id, lastLine.tfl_id)
  }

  // Determine available lines for selected station
  const getAvailableLinesForNewSegment = (): LineResponse[] => {
    if (!selectedStationId) return []

    const station = stations.find((s) => s.id === selectedStationId)
    if (!station) return []

    // If this is the first segment, show all lines serving this station
    if (localSegments.length === 0) {
      return getLinesForStation(station.tfl_id)
    }

    // For subsequent segments, constrain to lines that connect from previous station
    const lastSegment = localSegments[localSegments.length - 1]
    const lastStation = stations.find((s) => s.id === lastSegment.station_id)
    const lastLine = lines.find((l) => l.id === lastSegment.line_id)

    if (!lastStation || !lastLine) return []

    // Get connections from last station on last line
    const nextStations = getNextStations(lastStation.tfl_id, lastLine.tfl_id)
    const isReachable = nextStations.some((s) => s.id === selectedStationId)

    if (!isReachable) return []

    // Station is reachable - show all lines serving it
    return getLinesForStation(station.tfl_id)
  }

  const handleAddSegment = () => {
    if (!selectedStationId || !selectedLineId) return

    const newSegment: SegmentRequest = {
      sequence: localSegments.length,
      station_id: selectedStationId,
      line_id: selectedLineId,
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

      // Validate route
      const validation = await onValidate(localSegments)
      if (!validation.valid) {
        setError(validation.message)
        return
      }

      // Save segments
      await onSave(localSegments)
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

  const availableStations = getAvailableStations()
  const availableLines = getAvailableLinesForNewSegment()
  const canAddSegment = selectedStationId && selectedLineId
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
            ? 'Select your starting station, then choose a line. Continue adding stations to build your route.'
            : 'Add the next station on your route. Only stations reachable from the previous station are shown.'}
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
                  availableStations.length === 0 ? 'No stations available' : 'Select station...'
                }
                disabled={availableStations.length === 0}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="line-select">Line</Label>
              <LineSelect
                lines={availableLines}
                value={selectedLineId}
                onChange={setSelectedLineId}
                placeholder={
                  availableLines.length === 0 ? 'Select station first' : 'Select line...'
                }
                disabled={!selectedStationId || availableLines.length === 0}
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
