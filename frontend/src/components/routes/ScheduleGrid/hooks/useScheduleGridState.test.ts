import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useScheduleGridState } from './useScheduleGridState'

describe('useScheduleGridState', () => {
  describe('initial state', () => {
    it('should initialize with empty selection by default', () => {
      const { result } = renderHook(() => useScheduleGridState())

      expect(result.current.selection.size).toBe(0)
      expect(result.current.isDragging).toBe(false)
      expect(result.current.dragStart).toBe(null)
      expect(result.current.dragEnd).toBe(null)
    })

    it('should initialize with provided selection', () => {
      const initialSelection = new Set(['MON:0', 'TUE:5'])
      const { result } = renderHook(() => useScheduleGridState({ initialSelection }))

      expect(result.current.selection).toEqual(initialSelection)
    })

    it('should update selection when initialSelection prop changes', () => {
      const { result, rerender } = renderHook(
        ({ initialSelection }) => useScheduleGridState({ initialSelection }),
        {
          initialProps: { initialSelection: new Set(['MON:0']) },
        }
      )

      expect(result.current.selection.size).toBe(1)

      rerender({ initialSelection: new Set(['TUE:5', 'WED:10']) })

      expect(result.current.selection.size).toBe(2)
      expect(result.current.selection.has('TUE:5')).toBe(true)
      expect(result.current.selection.has('WED:10')).toBe(true)
    })
  })

  describe('handleCellClick', () => {
    it('should toggle cell on click', () => {
      const { result } = renderHook(() => useScheduleGridState())

      act(() => {
        result.current.handleCellClick({ day: 'MON', slot: 0 })
      })

      expect(result.current.selection.has('MON:0')).toBe(true)

      act(() => {
        result.current.handleCellClick({ day: 'MON', slot: 0 })
      })

      expect(result.current.selection.has('MON:0')).toBe(false)
    })

    it('should call onChange callback', () => {
      const onChange = vi.fn()
      const { result } = renderHook(() => useScheduleGridState({ onChange }))

      act(() => {
        result.current.handleCellClick({ day: 'MON', slot: 0 })
      })

      expect(onChange).toHaveBeenCalledTimes(1)
      const calledWith = onChange.mock.calls[0][0]
      expect(calledWith.has('MON:0')).toBe(true)
    })

    it('should not change selection when disabled', () => {
      const { result } = renderHook(() => useScheduleGridState({ disabled: true }))

      act(() => {
        result.current.handleCellClick({ day: 'MON', slot: 0 })
      })

      expect(result.current.selection.size).toBe(0)
    })
  })

  describe('drag selection', () => {
    it('should start drag on handleDragStart', () => {
      const { result } = renderHook(() => useScheduleGridState())

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      expect(result.current.isDragging).toBe(true)
      expect(result.current.dragStart).toEqual({ day: 'MON', slot: 0 })
      expect(result.current.dragEnd).toEqual({ day: 'MON', slot: 0 })
    })

    it('should update dragEnd on handleDragMove', () => {
      const { result } = renderHook(() => useScheduleGridState())

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      act(() => {
        result.current.handleDragMove({ day: 'MON', slot: 5 })
      })

      expect(result.current.dragEnd).toEqual({ day: 'MON', slot: 5 })
      expect(result.current.isDragging).toBe(true)
    })

    it('should not update dragEnd if not dragging', () => {
      const { result } = renderHook(() => useScheduleGridState())

      act(() => {
        result.current.handleDragMove({ day: 'MON', slot: 5 })
      })

      expect(result.current.dragEnd).toBe(null)
    })

    it('should commit selection and reset drag state on handleDragEnd', () => {
      const { result } = renderHook(() => useScheduleGridState())

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      act(() => {
        result.current.handleDragMove({ day: 'MON', slot: 2 })
      })

      act(() => {
        result.current.handleDragEnd()
      })

      expect(result.current.isDragging).toBe(false)
      expect(result.current.dragStart).toBe(null)
      expect(result.current.dragEnd).toBe(null)
      expect(result.current.selection.has('MON:0')).toBe(true)
      expect(result.current.selection.has('MON:1')).toBe(true)
      expect(result.current.selection.has('MON:2')).toBe(true)
    })

    it('should show preview selection during drag', () => {
      const { result } = renderHook(() => useScheduleGridState())

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      act(() => {
        result.current.handleDragMove({ day: 'MON', slot: 2 })
      })

      // Preview should include drag range
      expect(result.current.previewSelection.has('MON:0')).toBe(true)
      expect(result.current.previewSelection.has('MON:1')).toBe(true)
      expect(result.current.previewSelection.has('MON:2')).toBe(true)

      // Actual selection not changed yet
      expect(result.current.selection.size).toBe(0)
    })

    it('should add to existing selection when dragging', () => {
      const initialSelection = new Set(['TUE:10'])
      const { result } = renderHook(() => useScheduleGridState({ initialSelection }))

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      act(() => {
        result.current.handleDragMove({ day: 'MON', slot: 1 })
      })

      act(() => {
        result.current.handleDragEnd()
      })

      // Should have both original and new selection
      expect(result.current.selection.has('TUE:10')).toBe(true)
      expect(result.current.selection.has('MON:0')).toBe(true)
      expect(result.current.selection.has('MON:1')).toBe(true)
    })

    it('should not start drag when disabled', () => {
      const { result } = renderHook(() => useScheduleGridState({ disabled: true }))

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      expect(result.current.isDragging).toBe(false)
    })

    it('should not update drag when disabled mid-drag', () => {
      const { result, rerender } = renderHook(
        ({ disabled }) => useScheduleGridState({ disabled }),
        { initialProps: { disabled: false } }
      )

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      rerender({ disabled: true })

      act(() => {
        result.current.handleDragMove({ day: 'MON', slot: 5 })
      })

      expect(result.current.dragEnd).toEqual({ day: 'MON', slot: 0 })
    })

    it('should call onChange on drag end', () => {
      const onChange = vi.fn()
      const { result } = renderHook(() => useScheduleGridState({ onChange }))

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      act(() => {
        result.current.handleDragMove({ day: 'MON', slot: 2 })
      })

      act(() => {
        result.current.handleDragEnd()
      })

      expect(onChange).toHaveBeenCalledTimes(1)
      const calledWith = onChange.mock.calls[0][0]
      expect(calledWith.has('MON:0')).toBe(true)
      expect(calledWith.has('MON:1')).toBe(true)
      expect(calledWith.has('MON:2')).toBe(true)
    })
  })

  describe('setSelection', () => {
    it('should update selection programmatically', () => {
      const { result } = renderHook(() => useScheduleGridState())

      const newSelection = new Set(['MON:0', 'TUE:5'])
      act(() => {
        result.current.setSelection(newSelection)
      })

      expect(result.current.selection).toEqual(newSelection)
    })

    it('should call onChange when set programmatically', () => {
      const onChange = vi.fn()
      const { result } = renderHook(() => useScheduleGridState({ onChange }))

      const newSelection = new Set(['MON:0'])
      act(() => {
        result.current.setSelection(newSelection)
      })

      expect(onChange).toHaveBeenCalledWith(newSelection)
    })
  })

  describe('previewSelection', () => {
    it('should equal selection when not dragging', () => {
      const initialSelection = new Set(['MON:0'])
      const { result } = renderHook(() => useScheduleGridState({ initialSelection }))

      expect(result.current.previewSelection).toEqual(result.current.selection)
    })

    it('should include drag range when dragging', () => {
      const { result } = renderHook(() => useScheduleGridState())

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      act(() => {
        result.current.handleDragMove({ day: 'TUE', slot: 2 })
      })

      // Preview should include entire rectangular range
      expect(result.current.previewSelection.size).toBeGreaterThan(0)
      expect(result.current.previewSelection.has('MON:0')).toBe(true)
      expect(result.current.previewSelection.has('TUE:2')).toBe(true)
    })

    it('should return to normal selection after drag ends', () => {
      const { result } = renderHook(() => useScheduleGridState())

      act(() => {
        result.current.handleDragStart({ day: 'MON', slot: 0 })
      })

      act(() => {
        result.current.handleDragMove({ day: 'MON', slot: 2 })
      })

      const previewDuringDrag = result.current.previewSelection

      act(() => {
        result.current.handleDragEnd()
      })

      // After drag, preview should equal committed selection
      expect(result.current.previewSelection).toEqual(result.current.selection)
      expect(result.current.previewSelection.size).toBe(previewDuringDrag.size)
    })
  })
})
