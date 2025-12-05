import { describe, it, expect } from 'vitest'
import { validateNotEmpty, validateMaxSchedules, validateAll } from './validation'

describe('ScheduleGrid validation', () => {
  describe('validateNotEmpty', () => {
    it('should pass for non-empty selection', () => {
      const selection = new Set(['MON:0'])
      const result = validateNotEmpty(selection)
      expect(result.valid).toBe(true)
    })

    it('should fail for empty selection', () => {
      const selection = new Set<string>()
      const result = validateNotEmpty(selection)
      expect(result).toEqual({
        valid: false,
        error: 'Please select at least one time slot',
      })
    })

    it('should pass for multiple selected cells', () => {
      const selection = new Set(['MON:0', 'TUE:5', 'WED:10'])
      const result = validateNotEmpty(selection)
      expect(result.valid).toBe(true)
    })
  })

  describe('validateMaxSchedules', () => {
    it('should pass for selection within limit', () => {
      const selection = new Set(['MON:0', 'MON:1', 'TUE:5'])
      const result = validateMaxSchedules(selection, 10)
      expect(result.valid).toBe(true)
    })

    it('should pass for contiguous selection (single block per day)', () => {
      // MON: 0-10 (1 block), TUE: 0-10 (1 block) = 2 blocks total
      const selection = new Set<string>()
      for (let i = 0; i <= 10; i++) {
        selection.add(`MON:${i}`)
        selection.add(`TUE:${i}`)
      }
      const result = validateMaxSchedules(selection, 10)
      expect(result.valid).toBe(true)
    })

    it('should fail when too many blocks', () => {
      // Create 11 separate blocks (each day with gap)
      const selection = new Set<string>()
      for (let i = 0; i < 11; i++) {
        selection.add(`MON:${i * 2}`) // 0, 2, 4, 6... (creates gaps)
      }
      const result = validateMaxSchedules(selection, 10)
      expect(result.valid).toBe(false)
      expect(result.error).toContain('Too many time blocks')
      expect(result.error).toContain('11')
      expect(result.error).toContain('10')
    })

    it('should use default max of 100', () => {
      const selection = new Set(['MON:0'])
      const result = validateMaxSchedules(selection)
      expect(result.valid).toBe(true)
    })

    it('should handle complex pattern with multiple blocks per day', () => {
      // Create multiple non-contiguous blocks
      const selection = new Set([
        'MON:0',
        'MON:1', // Block 1
        'MON:5',
        'MON:6', // Block 2
        'TUE:10',
        'TUE:11', // Block 3
        'WED:20',
        'WED:21', // Block 4
      ])
      const result = validateMaxSchedules(selection, 5)
      expect(result.valid).toBe(true)

      const resultFail = validateMaxSchedules(selection, 3)
      expect(resultFail.valid).toBe(false)
    })

    it('should count blocks correctly with single-slot gaps', () => {
      // MON:0, gap, MON:2, gap, MON:4 = 3 blocks
      const selection = new Set(['MON:0', 'MON:2', 'MON:4'])
      const result = validateMaxSchedules(selection, 2)
      expect(result.valid).toBe(false)
    })

    it('should handle all days with blocks', () => {
      const selection = new Set<string>()
      const days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
      // Add 2 blocks per day = 14 blocks total
      for (const day of days) {
        selection.add(`${day}:0`)
        selection.add(`${day}:1`)
        selection.add(`${day}:5`)
        selection.add(`${day}:6`)
      }
      const result = validateMaxSchedules(selection, 20)
      expect(result.valid).toBe(true)

      const resultFail = validateMaxSchedules(selection, 10)
      expect(resultFail.valid).toBe(false)
    })
  })

  describe('validateAll', () => {
    it('should pass when all validations pass', () => {
      const selection = new Set(['MON:0', 'MON:1'])
      const result = validateAll(selection)
      expect(result.valid).toBe(true)
    })

    it('should fail on empty selection first', () => {
      const selection = new Set<string>()
      const result = validateAll(selection)
      expect(result.valid).toBe(false)
      expect(result.error).toContain('at least one time slot')
    })

    it('should fail on too many blocks if not empty', () => {
      const selection = new Set<string>()
      for (let i = 0; i < 11; i++) {
        selection.add(`MON:${i * 2}`)
      }
      const result = validateAll(selection, { maxSchedules: 10 })
      expect(result.valid).toBe(false)
      expect(result.error).toContain('Too many time blocks')
    })

    it('should respect custom maxSchedules option', () => {
      const selection = new Set(['MON:0', 'MON:1', 'MON:5', 'MON:6', 'MON:10', 'MON:11'])
      const resultPass = validateAll(selection, { maxSchedules: 5 })
      expect(resultPass.valid).toBe(true)

      const resultFail = validateAll(selection, { maxSchedules: 2 })
      expect(resultFail.valid).toBe(false)
    })

    it('should use default options when not provided', () => {
      const selection = new Set(['MON:0'])
      const result = validateAll(selection)
      expect(result.valid).toBe(true)
    })

    it('should return first validation error encountered', () => {
      // Empty selection will fail first check
      const selection = new Set<string>()
      const result = validateAll(selection, { maxSchedules: 0 })
      expect(result.valid).toBe(false)
      // Should get "empty" error, not "too many blocks"
      expect(result.error).toContain('at least one time slot')
    })
  })

  describe('validation result type', () => {
    it('should return discriminated union', () => {
      const validResult = validateNotEmpty(new Set(['MON:0']))
      if (validResult.valid) {
        // TypeScript should allow this branch
        expect(validResult.valid).toBe(true)
      }

      const invalidResult = validateNotEmpty(new Set())
      if (!invalidResult.valid) {
        // TypeScript should allow accessing error here
        expect(invalidResult.error).toBeDefined()
      }
    })
  })
})
