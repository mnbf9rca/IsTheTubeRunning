/**
 * Custom hook for SegmentBuilder state management
 *
 * This hook consolidates all state management logic for the SegmentBuilder component,
 * including state declarations, transitions, validation, and segment building.
 * The component using this hook focuses purely on rendering and save operations.
 *
 * @see Issue #98: Integrate Pure Functions & Rewrite SegmentBuilder Component
 * @see ADR 11: Frontend State Management Pattern
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import type {
  SegmentResponse,
  LineResponse,
  StationResponse,
  SegmentRequest,
} from '../../../../lib/api'
import type { Step, CoreSegmentBuilderState } from '../types'
import {
  MAX_ROUTE_SEGMENTS,
  validateNotDuplicate,
  validateMaxSegments,
  validateCanDeleteSegment,
  calculateAdditionalSegments,
} from '../validation'
import {
  buildSegmentsForContinue,
  buildSegmentsForDestination,
  deleteSegmentAndResequence,
  removeDestinationMarker,
} from '../segments'
import {
  transitionToSelectStation,
  transitionToSelectNextStation,
  transitionToChooseAction,
  transitionBackFromChooseAction,
  transitionToResumeFromSegments,
  computeStateAfterStationSelect,
} from '../transitions'
import { sortLines } from '../../../../lib/tfl-colors'

export interface UseSegmentBuilderStateParams {
  /**
   * Initial segments (from server) to load in edit mode
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
}

export interface UseSegmentBuilderStateReturn {
  // State
  localSegments: SegmentRequest[]
  currentStation: StationResponse | null
  selectedLine: LineResponse | null
  nextStation: StationResponse | null
  step: Step
  error: string | null

  // Setters (for save operation in component)
  setError: React.Dispatch<React.SetStateAction<string | null>>

  // Handlers
  handleStationSelect: (stationId: string | undefined) => void
  handleLineClick: (line: LineResponse) => void
  handleNextStationSelect: (stationId: string | undefined) => void
  handleContinueJourney: (line: LineResponse) => void
  handleMarkAsDestination: () => { segments: SegmentRequest[]; error: string | null }
  handleBackFromChooseAction: () => void
  handleEditRoute: () => void
  handleDeleteSegment: (sequence: number) => void
  handleCancel: (onCancel: () => void) => void

  // Computed values
  getCurrentStationLines: () => LineResponse[]
  getNextStationLines: () => LineResponse[]
  hasMaxSegments: boolean
  isRouteComplete: boolean
}

/**
 * Custom hook for managing SegmentBuilder state
 *
 * Consolidates all state management, validation, and segment building logic.
 * Returns state, handlers, and computed values for the component to use.
 *
 * @example
 * ```typescript
 * const {
 *   localSegments,
 *   currentStation,
 *   handleStationSelect,
 *   isRouteComplete
 * } = useSegmentBuilderState({
 *   initialSegments: route.segments,
 *   lines,
 *   stations,
 *   getLinesForStation
 * })
 * ```
 */
export function useSegmentBuilderState({
  initialSegments,
  lines,
  stations,
  getLinesForStation,
}: UseSegmentBuilderStateParams): UseSegmentBuilderStateReturn {
  // ===== State Declarations =====

  // Local state for segments being built
  const [localSegments, setLocalSegments] = useState<SegmentRequest[]>(
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    initialSegments.map(({ id: _id, ...rest }) => rest)
  )

  // State for building current segment
  const [currentStation, setCurrentStation] = useState<StationResponse | null>(null)
  const [selectedLine, setSelectedLine] = useState<LineResponse | null>(null)
  const [nextStation, setNextStation] = useState<StationResponse | null>(null)

  // UI state
  const [step, setStep] = useState<Step>('select-station')
  const [error, setError] = useState<string | null>(null)

  // ===== Helper Functions =====

  /**
   * Helper to apply a state transition to component state
   * Takes a CoreSegmentBuilderState and applies it to individual setters
   */
  const applyTransition = useCallback((newState: CoreSegmentBuilderState) => {
    setCurrentStation(newState.currentStation)
    setSelectedLine(newState.selectedLine)
    setNextStation(newState.nextStation)
    setStep(newState.step)
    setError(newState.error)
  }, [])

  // ===== Computed Values =====

  /**
   * Get available lines for current station (sorted alphabetically)
   */
  const getCurrentStationLines = useCallback((): LineResponse[] => {
    if (!currentStation) return []
    const stationLines = getLinesForStation(currentStation.tfl_id)
    return sortLines(stationLines)
  }, [currentStation, getLinesForStation])

  /**
   * Get available lines for next station (sorted alphabetically)
   */
  const getNextStationLines = useCallback((): LineResponse[] => {
    if (!nextStation) return []
    const stationLines = getLinesForStation(nextStation.tfl_id)
    return sortLines(stationLines)
  }, [nextStation, getLinesForStation])

  /**
   * Check if route has reached maximum segments
   */
  const hasMaxSegments = useMemo(
    () => localSegments.length >= MAX_ROUTE_SEGMENTS,
    [localSegments.length]
  )

  /**
   * Check if route is complete (has destination segment with line_tfl_id: null)
   * Route is not considered "complete" when in editing mode
   */
  const isRouteComplete = useMemo(
    () =>
      localSegments.length >= 2 &&
      localSegments[localSegments.length - 1].line_tfl_id === null &&
      step !== 'choose-action' &&
      !(step === 'select-next-station' && currentStation) &&
      !nextStation,
    [localSegments, step, currentStation, nextStation]
  )

  // ===== Effects =====

  /**
   * Auto-advance logic when station selected
   * If station has only 1 line, auto-advance to select-next-station
   * If station has 2+ lines, advance to select-line
   *
   * Note: This intentionally calls setState in an effect for auto-advance UX.
   * This is a valid use case for synchronous state updates in effects.
   */
  useEffect(() => {
    if (step === 'select-station' && currentStation) {
      // Inline the line fetching logic to avoid unnecessary dependencies
      const stationLines = getLinesForStation(currentStation.tfl_id)
      const sortedLines = sortLines(stationLines)
      const newState = computeStateAfterStationSelect(currentStation, sortedLines)
      applyTransition(newState)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStation, step, getLinesForStation])

  // ===== Handlers =====

  /**
   * Handle station selection (starting or continuing)
   */
  const handleStationSelect = useCallback(
    (stationId: string | undefined) => {
      if (!stationId) {
        const newState = transitionToSelectStation()
        applyTransition(newState)
        return
      }

      const station = stations.find((s) => s.id === stationId)
      if (station) {
        setCurrentStation(station)
        setError(null)
        // Auto-advance logic will trigger in useEffect
      }
    },
    [stations, applyTransition]
  )

  /**
   * Handle line selection (when station has multiple lines)
   */
  const handleLineClick = useCallback(
    (line: LineResponse) => {
      if (!currentStation) return
      const newState = transitionToSelectNextStation(currentStation, line)
      applyTransition(newState)
    },
    [currentStation, applyTransition]
  )

  /**
   * Handle next station selection
   */
  const handleNextStationSelect = useCallback(
    (stationId: string | undefined) => {
      // Guard clause: missing required state (shouldn't happen in normal operation)
      if (!currentStation || !selectedLine) return

      // If combobox cleared, go back to select-next-station step
      if (!stationId) {
        const newState = transitionBackFromChooseAction(currentStation, selectedLine)
        applyTransition(newState)
        return
      }

      const station = stations.find((s) => s.id === stationId)
      if (!station) {
        // Station lookup failed - stay in current state with warning
        if (import.meta.env.DEV) {
          console.warn('[useSegmentBuilderState] Station not found:', stationId)
        }
        return
      }

      const newState = transitionToChooseAction(currentStation, selectedLine, station)
      applyTransition(newState)
    },
    [currentStation, selectedLine, stations, applyTransition]
  )

  /**
   * Handle continue journey (add segments and reset for next)
   */
  const handleContinueJourney = useCallback(
    (line: LineResponse) => {
      if (!currentStation || !selectedLine || !nextStation) return

      // Clear any previous errors
      setError(null)

      // Check for duplicate stations (acyclic enforcement)
      // Allow currentStation if it's the last segment (junction we're continuing from)
      const validation = validateNotDuplicate(currentStation, localSegments, { allowLast: true })
      if (!validation.valid) {
        setError(validation.error)
        return
      }

      // Calculate how many segments will be added based on junction scenario
      const additionalSegments = calculateAdditionalSegments(
        currentStation,
        selectedLine,
        line,
        localSegments
      )

      // Check max segments limit before building
      const maxSegmentsValidation = validateMaxSegments(localSegments.length, additionalSegments)
      if (!maxSegmentsValidation.valid) {
        setError(maxSegmentsValidation.error)
        return
      }

      // If changing lines, validate nextStation is not a duplicate
      const isChangingLines = selectedLine.tfl_id !== line.tfl_id
      if (isChangingLines) {
        const nextValidation = validateNotDuplicate(nextStation, localSegments)
        if (!nextValidation.valid) {
          setError(nextValidation.error)
          return
        }
      }

      // Build segments using pure function
      const updatedSegments = buildSegmentsForContinue({
        currentStation,
        selectedLine,
        nextStation,
        currentSegments: localSegments,
        continueLine: line,
      })

      setLocalSegments(updatedSegments)

      // Set up for next segment using transition function
      const newState = transitionToSelectNextStation(nextStation, line)
      applyTransition(newState)
    },
    [currentStation, selectedLine, nextStation, localSegments, applyTransition]
  )

  /**
   * Handle mark as destination
   * Builds final segments and returns them along with any validation error.
   *
   * @returns Object containing:
   *   - segments: The final segments (unchanged if validation failed)
   *   - error: Validation error message or null if successful
   *
   * Note: This function still updates local state (segments and UI state) even though
   * it returns values. The return values are for the component's save operation to
   * check before proceeding with async save.
   */
  const handleMarkAsDestination = useCallback((): {
    segments: SegmentRequest[]
    error: string | null
  } => {
    if (!currentStation || !selectedLine || !nextStation) {
      return { segments: localSegments, error: null }
    }

    // Clear any previous errors
    setError(null)

    // Check for duplicate stations
    // Allow currentStation if it's the last segment (junction we're continuing from)
    const currentValidation = validateNotDuplicate(currentStation, localSegments, {
      allowLast: true,
    })
    if (!currentValidation.valid) {
      setError(currentValidation.error)
      return { segments: localSegments, error: currentValidation.error }
    }

    const nextValidation = validateNotDuplicate(nextStation, localSegments)
    if (!nextValidation.valid) {
      setError(nextValidation.error)
      return { segments: localSegments, error: nextValidation.error }
    }

    // Calculate how many segments will be added (destination always uses same line)
    const additionalSegments = calculateAdditionalSegments(
      currentStation,
      selectedLine,
      selectedLine, // Destination doesn't change lines
      localSegments
    )
    const maxSegmentsValidation = validateMaxSegments(localSegments.length, additionalSegments)
    if (!maxSegmentsValidation.valid) {
      setError(maxSegmentsValidation.error)
      return { segments: localSegments, error: maxSegmentsValidation.error }
    }

    // Build final segments using pure function
    const finalSegments = buildSegmentsForDestination({
      currentStation,
      selectedLine,
      destinationStation: nextStation,
      currentSegments: localSegments,
    })

    // Update local segments
    setLocalSegments(finalSegments)

    // Reset UI state using transition function
    const newState = transitionToSelectStation()
    applyTransition(newState)

    return { segments: finalSegments, error: null }
  }, [currentStation, selectedLine, nextStation, localSegments, applyTransition])

  /**
   * Go back from choose-action step to select-next-station
   * Allows user to re-select the next station if they made a mistake
   */
  const handleBackFromChooseAction = useCallback(() => {
    if (!currentStation || !selectedLine) return

    const newState = transitionBackFromChooseAction(currentStation, selectedLine)
    applyTransition(newState)
  }, [currentStation, selectedLine, applyTransition])

  /**
   * Enter edit mode for a completed route
   * Removes the destination marker and positions the user as if they just selected
   * the destination as the next station, allowing them to continue the route or
   * mark it as destination again.
   */
  const handleEditRoute = useCallback(() => {
    // Clear any stale errors from previous operations
    setError(null)

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
      // CRITICAL: Remove the destination marker BEFORE transitioning
      // This makes prevStation the last segment, so handleContinueJourney's
      // validateNotDuplicate(currentStation, segments, { allowLast: true })
      // will pass (prevStation is now the last segment)
      const segmentsWithoutDestination = removeDestinationMarker(localSegments)
      setLocalSegments(segmentsWithoutDestination)

      // Set up state as if we just selected the destination as the "next station"
      // This shows line buttons for interchanges + "Mark as Destination" button
      // With the destination marker removed, prevStation is now the last segment,
      // so it won't trigger duplicate errors when continuing
      const newState = transitionToChooseAction(prevStation, arrivalLine, destinationStation)
      applyTransition(newState)
    }
  }, [localSegments, stations, lines, applyTransition])

  /**
   * Handle segment deletion
   * Deletes segment, resequences remaining segments, and resumes from truncation point
   */
  const handleDeleteSegment = useCallback(
    (sequence: number) => {
      // Clear any previous errors
      setError(null)

      // Validate deletion (prevents deleting destination, validates bounds)
      const deleteValidation = validateCanDeleteSegment(sequence, localSegments)
      if (!deleteValidation.valid) {
        setError(deleteValidation.error)
        return
      }

      // Delete segment and get truncation context using enhanced pure function
      const deletionResult = deleteSegmentAndResequence(sequence, localSegments, stations, lines)

      setLocalSegments(deletionResult.segments)

      // Resume from truncation point using the provided context
      const newState = transitionToResumeFromSegments(
        deletionResult.resumeFrom.station,
        deletionResult.resumeFrom.line
      )
      applyTransition(newState)
    },
    [localSegments, stations, lines, applyTransition]
  )

  /**
   * Handle cancel
   * Resets to initial segments and clears all state, then invokes the provided callback.
   *
   * @param onCancel - Callback to invoke after state is reset (e.g., close modal, navigate away)
   *
   * Note: This hook intentionally invokes the callback directly for simplicity.
   * The component passes its cleanup/navigation logic via this parameter.
   */
  const handleCancel = useCallback(
    (onCancel: () => void) => {
      setLocalSegments(
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        initialSegments.map(({ id: _id, ...rest }) => rest)
      )

      // Reset state using transition function
      const newState = transitionToSelectStation()
      applyTransition(newState)

      onCancel()
    },
    [initialSegments, applyTransition]
  )

  // ===== Return =====

  return {
    // State
    localSegments,
    currentStation,
    selectedLine,
    nextStation,
    step,
    error,

    // Setters
    setError,

    // Handlers
    handleStationSelect,
    handleLineClick,
    handleNextStationSelect,
    handleContinueJourney,
    handleMarkAsDestination,
    handleBackFromChooseAction,
    handleEditRoute,
    handleDeleteSegment,
    handleCancel,

    // Computed values
    getCurrentStationLines,
    getNextStationLines,
    hasMaxSegments,
    isRouteComplete,
  }
}
