/**
 * Custom hook for managing schedule grid state
 *
 * This hook integrates the pure functions for grid selection and drag handling.
 * It manages:
 * - Selection state
 * - Drag selection state (start cell, current cell, is dragging)
 * - Event handlers for click and drag interactions
 *
 * @see ADR 11: Frontend State Management Pattern
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import { type GridSelection, type CellId } from '../types'
import { toggleCell, selectRange, isSelected } from '../selection'

export interface UseScheduleGridStateOptions {
  /** Initial selection (e.g., loaded from API) */
  initialSelection?: GridSelection
  /** Callback when selection changes */
  onChange?: (selection: GridSelection) => void
  /** Whether grid is disabled */
  disabled?: boolean
}

export interface UseScheduleGridStateReturn {
  /** Current selection */
  selection: GridSelection

  /** Whether user is currently dragging to select */
  isDragging: boolean

  /** Drag start cell (null when not dragging) */
  dragStart: CellId | null

  /** Current drag end cell (null when not dragging) */
  dragEnd: CellId | null

  /** Preview selection during drag (includes original selection + drag range) */
  previewSelection: GridSelection

  /** Handle cell click (toggle single cell) */
  handleCellClick: (cell: CellId) => void

  /** Handle drag start (mouse down on cell) */
  handleDragStart: (cell: CellId) => void

  /** Handle drag move (mouse move over cell while dragging) */
  handleDragMove: (cell: CellId) => void

  /** Handle drag end (mouse up) */
  handleDragEnd: () => void

  /** Programmatically set selection */
  setSelection: (selection: GridSelection) => void
}

/**
 * Hook for managing schedule grid state and drag selection
 *
 * @param options Configuration options
 * @returns State and handlers for grid interaction
 *
 * @example
 * const {
 *   selection,
 *   isDragging,
 *   previewSelection,
 *   handleCellClick,
 *   handleDragStart,
 *   handleDragMove,
 *   handleDragEnd
 * } = useScheduleGridState({
 *   initialSelection: schedulesToGrid(schedules),
 *   onChange: (sel) => console.log('Selection changed', sel)
 * })
 */
export function useScheduleGridState(
  options: UseScheduleGridStateOptions = {}
): UseScheduleGridStateReturn {
  const { initialSelection = new Set(), onChange, disabled = false } = options

  // Selection state
  const [selection, setSelectionInternal] = useState<GridSelection>(initialSelection)

  // Drag state
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState<CellId | null>(null)
  const [dragEnd, setDragEnd] = useState<CellId | null>(null)
  const [dragMode, setDragMode] = useState<'add' | 'remove'>('add')

  // Notify parent of selection changes
  const setSelection = useCallback(
    (newSelection: GridSelection) => {
      setSelectionInternal(newSelection)
      onChange?.(newSelection)
    },
    [onChange]
  )

  // Track previous initialSelection to detect changes by content, not reference
  const prevInitialSelection = useRef(initialSelection)

  // Update selection when initialSelection changes (compare Set contents, not reference)
  useEffect(() => {
    const prev = prevInitialSelection.current

    // Check if contents have changed
    let hasChanged = false
    if (prev.size !== initialSelection.size) {
      hasChanged = true
    } else {
      // Check if all items are the same
      for (const item of initialSelection) {
        if (!prev.has(item)) {
          hasChanged = true
          break
        }
      }
    }

    if (hasChanged) {
      setSelectionInternal(initialSelection)
      prevInitialSelection.current = initialSelection
    }
  }, [initialSelection])

  // Calculate preview selection during drag
  const previewSelection =
    isDragging && dragStart && dragEnd
      ? selectRange(selection, dragStart, dragEnd, dragMode)
      : selection

  // Handle single cell click (toggle)
  const handleCellClick = useCallback(
    (cell: CellId) => {
      if (disabled) return

      const newSelection = toggleCell(selection, cell)
      setSelection(newSelection)
    },
    [selection, setSelection, disabled]
  )

  // Handle drag start
  const handleDragStart = useCallback(
    (cell: CellId) => {
      if (disabled) return

      // Determine drag mode: if starting cell is selected, we're removing; otherwise adding
      const mode = isSelected(selection, cell) ? 'remove' : 'add'

      setIsDragging(true)
      setDragStart(cell)
      setDragEnd(cell)
      setDragMode(mode)
    },
    [disabled, selection]
  )

  // Handle drag move
  const handleDragMove = useCallback(
    (cell: CellId) => {
      if (!isDragging || disabled) return

      setDragEnd(cell)
    },
    [isDragging, disabled]
  )

  // Handle drag end
  const handleDragEnd = useCallback(() => {
    if (!isDragging || disabled) return

    // Only commit if it's a real drag (more than one cell)
    // Single-cell "drags" are handled by handleCellClick
    if (dragStart && dragEnd) {
      const isSingleCell = dragStart.day === dragEnd.day && dragStart.slot === dragEnd.slot

      if (!isSingleCell) {
        // Commit the drag selection using the determined mode
        const newSelection = selectRange(selection, dragStart, dragEnd, dragMode)
        setSelection(newSelection)
      }
    }

    // Reset drag state
    setIsDragging(false)
    setDragStart(null)
    setDragEnd(null)
    setDragMode('add')
  }, [isDragging, dragStart, dragEnd, dragMode, selection, setSelection, disabled])

  // Store handleDragEnd in a ref to avoid dependency cascade in useEffect
  const handleDragEndRef = useRef(handleDragEnd)
  useEffect(() => {
    handleDragEndRef.current = handleDragEnd
  }, [handleDragEnd])

  // Handle mouse up globally to end drag even if cursor leaves grid
  useEffect(() => {
    if (!isDragging) return

    const handleGlobalMouseUp = () => {
      handleDragEndRef.current()
    }

    window.addEventListener('mouseup', handleGlobalMouseUp)
    window.addEventListener('touchend', handleGlobalMouseUp)

    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp)
      window.removeEventListener('touchend', handleGlobalMouseUp)
    }
  }, [isDragging])

  return {
    selection,
    isDragging,
    dragStart,
    dragEnd,
    previewSelection,
    handleCellClick,
    handleDragStart,
    handleDragMove,
    handleDragEnd,
    setSelection,
  }
}
