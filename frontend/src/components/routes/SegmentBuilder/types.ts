/**
 * Type definitions for SegmentBuilder state management
 *
 * This module provides shared types for the SegmentBuilder component's state machine,
 * validation results, and related data structures. These types support the extraction
 * of validation and business logic into pure, testable functions.
 *
 * @see ADR 11: Frontend State Management Pattern
 */

import type { StationResponse, LineResponse, SegmentRequest } from '@/types'

/**
 * State machine step for segment building workflow
 *
 * The segment building process follows a sequential state machine:
 * 1. select-station: User selects a station to add to the route
 * 2. select-line: User selects which line to travel on from the station
 * 3. select-next-station: User selects the next station on the chosen line
 * 4. choose-action: User decides whether to continue journey or mark as destination
 */
export type Step = 'select-station' | 'select-line' | 'select-next-station' | 'choose-action'

/**
 * Result of a validation check
 *
 * This is a discriminated union type that represents either a successful
 * validation (valid: true) or a failed validation (valid: false) with an
 * error message. This pattern makes it easy to check validation results
 * and handle errors consistently.
 *
 * @example
 * ```typescript
 * const result = validateNotDuplicate(station, segments)
 * if (!result.valid) {
 *   setError(result.error)
 *   return
 * }
 * // Continue with valid station...
 * ```
 */
export type ValidationResult = { valid: true } | { valid: false; error: string }

/**
 * Core state machine state (used by pure transition functions)
 *
 * This interface represents only the core state machine logic, excluding
 * UI-specific state like `isSaving` and `saveSuccess`. Transition functions
 * operate on this core state to maintain separation of concerns:
 * - State machine logic is pure and synchronous
 * - UI state is managed by component handlers around async operations
 *
 * This type is used by transition functions in transitions.ts to ensure
 * they remain pure and testable.
 *
 * @see Issue #97: Extract State Machine Logic
 * @see transitions.ts for state transition functions
 */
export interface CoreSegmentBuilderState {
  /** Currently selected station (null when not selected) */
  currentStation: StationResponse | null

  /** Currently selected line for travel (null when not selected) */
  selectedLine: LineResponse | null

  /** Next station selected on the current line (null when not selected) */
  nextStation: StationResponse | null

  /** Current step in the segment building state machine */
  step: Step

  /** Error message to display to user (null when no error) */
  error: string | null
}

/**
 * Complete state for the SegmentBuilder component
 *
 * This interface aggregates all state variables used in the SegmentBuilder,
 * including both core state machine state and UI-specific state.
 *
 * The component uses individual useState hooks for each field. In future
 * refactoring (issue #98), this will be consolidated into a custom hook.
 *
 * @see Issue #96: Extract Segment Building Logic
 * @see Issue #97: Extract State Machine Logic
 * @see Issue #98: Integrate Pure Functions into Custom Hook
 */
export interface SegmentBuilderState {
  /** Currently selected station (null when not selected) */
  currentStation: StationResponse | null

  /** Currently selected line for travel (null when not selected) */
  selectedLine: LineResponse | null

  /** Next station selected on the current line (null when not selected) */
  nextStation: StationResponse | null

  /** Current step in the segment building state machine */
  step: Step

  /** Whether a save operation is in progress */
  isSaving: boolean

  /** Whether the last save operation succeeded */
  saveSuccess: boolean

  /** Error message to display to user (null when no error) */
  error: string | null
}

/**
 * Re-export SegmentRequest from API types for convenience
 *
 * This avoids the need to import from two different places when working
 * with SegmentBuilder types and validation functions.
 *
 * @see ../../../lib/api.ts for the original definition
 */
export type { SegmentRequest }
