/**
 * Pure functions for manipulating grid selection state
 *
 * These functions handle all selection operations:
 * - Toggle single cells
 * - Select rectangular ranges (for drag selection)
 * - Bulk operations (select all, clear all)
 *
 * All functions return new Set instances (immutable updates).
 *
 * @see ADR 11: Frontend State Management Pattern
 */

import {
  type GridSelection,
  type CellId,
  type DayCode,
  type TimeSlotIndex,
  DAYS,
  cellKey,
} from './types'

/**
 * Toggle a single cell's selection state
 *
 * If the cell is currently selected, it will be deselected.
 * If the cell is not selected, it will be selected.
 *
 * @param selection Current grid selection
 * @param cell Cell to toggle
 * @returns New grid selection with cell toggled
 *
 * @example
 * const selection = new Set(['MON:0'])
 * toggleCell(selection, { day: 'MON', slot: 0 })
 * // => Set([]) (cell was removed)
 *
 * toggleCell(selection, { day: 'TUE', slot: 5 })
 * // => Set(['MON:0', 'TUE:5']) (cell was added)
 */
export function toggleCell(selection: GridSelection, cell: CellId): GridSelection {
  const newSelection = new Set(selection)
  const key = cellKey(cell.day, cell.slot)

  if (newSelection.has(key)) {
    newSelection.delete(key)
  } else {
    newSelection.add(key)
  }

  return newSelection
}

/**
 * Check if a cell is currently selected
 *
 * @param selection Current grid selection
 * @param cell Cell to check
 * @returns True if cell is selected, false otherwise
 *
 * @example
 * const selection = new Set(['MON:0', 'TUE:5'])
 * isSelected(selection, { day: 'MON', slot: 0 }) // => true
 * isSelected(selection, { day: 'WED', slot: 10 }) // => false
 */
export function isSelected(selection: GridSelection, cell: CellId): boolean {
  return selection.has(cellKey(cell.day, cell.slot))
}

/**
 * Select mode for range selection
 *
 * - 'add': Add all cells in range to selection
 * - 'remove': Remove all cells in range from selection
 * - 'toggle': Toggle each cell in range individually
 */
export type SelectMode = 'add' | 'remove' | 'toggle'

/**
 * Select a rectangular range of cells
 *
 * Used for drag selection. Selects all cells in the rectangular region
 * defined by start and end cells.
 *
 * @param selection Current grid selection
 * @param start Start cell (one corner of rectangle)
 * @param end End cell (opposite corner of rectangle)
 * @param mode Selection mode ('add', 'remove', or 'toggle')
 * @returns New grid selection with range applied
 *
 * @example
 * const selection = new Set()
 * const start = { day: 'MON', slot: 0 }
 * const end = { day: 'TUE', slot: 2 }
 * selectRange(selection, start, end, 'add')
 * // => Set(['MON:0', 'MON:1', 'MON:2', 'TUE:0', 'TUE:1', 'TUE:2'])
 */
export function selectRange(
  selection: GridSelection,
  start: CellId,
  end: CellId,
  mode: SelectMode = 'add'
): GridSelection {
  const newSelection = new Set(selection)

  // Determine day range
  const startDayIndex = DAYS.indexOf(start.day)
  const endDayIndex = DAYS.indexOf(end.day)
  const minDayIndex = Math.min(startDayIndex, endDayIndex)
  const maxDayIndex = Math.max(startDayIndex, endDayIndex)

  // Determine slot range
  const minSlot = Math.min(start.slot, end.slot)
  const maxSlot = Math.max(start.slot, end.slot)

  // Apply operation to all cells in range
  for (let dayIndex = minDayIndex; dayIndex <= maxDayIndex; dayIndex++) {
    const day = DAYS[dayIndex]
    for (let slot = minSlot; slot <= maxSlot; slot++) {
      const key = cellKey(day, slot)

      if (mode === 'add') {
        newSelection.add(key)
      } else if (mode === 'remove') {
        newSelection.delete(key)
      } else if (mode === 'toggle') {
        if (newSelection.has(key)) {
          newSelection.delete(key)
        } else {
          newSelection.add(key)
        }
      }
    }
  }

  return newSelection
}

/**
 * Clear all selections
 *
 * @returns Empty grid selection
 *
 * @example
 * clearSelection() // => Set([])
 */
export function clearSelection(): GridSelection {
  return new Set()
}

/**
 * Select all cells for a specific day
 *
 * @param selection Current grid selection
 * @param day Day to select
 * @returns New grid selection with all cells for day selected
 *
 * @example
 * const selection = new Set()
 * selectDay(selection, 'MON')
 * // => Set(['MON:0', 'MON:1', ..., 'MON:95'])
 */
export function selectDay(selection: GridSelection, day: DayCode): GridSelection {
  const newSelection = new Set(selection)

  for (let slot = 0; slot < 96; slot++) {
    newSelection.add(cellKey(day, slot))
  }

  return newSelection
}

/**
 * Deselect all cells for a specific day
 *
 * @param selection Current grid selection
 * @param day Day to deselect
 * @returns New grid selection with all cells for day removed
 *
 * @example
 * const selection = new Set(['MON:0', 'MON:1', 'TUE:5'])
 * deselectDay(selection, 'MON')
 * // => Set(['TUE:5'])
 */
export function deselectDay(selection: GridSelection, day: DayCode): GridSelection {
  const newSelection = new Set(selection)

  for (let slot = 0; slot < 96; slot++) {
    newSelection.delete(cellKey(day, slot))
  }

  return newSelection
}

/**
 * Select a specific time slot across all days
 *
 * @param selection Current grid selection
 * @param slot Time slot to select
 * @returns New grid selection with slot selected for all days
 *
 * @example
 * const selection = new Set()
 * selectTimeSlot(selection, 48) // 12:00
 * // => Set(['MON:48', 'TUE:48', 'WED:48', 'THU:48', 'FRI:48', 'SAT:48', 'SUN:48'])
 */
export function selectTimeSlot(selection: GridSelection, slot: TimeSlotIndex): GridSelection {
  const newSelection = new Set(selection)

  for (const day of DAYS) {
    newSelection.add(cellKey(day, slot))
  }

  return newSelection
}

/**
 * Deselect a specific time slot across all days
 *
 * @param selection Current grid selection
 * @param slot Time slot to deselect
 * @returns New grid selection with slot removed from all days
 *
 * @example
 * const selection = new Set(['MON:48', 'TUE:48', 'TUE:49'])
 * deselectTimeSlot(selection, 48)
 * // => Set(['TUE:49'])
 */
export function deselectTimeSlot(selection: GridSelection, slot: TimeSlotIndex): GridSelection {
  const newSelection = new Set(selection)

  for (const day of DAYS) {
    newSelection.delete(cellKey(day, slot))
  }

  return newSelection
}

/**
 * Check if an entire day is selected
 *
 * @param selection Current grid selection
 * @param day Day to check
 * @returns True if all slots for the day are selected
 *
 * @example
 * const selection = new Set(['MON:0', 'MON:1', ..., 'MON:95'])
 * isDaySelected(selection, 'MON') // => true
 */
export function isDaySelected(selection: GridSelection, day: DayCode): boolean {
  for (let slot = 0; slot < 96; slot++) {
    if (!selection.has(cellKey(day, slot))) {
      return false
    }
  }
  return true
}

/**
 * Check if a time slot is selected across all days
 *
 * @param selection Current grid selection
 * @param slot Time slot to check
 * @returns True if slot is selected for all days
 *
 * @example
 * const selection = new Set(['MON:48', 'TUE:48', ..., 'SUN:48'])
 * isTimeSlotSelected(selection, 48) // => true
 */
export function isTimeSlotSelected(selection: GridSelection, slot: TimeSlotIndex): boolean {
  for (const day of DAYS) {
    if (!selection.has(cellKey(day, slot))) {
      return false
    }
  }
  return true
}
