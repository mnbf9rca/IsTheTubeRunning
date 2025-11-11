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
  isStationLastInRoute,
} from '../validation'
import { isSameLine } from '../utils'
import {
  buildSegmentsForContinue,
  buildSegmentsForDestination,
  deleteSegmentAndResequence,
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
  handleMarkAsDestination: () => SegmentRequest[]
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
 *   getLinesForStation,
 *   getNextStations
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
      const stationLines = getCurrentStationLines()
      const newState = computeStateAfterStationSelect(currentStation, stationLines)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      applyTransition(newState)
    }
  }, [currentStation, step, getCurrentStationLines, applyTransition])

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

      // Determine how many segments will be added
      const isChangingLines = !isSameLine(line, selectedLine)
      const isCurrentStationLast = isStationLastInRoute(currentStation, localSegments)

      // Calculate actual segments to be added based on junction scenario
      let additionalSegments: number
      if (isCurrentStationLast) {
        // Current station already in route - won't be added again
        additionalSegments = isChangingLines ? 1 : 0
      } else {
        // Current station will be added
        additionalSegments = isChangingLines ? 2 : 1
      }

      // Check max segments limit before building
      const maxSegmentsValidation = validateMaxSegments(localSegments.length, additionalSegments)
      if (!maxSegmentsValidation.valid) {
        setError(maxSegmentsValidation.error)
        return
      }

      // If changing lines, validate nextStation is not a duplicate
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
   * Returns the final segments without saving (component handles save)
   */
  const handleMarkAsDestination = useCallback((): SegmentRequest[] => {
    if (!currentStation || !selectedLine || !nextStation) {
      return localSegments
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
      return localSegments
    }

    const nextValidation = validateNotDuplicate(nextStation, localSegments)
    if (!nextValidation.valid) {
      setError(nextValidation.error)
      return localSegments
    }

    // Check max segments limit (will add 1 or 2 segments depending on whether current is last)
    const isCurrentStationLast = isStationLastInRoute(currentStation, localSegments)
    const additionalSegments = isCurrentStationLast ? 1 : 2
    const maxSegmentsValidation = validateMaxSegments(localSegments.length, additionalSegments)
    if (!maxSegmentsValidation.valid) {
      setError(maxSegmentsValidation.error)
      return localSegments
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

    return finalSegments
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
   * Sets state to show the destination station with action buttons
   */
  const handleEditRoute = useCallback(() => {
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
   * Resets to initial segments and clears all state
   */
  const handleCancel = useCallback(
    (onCancel: () => void) => {
      setLocalSegments(
        initialSegments.map((seg) => ({
          sequence: seg.sequence,
          station_tfl_id: seg.station_tfl_id,
          line_tfl_id: seg.line_tfl_id,
        }))
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
