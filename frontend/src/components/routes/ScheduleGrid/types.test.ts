import { describe, it, expect } from 'vitest'
import { cellKey, parseKey, DAYS, SLOTS_PER_DAY, MINUTES_PER_SLOT, DAY_LABELS } from './types'

describe('ScheduleGrid types', () => {
  describe('constants', () => {
    it('DAYS should contain all 7 days in order', () => {
      expect(DAYS).toEqual(['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'])
    })

    it('DAY_LABELS should have labels for all days', () => {
      expect(DAY_LABELS).toEqual({
        MON: 'Mon',
        TUE: 'Tue',
        WED: 'Wed',
        THU: 'Thu',
        FRI: 'Fri',
        SAT: 'Sat',
        SUN: 'Sun',
      })
    })

    it('SLOTS_PER_DAY should be 96 (24 hours * 4 slots/hour)', () => {
      expect(SLOTS_PER_DAY).toBe(96)
    })

    it('MINUTES_PER_SLOT should be 15', () => {
      expect(MINUTES_PER_SLOT).toBe(15)
    })
  })

  describe('cellKey', () => {
    it('should create key from day and slot', () => {
      expect(cellKey('MON', 0)).toBe('MON:0')
      expect(cellKey('FRI', 48)).toBe('FRI:48')
      expect(cellKey('SUN', 95)).toBe('SUN:95')
    })

    it('should handle all days', () => {
      for (const day of DAYS) {
        expect(cellKey(day, 0)).toBe(`${day}:0`)
      }
    })

    it('should handle all slot indices', () => {
      expect(cellKey('MON', 0)).toBe('MON:0')
      expect(cellKey('MON', 95)).toBe('MON:95')
    })
  })

  describe('parseKey', () => {
    it('should parse valid keys', () => {
      expect(parseKey('MON:0')).toEqual({ day: 'MON', slot: 0 })
      expect(parseKey('FRI:48')).toEqual({ day: 'FRI', slot: 48 })
      expect(parseKey('SUN:95')).toEqual({ day: 'SUN', slot: 95 })
    })

    it('should round-trip with cellKey', () => {
      const original = { day: 'TUE' as const, slot: 42 }
      const key = cellKey(original.day, original.slot)
      const parsed = parseKey(key)
      expect(parsed).toEqual(original)
    })

    it('should throw error for invalid day code', () => {
      expect(() => parseKey('MONDAY:0')).toThrow('Invalid day code')
      expect(() => parseKey('XXX:5')).toThrow('Invalid day code')
    })

    it('should throw error for invalid slot index', () => {
      expect(() => parseKey('MON:abc')).toThrow('Invalid slot index')
      expect(() => parseKey('MON:-1')).toThrow('Invalid slot index')
      expect(() => parseKey('MON:96')).toThrow('Invalid slot index')
      expect(() => parseKey('MON:100')).toThrow('Invalid slot index')
    })

    it('should throw error for malformed keys', () => {
      expect(() => parseKey('MON')).toThrow()
      expect(() => parseKey('0:MON')).toThrow('Invalid day code')
      expect(() => parseKey('')).toThrow('Invalid day code')
    })
  })
})
