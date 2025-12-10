/**
 * Pure validation functions for grid selection
 *
 * These functions validate grid selection state and return validation results
 * following the discriminated union pattern.
 *
 * @see ADR 11: Frontend State Management Pattern
 */

import { DAYS, SLOTS_PER_DAY, type GridSelection, type ValidationResult } from './types'

/**
 * Validate that selection is not empty
 *
 * @param selection Grid selection to validate
 * @returns Validation result
 *
 * @example
 * validateNotEmpty(new Set()) // => { valid: false, error: 'Please select at least one time slot' }
 * validateNotEmpty(new Set(['MON:0'])) // => { valid: true }
 */
export function validateNotEmpty(selection: GridSelection): ValidationResult {
  if (selection.size === 0) {
    return { valid: false, error: 'Please select at least one time slot' }
  }
  return { valid: true }
}

/**
 * Validate that selection doesn't exceed maximum number of schedules
 *
 * Since each contiguous block per day becomes a separate schedule,
 * we need to ensure we don't exceed backend limits.
 *
 * Note: This is a soft limit - the backend doesn't enforce a hard limit,
 * but having too many schedules could impact performance.
 *
 * @param selection Grid selection to validate
 * @param maxSchedules Maximum number of schedules allowed (default: 100)
 * @returns Validation result
 *
 * @example
 * const selection = new Set(['MON:0', 'MON:5', 'TUE:10']) // 3 separate blocks
 * validateMaxSchedules(selection, 2) // => { valid: false, error: 'Too many time blocks...' }
 * validateMaxSchedules(selection, 5) // => { valid: true }
 */
export function validateMaxSchedules(
  selection: GridSelection,
  maxSchedules: number = 100
): ValidationResult {
  // Count number of blocks by counting transitions from selected to not-selected
  // This is an approximation - actual block count is calculated in transforms.ts
  // But for validation purposes, this gives us a reasonable upper bound

  let blockCount = 0

  for (const day of DAYS) {
    let inBlock = false
    for (let slot = 0; slot < SLOTS_PER_DAY; slot++) {
      const isSelected = selection.has(`${day}:${slot}`)
      if (isSelected && !inBlock) {
        blockCount++
        inBlock = true
      } else if (!isSelected && inBlock) {
        inBlock = false
      }
    }
  }

  if (blockCount > maxSchedules) {
    return {
      valid: false,
      error: `Too many time blocks selected (${blockCount}). Please limit to ${maxSchedules} blocks or fewer.`,
    }
  }

  return { valid: true }
}

/**
 * Run all validation checks on a selection
 *
 * @param selection Grid selection to validate
 * @param options Validation options
 * @returns Validation result (first failure encountered, or valid)
 *
 * @example
 * validateAll(new Set()) // => { valid: false, error: 'Please select at least one time slot' }
 * validateAll(new Set(['MON:0'])) // => { valid: true }
 */
export function validateAll(
  selection: GridSelection,
  options: { maxSchedules?: number } = {}
): ValidationResult {
  const notEmptyResult = validateNotEmpty(selection)
  if (!notEmptyResult.valid) {
    return notEmptyResult
  }

  const maxSchedulesResult = validateMaxSchedules(selection, options.maxSchedules)
  if (!maxSchedulesResult.valid) {
    return maxSchedulesResult
  }

  return { valid: true }
}
