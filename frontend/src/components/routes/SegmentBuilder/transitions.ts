/**
 * Pure state transition functions for SegmentBuilder state machine
 *
 * This module provides pure functions that define all valid state transitions
 * in the segment building workflow. Each function returns a complete new state
 * object, making transitions explicit, testable, and easy to reason about.
 *
 * **Design principles:**
 * - Pure functions: same input → same output, no side effects
 * - Complete state: each function returns all 5 core state fields
 * - Explicit transitions: no hidden state dependencies
 * - Separation of concerns: core state machine logic only (no UI state like isSaving)
 *
 * **State machine flow:**
 * ```
 * select-station ←→ select-line → select-next-station → choose-action
 *      ↑                                                        ↓
 *      └────────────────────────────────────────────────────────
 * ```
 *
 * @see ADR 11: Frontend State Management Pattern - Pure Function Architecture
 * @see Issue #97: Extract State Machine Logic from SegmentBuilder
 */

import type { StationResponse, LineResponse } from '@/lib/api'
import type { CoreSegmentBuilderState, Step } from './types'

/**
 * Transitions to initial state (select station)
 *
 * **Use when:**
 * - Starting a new route
 * - Canceling current operation
 * - Resetting after completing destination
 *
 * @returns Complete initial state with all fields reset
 *
 * @example
 * ```typescript
 * const handleCancel = () => {
 *   const newState = transitionToSelectStation()
 *   applyTransition(newState)
 * }
 * ```
 */
export function transitionToSelectStation(): CoreSegmentBuilderState {
  return {
    currentStation: null,
    selectedLine: null,
    nextStation: null,
    step: 'select-station',
    error: null,
  }
}

/**
 * Transitions to select line step
 *
 * **Use when:**
 * - Station selected that has multiple lines
 * - User needs to choose which line to travel on
 *
 * @param currentStation - Station that was selected
 * @returns State ready for line selection
 *
 * @example
 * ```typescript
 * if (availableLines.length > 1) {
 *   const newState = transitionToSelectLine(selectedStation)
 *   applyTransition(newState)
 * }
 * ```
 */
export function transitionToSelectLine(currentStation: StationResponse): CoreSegmentBuilderState {
  return {
    currentStation,
    selectedLine: null,
    nextStation: null,
    step: 'select-line',
    error: null,
  }
}

/**
 * Transitions to select next station step
 *
 * **Use when:**
 * - Line selected (or auto-selected if only one line)
 * - Ready to pick the next station on this line
 *
 * @param currentStation - Current station user is at
 * @param selectedLine - Line to travel on
 * @returns State ready for next station selection
 *
 * @example
 * ```typescript
 * const handleLineClick = (line: LineResponse) => {
 *   const newState = transitionToSelectNextStation(currentStation, line)
 *   applyTransition(newState)
 * }
 * ```
 */
export function transitionToSelectNextStation(
  currentStation: StationResponse,
  selectedLine: LineResponse
): CoreSegmentBuilderState {
  return {
    currentStation,
    selectedLine,
    nextStation: null,
    step: 'select-next-station',
    error: null,
  }
}

/**
 * Transitions to choose action step
 *
 * **Use when:**
 * - Next station selected
 * - User needs to choose: continue journey or mark as destination
 *
 * @param currentStation - Current station
 * @param selectedLine - Current line
 * @param nextStation - Next station selected
 * @returns State ready for action choice
 *
 * @example
 * ```typescript
 * const handleNextStationSelect = (station: StationResponse) => {
 *   const newState = transitionToChooseAction(currentStation, selectedLine, station)
 *   applyTransition(newState)
 * }
 * ```
 */
export function transitionToChooseAction(
  currentStation: StationResponse,
  selectedLine: LineResponse,
  nextStation: StationResponse
): CoreSegmentBuilderState {
  return {
    currentStation,
    selectedLine,
    nextStation,
    step: 'choose-action',
    error: null,
  }
}

/**
 * Transitions back from choose-action to select-next-station
 *
 * **Use when:**
 * - User clicks "Back" button from choose-action step
 * - Allows user to select a different next station
 *
 * @param currentStation - Current station to keep
 * @param selectedLine - Current line to keep
 * @returns State ready to select a different next station
 *
 * @example
 * ```typescript
 * const handleBackFromChooseAction = () => {
 *   const newState = transitionBackFromChooseAction(currentStation, selectedLine)
 *   applyTransition(newState)
 * }
 * ```
 */
export function transitionBackFromChooseAction(
  currentStation: StationResponse,
  selectedLine: LineResponse
): CoreSegmentBuilderState {
  return {
    currentStation,
    selectedLine,
    nextStation: null,
    step: 'select-next-station',
    error: null,
  }
}

/**
 * Transitions to resume building from existing segments
 *
 * **Use when:**
 * - Editing an existing route
 * - After deleting a segment (resume from truncation point)
 * - Resuming after clearing destination marker
 *
 * If resume context is null (empty route), resets to initial state.
 *
 * @param resumeStation - Station to resume from (from computeResumeState or DeletionResult)
 * @param resumeLine - Line to resume on (from computeResumeState or DeletionResult)
 * @returns State ready to continue building from resume point
 *
 * @example
 * ```typescript
 * const handleDeleteSegment = (index: number) => {
 *   const result = deleteSegmentAndResequence(index, segments, stations, lines)
 *   setLocalSegments(result.segments)
 *
 *   const newState = transitionToResumeFromSegments(
 *     result.resumeFrom.station,
 *     result.resumeFrom.line
 *   )
 *   applyTransition(newState)
 * }
 * ```
 */
export function transitionToResumeFromSegments(
  resumeStation: StationResponse | null,
  resumeLine: LineResponse | null
): CoreSegmentBuilderState {
  if (!resumeStation || !resumeLine) {
    return transitionToSelectStation()
  }

  return transitionToSelectNextStation(resumeStation, resumeLine)
}

/**
 * Computes next state after station selection based on available lines
 *
 * **Use when:**
 * - Station selected, need to determine next step automatically
 * - Implements auto-advance logic based on line count
 *
 * **Logic:**
 * - 0 lines: Error state (station has no lines)
 * - 1 line: Auto-select line and advance to select-next-station
 * - 2+ lines: Advance to select-line (user must choose)
 *
 * @param station - Station that was selected
 * @param availableLines - Lines available at this station
 * @returns Next state based on line count
 *
 * @example
 * ```typescript
 * const handleStationSelect = (station: StationResponse) => {
 *   const linesAtStation = lines.filter(l => station.lines.includes(l.tfl_id))
 *   const newState = computeStateAfterStationSelect(station, linesAtStation)
 *   applyTransition(newState)
 * }
 * ```
 */
export function computeStateAfterStationSelect(
  station: StationResponse,
  availableLines: LineResponse[]
): CoreSegmentBuilderState {
  if (availableLines.length === 0) {
    return transitionWithError(
      transitionToSelectLine(station),
      'Selected station has no lines available'
    )
  }

  if (availableLines.length === 1) {
    // Auto-select the only line
    return transitionToSelectNextStation(station, availableLines[0])
  }

  // Multiple lines - user must choose
  return transitionToSelectLine(station)
}

/**
 * Computes next state after segments are updated
 *
 * **Use when:**
 * - Segments change (continue, destination, delete)
 * - Need to determine appropriate next state
 *
 * **Logic:**
 * - At choose-action with segments: Stay at choose-action
 * - Has segments + current/selected set: Transition to select-next-station
 * - No segments: Reset to initial state
 *
 * This implements the "auto-advance" logic after segment operations.
 *
 * @param currentState - Current state before segment update
 * @param hasSegments - Whether route has any segments after update
 * @returns Next state based on segment presence
 *
 * @example
 * ```typescript
 * useEffect(() => {
 *   const newState = computeStateAfterSegmentUpdate(
 *     { currentStation, selectedLine, nextStation, step, error },
 *     localSegments.length > 0
 *   )
 *   applyTransition(newState)
 * }, [localSegments.length])
 * ```
 */
export function computeStateAfterSegmentUpdate(
  currentState: CoreSegmentBuilderState,
  hasSegments: boolean
): CoreSegmentBuilderState {
  // If we're at choose-action and have segments, stay there
  if (currentState.step === 'choose-action' && hasSegments) {
    return currentState
  }

  // If we have segments and current/selected are set, transition to next station
  if (hasSegments && currentState.currentStation && currentState.selectedLine) {
    return transitionToSelectNextStation(currentState.currentStation, currentState.selectedLine)
  }

  // Otherwise, reset to initial state
  return transitionToSelectStation()
}

/**
 * Transitions to error state (preserves current state, adds error)
 *
 * **Use when:**
 * - Validation fails
 * - API error occurs during state transition
 * - Need to show error without changing current step
 *
 * @param currentState - Current state to preserve
 * @param error - Error message to display
 * @returns State with error message added
 *
 * @example
 * ```typescript
 * const validation = validateNotDuplicate(station, segments)
 * if (!validation.valid) {
 *   const newState = transitionWithError(currentState, validation.error)
 *   applyTransition(newState)
 *   return
 * }
 * ```
 */
export function transitionWithError(
  currentState: CoreSegmentBuilderState,
  error: string
): CoreSegmentBuilderState {
  return {
    ...currentState,
    error,
  }
}

/**
 * Clears error from current state
 *
 * **Use when:**
 * - User takes action after error (retry, select different option)
 * - Dismissing error message
 *
 * @param currentState - Current state with possible error
 * @returns State with error cleared
 *
 * @example
 * ```typescript
 * const handleStationSelect = (station: StationResponse) => {
 *   // Clear any previous errors
 *   const stateWithoutError = transitionClearError(currentState)
 *   // ... continue with validation and transition
 * }
 * ```
 */
export function transitionClearError(
  currentState: CoreSegmentBuilderState
): CoreSegmentBuilderState {
  return {
    ...currentState,
    error: null,
  }
}

/**
 * Validates that a state transition is allowed
 *
 * **Use for:**
 * - Debugging state machine issues
 * - Runtime invariant checking in development
 * - Testing state machine completeness
 *
 * @param from - Current step
 * @param to - Target step
 * @returns true if transition is valid, false otherwise
 *
 * @example
 * ```typescript
 * if (process.env.NODE_ENV === 'development') {
 *   if (!isValidTransition(currentState.step, newState.step)) {
 *     console.warn('Invalid transition detected', currentState.step, '->', newState.step)
 *   }
 * }
 * ```
 */
export function isValidTransition(from: Step, to: Step): boolean {
  const validTransitions: Record<Step, Step[]> = {
    'select-station': ['select-line', 'select-next-station'],
    'select-line': ['select-next-station'],
    'select-next-station': ['choose-action'],
    'choose-action': ['select-next-station', 'select-station'],
  }

  return validTransitions[from].includes(to)
}

/**
 * Logs state transition (useful for debugging)
 *
 * **Use when:**
 * - Debugging state machine behavior
 * - Tracking down unexpected state changes
 * - Understanding transition flow during development
 *
 * Only logs in development mode. No-op in production.
 *
 * @param from - Previous state
 * @param to - New state
 * @param action - Description of action that caused transition
 *
 * @example
 * ```typescript
 * const applyTransition = (newState: CoreSegmentBuilderState) => {
 *   logTransition(
 *     { currentStation, selectedLine, nextStation, step, error },
 *     newState,
 *     'handleStationSelect'
 *   )
 *   setCurrentStation(newState.currentStation)
 *   setSelectedLine(newState.selectedLine)
 *   // ...
 * }
 * ```
 */
export function logTransition(
  from: CoreSegmentBuilderState,
  to: CoreSegmentBuilderState,
  action: string
): void {
  if (import.meta.env.DEV) {
    console.log('[SegmentBuilder Transition]', {
      action,
      from: {
        step: from.step,
        currentStation: from.currentStation?.name,
        selectedLine: from.selectedLine?.name,
        nextStation: from.nextStation?.name,
        hasError: !!from.error,
      },
      to: {
        step: to.step,
        currentStation: to.currentStation?.name,
        selectedLine: to.selectedLine?.name,
        nextStation: to.nextStation?.name,
        hasError: !!to.error,
      },
    })
  }
}
