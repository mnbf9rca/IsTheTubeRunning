/**
 * Type definitions for ScheduleGrid state management
 *
 * This module provides shared types for the ScheduleGrid component's state,
 * grid selection representation, and related data structures. These types support
 * the extraction of validation and business logic into pure, testable functions.
 *
 * @see ADR 11: Frontend State Management Pattern
 */

import type { ScheduleResponse, CreateScheduleRequest } from '@/types'

/**
 * Days of the week as used by the API
 *
 * These match the backend day codes in UserRouteSchedule model
 */
export const DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'] as const
export type DayCode = (typeof DAYS)[number]

/**
 * Display labels for days of the week (short form)
 */
export const DAY_LABELS: Record<DayCode, string> = {
  MON: 'Mon',
  TUE: 'Tue',
  WED: 'Wed',
  THU: 'Thu',
  FRI: 'Fri',
  SAT: 'Sat',
  SUN: 'Sun',
}

/**
 * Time slot index representing 15-minute intervals
 *
 * - 0 = 00:00
 * - 1 = 00:15
 * - 2 = 00:30
 * - 3 = 00:45
 * - 4 = 01:00
 * - ...
 * - 95 = 23:45
 *
 * Total of 96 slots per day (24 hours × 4 slots/hour)
 */
export type TimeSlotIndex = number // 0-95

/**
 * Number of 15-minute time slots in a day
 */
export const SLOTS_PER_DAY = 96

/**
 * Number of minutes per time slot
 */
export const MINUTES_PER_SLOT = 15

/**
 * Identifier for a single cell in the grid
 */
export interface CellId {
  /** Day of the week */
  day: DayCode
  /** Time slot index (0-95) */
  slot: TimeSlotIndex
}

/**
 * Grid selection state
 *
 * Stores selected cells as a Set of string keys for O(1) lookups.
 * Each key is formatted as "DAY:SLOT" (e.g., "MON:0", "TUE:48")
 *
 * Using a Set rather than a 2D array provides:
 * - Efficient membership testing
 * - Immutable update patterns
 * - Sparse storage (only selected cells consume memory)
 */
export type GridSelection = Set<string>

/**
 * Create a cell key from day and slot
 *
 * @param day Day of the week
 * @param slot Time slot index (0-95)
 * @returns String key "DAY:SLOT"
 *
 * @example
 * cellKey('MON', 0) // => 'MON:0'
 * cellKey('FRI', 48) // => 'FRI:48'
 */
export function cellKey(day: DayCode, slot: TimeSlotIndex): string {
  return `${day}:${slot}`
}

/**
 * Parse a cell key back into day and slot
 *
 * @param key Cell key string "DAY:SLOT"
 * @returns CellId object with day and slot
 * @throws Error if key format is invalid
 *
 * @example
 * parseKey('MON:0') // => { day: 'MON', slot: 0 }
 * parseKey('FRI:48') // => { day: 'FRI', slot: 48 }
 */
export function parseKey(key: string): CellId {
  const [day, slotStr] = key.split(':')
  const slot = parseInt(slotStr, 10)

  if (!DAYS.includes(day as DayCode)) {
    throw new Error(`Invalid day code in key: ${day}`)
  }

  if (isNaN(slot) || slot < 0 || slot >= SLOTS_PER_DAY) {
    throw new Error(`Invalid slot index in key: ${slotStr}`)
  }

  return { day: day as DayCode, slot }
}

/**
 * Validation result (discriminated union)
 *
 * This pattern makes it easy to check validation results and handle
 * errors consistently throughout the component.
 *
 * @example
 * ```typescript
 * const result = validateNotEmpty(selection)
 * if (!result.valid) {
 *   setError(result.error)
 *   return
 * }
 * // Continue with valid selection...
 * ```
 */
export type ValidationResult = { valid: true } | { valid: false; error: string }

/**
 * Contiguous time block for a single day
 *
 * Represents a continuous range of selected time slots on one day.
 * Used as an intermediate representation when converting grid selection
 * to API schedule format.
 */
export interface TimeBlock {
  /** Day of the week */
  day: DayCode
  /** Start slot index (inclusive) */
  startSlot: TimeSlotIndex
  /** End slot index (exclusive) */
  endSlot: TimeSlotIndex
}

/**
 * Re-export schedule types from API for convenience
 */
export type { ScheduleResponse, CreateScheduleRequest }
