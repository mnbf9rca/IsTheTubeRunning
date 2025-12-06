import { describe, it, expect } from 'vitest'
import {
  toggleCell,
  isSelected,
  selectRange,
  clearSelection,
  selectDay,
  deselectDay,
  selectTimeSlot,
  deselectTimeSlot,
  isDaySelected,
  isTimeSlotSelected,
} from './selection'

describe('ScheduleGrid selection', () => {
  describe('toggleCell', () => {
    it('should add cell if not in selection', () => {
      const selection = new Set<string>()
      const result = toggleCell(selection, { day: 'MON', slot: 0 })
      expect(result.has('MON:0')).toBe(true)
    })

    it('should remove cell if in selection', () => {
      const selection = new Set(['MON:0'])
      const result = toggleCell(selection, { day: 'MON', slot: 0 })
      expect(result.has('MON:0')).toBe(false)
      expect(result.size).toBe(0)
    })

    it('should return new Set (immutable)', () => {
      const selection = new Set<string>()
      const result = toggleCell(selection, { day: 'MON', slot: 0 })
      expect(result).not.toBe(selection)
      expect(selection.size).toBe(0) // Original unchanged
    })

    it('should not affect other cells', () => {
      const selection = new Set(['TUE:5'])
      const result = toggleCell(selection, { day: 'MON', slot: 0 })
      expect(result.has('TUE:5')).toBe(true)
      expect(result.has('MON:0')).toBe(true)
      expect(result.size).toBe(2)
    })
  })

  describe('isSelected', () => {
    it('should return true for selected cell', () => {
      const selection = new Set(['MON:0', 'TUE:5'])
      expect(isSelected(selection, { day: 'MON', slot: 0 })).toBe(true)
      expect(isSelected(selection, { day: 'TUE', slot: 5 })).toBe(true)
    })

    it('should return false for unselected cell', () => {
      const selection = new Set(['MON:0'])
      expect(isSelected(selection, { day: 'TUE', slot: 0 })).toBe(false)
      expect(isSelected(selection, { day: 'MON', slot: 1 })).toBe(false)
    })

    it('should return false for empty selection', () => {
      const selection = new Set<string>()
      expect(isSelected(selection, { day: 'MON', slot: 0 })).toBe(false)
    })
  })

  describe('selectRange', () => {
    it('should select rectangular range (add mode)', () => {
      const selection = new Set<string>()
      const result = selectRange(selection, { day: 'MON', slot: 0 }, { day: 'TUE', slot: 2 }, 'add')

      // Should have MON:0, MON:1, MON:2, TUE:0, TUE:1, TUE:2
      expect(result.size).toBe(6)
      expect(result.has('MON:0')).toBe(true)
      expect(result.has('MON:1')).toBe(true)
      expect(result.has('MON:2')).toBe(true)
      expect(result.has('TUE:0')).toBe(true)
      expect(result.has('TUE:1')).toBe(true)
      expect(result.has('TUE:2')).toBe(true)
    })

    it('should handle reverse order (end before start)', () => {
      const selection = new Set<string>()
      const result = selectRange(selection, { day: 'TUE', slot: 2 }, { day: 'MON', slot: 0 }, 'add')

      // Should still select the rectangle
      expect(result.size).toBe(6)
      expect(result.has('MON:0')).toBe(true)
      expect(result.has('TUE:2')).toBe(true)
    })

    it('should select single cell when start equals end', () => {
      const selection = new Set<string>()
      const result = selectRange(selection, { day: 'MON', slot: 5 }, { day: 'MON', slot: 5 }, 'add')

      expect(result.size).toBe(1)
      expect(result.has('MON:5')).toBe(true)
    })

    it('should remove cells in remove mode', () => {
      const selection = new Set(['MON:0', 'MON:1', 'TUE:0', 'TUE:1'])
      const result = selectRange(
        selection,
        { day: 'MON', slot: 0 },
        { day: 'MON', slot: 1 },
        'remove'
      )

      expect(result.size).toBe(2)
      expect(result.has('MON:0')).toBe(false)
      expect(result.has('MON:1')).toBe(false)
      expect(result.has('TUE:0')).toBe(true)
      expect(result.has('TUE:1')).toBe(true)
    })

    it('should toggle cells in toggle mode', () => {
      const selection = new Set(['MON:0', 'MON:1'])
      const result = selectRange(
        selection,
        { day: 'MON', slot: 1 },
        { day: 'MON', slot: 2 },
        'toggle'
      )

      // MON:1 was selected, so it's removed
      // MON:2 was not selected, so it's added
      // MON:0 remains selected (not in range)
      expect(result.size).toBe(2)
      expect(result.has('MON:0')).toBe(true)
      expect(result.has('MON:1')).toBe(false)
      expect(result.has('MON:2')).toBe(true)
    })

    it('should handle multi-day range', () => {
      const selection = new Set<string>()
      const result = selectRange(
        selection,
        { day: 'THU', slot: 48 },
        { day: 'SUN', slot: 50 },
        'add'
      )

      // Should select THU, FRI, SAT, SUN for slots 48, 49, 50
      expect(result.size).toBe(4 * 3) // 4 days × 3 slots
      expect(result.has('THU:48')).toBe(true)
      expect(result.has('FRI:49')).toBe(true)
      expect(result.has('SAT:50')).toBe(true)
      expect(result.has('SUN:48')).toBe(true)
    })

    it('should default to add mode', () => {
      const selection = new Set<string>()
      const result = selectRange(selection, { day: 'MON', slot: 0 }, { day: 'MON', slot: 1 })

      expect(result.size).toBe(2)
      expect(result.has('MON:0')).toBe(true)
      expect(result.has('MON:1')).toBe(true)
    })
  })

  describe('clearSelection', () => {
    it('should return empty set', () => {
      const result = clearSelection()
      expect(result.size).toBe(0)
      expect(result).toEqual(new Set())
    })
  })

  describe('selectDay', () => {
    it('should select all slots for a day', () => {
      const selection = new Set<string>()
      const result = selectDay(selection, 'MON')

      expect(result.size).toBe(96)
      expect(result.has('MON:0')).toBe(true)
      expect(result.has('MON:47')).toBe(true)
      expect(result.has('MON:95')).toBe(true)
    })

    it('should add to existing selection', () => {
      const selection = new Set(['TUE:0'])
      const result = selectDay(selection, 'MON')

      expect(result.size).toBe(97) // 96 + 1
      expect(result.has('TUE:0')).toBe(true)
    })

    it('should be idempotent', () => {
      const selection = new Set<string>()
      const result1 = selectDay(selection, 'MON')
      const result2 = selectDay(result1, 'MON')

      expect(result2.size).toBe(96)
      expect(result2).toEqual(result1)
    })
  })

  describe('deselectDay', () => {
    it('should remove all slots for a day', () => {
      const selection = new Set(['MON:0', 'MON:1', 'TUE:0'])
      const result = deselectDay(selection, 'MON')

      expect(result.size).toBe(1)
      expect(result.has('MON:0')).toBe(false)
      expect(result.has('MON:1')).toBe(false)
      expect(result.has('TUE:0')).toBe(true)
    })

    it('should work on empty selection', () => {
      const selection = new Set<string>()
      const result = deselectDay(selection, 'MON')

      expect(result.size).toBe(0)
    })

    it('should be idempotent', () => {
      const selection = selectDay(new Set(), 'MON')
      const result1 = deselectDay(selection, 'MON')
      const result2 = deselectDay(result1, 'MON')

      expect(result2.size).toBe(0)
      expect(result2).toEqual(result1)
    })
  })

  describe('selectTimeSlot', () => {
    it('should select slot across all days', () => {
      const selection = new Set<string>()
      const result = selectTimeSlot(selection, 48) // 12:00

      expect(result.size).toBe(7)
      expect(result.has('MON:48')).toBe(true)
      expect(result.has('TUE:48')).toBe(true)
      expect(result.has('WED:48')).toBe(true)
      expect(result.has('THU:48')).toBe(true)
      expect(result.has('FRI:48')).toBe(true)
      expect(result.has('SAT:48')).toBe(true)
      expect(result.has('SUN:48')).toBe(true)
    })

    it('should add to existing selection', () => {
      const selection = new Set(['MON:0'])
      const result = selectTimeSlot(selection, 48)

      expect(result.size).toBe(8) // 1 + 7
    })

    it('should be idempotent', () => {
      const selection = new Set<string>()
      const result1 = selectTimeSlot(selection, 48)
      const result2 = selectTimeSlot(result1, 48)

      expect(result2.size).toBe(7)
      expect(result2).toEqual(result1)
    })
  })

  describe('deselectTimeSlot', () => {
    it('should remove slot from all days', () => {
      const selection = new Set(['MON:48', 'TUE:48', 'MON:0'])
      const result = deselectTimeSlot(selection, 48)

      expect(result.size).toBe(1)
      expect(result.has('MON:48')).toBe(false)
      expect(result.has('TUE:48')).toBe(false)
      expect(result.has('MON:0')).toBe(true)
    })

    it('should work on empty selection', () => {
      const selection = new Set<string>()
      const result = deselectTimeSlot(selection, 48)

      expect(result.size).toBe(0)
    })
  })

  describe('isDaySelected', () => {
    it('should return true when all slots for day are selected', () => {
      const selection = selectDay(new Set(), 'MON')
      expect(isDaySelected(selection, 'MON')).toBe(true)
    })

    it('should return false when any slot is missing', () => {
      const selection = selectDay(new Set(), 'MON')
      selection.delete('MON:0')
      expect(isDaySelected(selection, 'MON')).toBe(false)
    })

    it('should return false for empty selection', () => {
      const selection = new Set<string>()
      expect(isDaySelected(selection, 'MON')).toBe(false)
    })
  })

  describe('isTimeSlotSelected', () => {
    it('should return true when slot selected for all days', () => {
      const selection = selectTimeSlot(new Set(), 48)
      expect(isTimeSlotSelected(selection, 48)).toBe(true)
    })

    it('should return false when any day is missing the slot', () => {
      const selection = selectTimeSlot(new Set(), 48)
      selection.delete('MON:48')
      expect(isTimeSlotSelected(selection, 48)).toBe(false)
    })

    it('should return false for empty selection', () => {
      const selection = new Set<string>()
      expect(isTimeSlotSelected(selection, 48)).toBe(false)
    })
  })

  describe('immutability', () => {
    it('all functions should return new Set instances', () => {
      const original = new Set(['MON:0'])

      const toggled = toggleCell(original, { day: 'TUE', slot: 0 })
      expect(toggled).not.toBe(original)

      const ranged = selectRange(original, { day: 'MON', slot: 1 }, { day: 'MON', slot: 2 })
      expect(ranged).not.toBe(original)

      const daySelected = selectDay(original, 'TUE')
      expect(daySelected).not.toBe(original)

      const dayDeselected = deselectDay(original, 'MON')
      expect(dayDeselected).not.toBe(original)

      const slotSelected = selectTimeSlot(original, 10)
      expect(slotSelected).not.toBe(original)

      const slotDeselected = deselectTimeSlot(original, 0)
      expect(slotDeselected).not.toBe(original)
    })
  })
})
