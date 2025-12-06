import { describe, it, expect } from 'vitest'
import {
  slotToTime,
  timeToSlot,
  selectionToBlocks,
  gridToSchedules,
  schedulesToGrid,
} from './transforms'
import type { ScheduleResponse } from './types'

describe('ScheduleGrid transforms', () => {
  describe('slotToTime', () => {
    it('should convert slot 0 to 00:00:00', () => {
      expect(slotToTime(0)).toBe('00:00:00')
    })

    it('should convert slot 1 to 00:15:00', () => {
      expect(slotToTime(1)).toBe('00:15:00')
    })

    it('should convert slot 4 to 01:00:00', () => {
      expect(slotToTime(4)).toBe('01:00:00')
    })

    it('should convert slot 48 to 12:00:00', () => {
      expect(slotToTime(48)).toBe('12:00:00')
    })

    it('should convert slot 95 to 23:45:00', () => {
      expect(slotToTime(95)).toBe('23:45:00')
    })

    it('should pad single digit hours and minutes', () => {
      expect(slotToTime(2)).toBe('00:30:00') // 00:30
      expect(slotToTime(5)).toBe('01:15:00') // 01:15
      expect(slotToTime(36)).toBe('09:00:00') // 09:00
    })
  })

  describe('timeToSlot', () => {
    it('should convert 00:00:00 to slot 0', () => {
      expect(timeToSlot('00:00:00')).toBe(0)
    })

    it('should convert 00:15:00 to slot 1', () => {
      expect(timeToSlot('00:15:00')).toBe(1)
    })

    it('should convert 01:00:00 to slot 4', () => {
      expect(timeToSlot('01:00:00')).toBe(4)
    })

    it('should convert 12:00:00 to slot 48', () => {
      expect(timeToSlot('12:00:00')).toBe(48)
    })

    it('should convert 23:45:00 to slot 95', () => {
      expect(timeToSlot('23:45:00')).toBe(95)
    })

    it('should round down non-15-minute times', () => {
      expect(timeToSlot('09:22:00')).toBe(37) // Rounds down to 09:15 (slot 37)
      expect(timeToSlot('14:59:00')).toBe(59) // Rounds down to 14:45 (slot 59)
      expect(timeToSlot('10:07:00')).toBe(40) // Rounds down to 10:00 (slot 40)
    })

    it('should be inverse of slotToTime for valid 15-minute intervals', () => {
      for (let slot = 0; slot < 96; slot++) {
        const time = slotToTime(slot)
        expect(timeToSlot(time)).toBe(slot)
      }
    })
  })

  describe('selectionToBlocks', () => {
    it('should return empty array for empty selection', () => {
      const selection = new Set<string>()
      expect(selectionToBlocks(selection)).toEqual([])
    })

    it('should create single block for contiguous selection', () => {
      const selection = new Set(['MON:0', 'MON:1', 'MON:2'])
      const blocks = selectionToBlocks(selection)
      expect(blocks).toEqual([{ day: 'MON', startSlot: 0, endSlot: 3 }])
    })

    it('should create multiple blocks for non-contiguous selection on same day', () => {
      const selection = new Set(['MON:0', 'MON:1', 'MON:5', 'MON:6'])
      const blocks = selectionToBlocks(selection)
      expect(blocks).toEqual([
        { day: 'MON', startSlot: 0, endSlot: 2 },
        { day: 'MON', startSlot: 5, endSlot: 7 },
      ])
    })

    it('should create separate blocks for different days', () => {
      const selection = new Set(['MON:0', 'TUE:10', 'WED:20'])
      const blocks = selectionToBlocks(selection)
      expect(blocks).toEqual([
        { day: 'MON', startSlot: 0, endSlot: 1 },
        { day: 'TUE', startSlot: 10, endSlot: 11 },
        { day: 'WED', startSlot: 20, endSlot: 21 },
      ])
    })

    it('should handle complex selection patterns', () => {
      const selection = new Set([
        'MON:0',
        'MON:1',
        'MON:2', // Mon 00:00-00:45
        'MON:10',
        'MON:11', // Mon 02:30-03:00
        'TUE:48',
        'TUE:49',
        'TUE:50', // Tue 12:00-12:45
      ])
      const blocks = selectionToBlocks(selection)
      expect(blocks).toEqual([
        { day: 'MON', startSlot: 0, endSlot: 3 },
        { day: 'MON', startSlot: 10, endSlot: 12 },
        { day: 'TUE', startSlot: 48, endSlot: 51 },
      ])
    })

    it('should handle single slot selection', () => {
      const selection = new Set(['FRI:48'])
      const blocks = selectionToBlocks(selection)
      expect(blocks).toEqual([{ day: 'FRI', startSlot: 48, endSlot: 49 }])
    })
  })

  describe('gridToSchedules', () => {
    it('should return empty array for empty selection', () => {
      const selection = new Set<string>()
      expect(gridToSchedules(selection)).toEqual([])
    })

    it('should convert single contiguous block to schedule', () => {
      const selection = new Set(['MON:0', 'MON:1', 'MON:2', 'MON:3'])
      const schedules = gridToSchedules(selection)
      expect(schedules).toEqual([
        {
          days_of_week: ['MON'],
          start_time: '00:00:00',
          end_time: '01:00:00',
        },
      ])
    })

    it('should create separate schedules for non-contiguous blocks', () => {
      const selection = new Set(['MON:0', 'MON:1', 'MON:10', 'MON:11'])
      const schedules = gridToSchedules(selection)
      expect(schedules).toEqual([
        {
          days_of_week: ['MON'],
          start_time: '00:00:00',
          end_time: '00:30:00',
        },
        {
          days_of_week: ['MON'],
          start_time: '02:30:00',
          end_time: '03:00:00',
        },
      ])
    })

    it('should create separate schedules for different days', () => {
      const selection = new Set(['MON:36', 'TUE:36']) // 09:00
      const schedules = gridToSchedules(selection)
      expect(schedules).toEqual([
        {
          days_of_week: ['MON'],
          start_time: '09:00:00',
          end_time: '09:15:00',
        },
        {
          days_of_week: ['TUE'],
          start_time: '09:00:00',
          end_time: '09:15:00',
        },
      ])
    })

    it('should handle typical weekday morning commute', () => {
      // Mon-Fri 07:00-09:00 (slots 28-35)
      const selection = new Set([
        'MON:28',
        'MON:29',
        'MON:30',
        'MON:31',
        'MON:32',
        'MON:33',
        'MON:34',
        'MON:35',
      ])
      const schedules = gridToSchedules(selection)
      expect(schedules).toEqual([
        {
          days_of_week: ['MON'],
          start_time: '07:00:00',
          end_time: '09:00:00',
        },
      ])
    })
  })

  describe('schedulesToGrid', () => {
    it('should return empty set for empty schedules', () => {
      const schedules: ScheduleResponse[] = []
      const selection = schedulesToGrid(schedules)
      expect(selection.size).toBe(0)
    })

    it('should convert single schedule to grid selection', () => {
      const schedules: ScheduleResponse[] = [
        {
          id: '1',
          days_of_week: ['MON'],
          start_time: '00:00:00',
          end_time: '01:00:00',
        },
      ]
      const selection = schedulesToGrid(schedules)
      expect(selection).toEqual(new Set(['MON:0', 'MON:1', 'MON:2', 'MON:3']))
    })

    it('should expand schedule with multiple days', () => {
      const schedules: ScheduleResponse[] = [
        {
          id: '1',
          days_of_week: ['MON', 'TUE'],
          start_time: '09:00:00',
          end_time: '09:30:00',
        },
      ]
      const selection = schedulesToGrid(schedules)
      expect(selection).toEqual(new Set(['MON:36', 'MON:37', 'TUE:36', 'TUE:37']))
    })

    it('should handle multiple schedules', () => {
      const schedules: ScheduleResponse[] = [
        {
          id: '1',
          days_of_week: ['MON'],
          start_time: '09:00:00',
          end_time: '09:15:00',
        },
        {
          id: '2',
          days_of_week: ['TUE'],
          start_time: '14:00:00',
          end_time: '14:15:00',
        },
      ]
      const selection = schedulesToGrid(schedules)
      expect(selection).toEqual(new Set(['MON:36', 'TUE:56']))
    })

    it('should handle overlapping schedules (union)', () => {
      const schedules: ScheduleResponse[] = [
        {
          id: '1',
          days_of_week: ['MON'],
          start_time: '09:00:00',
          end_time: '10:00:00',
        },
        {
          id: '2',
          days_of_week: ['MON'],
          start_time: '09:30:00',
          end_time: '10:30:00',
        },
      ]
      const selection = schedulesToGrid(schedules)
      // Should include 09:00-10:30 (slots 36-41, exclusive of end)
      // Schedule 1: slots 36-39 (09:00-10:00)
      // Schedule 2: slots 38-41 (09:30-10:30)
      // Union: slots 36-41 (6 slots total)
      expect(selection.has('MON:36')).toBe(true)
      expect(selection.has('MON:37')).toBe(true)
      expect(selection.has('MON:38')).toBe(true)
      expect(selection.has('MON:39')).toBe(true)
      expect(selection.has('MON:40')).toBe(true)
      expect(selection.has('MON:41')).toBe(true)
      expect(selection.has('MON:42')).toBe(false) // Exclusive of end time
      expect(selection.size).toBe(6)
    })
  })

  describe('round-trip conversion', () => {
    it('should round-trip from grid to schedules to grid', () => {
      const original = new Set(['MON:0', 'MON:1', 'TUE:48', 'TUE:49'])
      const schedules = gridToSchedules(original)
      const restored = schedulesToGrid(schedules)
      expect(restored).toEqual(original)
    })

    it('should round-trip from schedules to grid to schedules', () => {
      const original: ScheduleResponse[] = [
        {
          id: '1',
          days_of_week: ['MON'],
          start_time: '09:00:00',
          end_time: '17:00:00',
        },
      ]
      const grid = schedulesToGrid(original)
      const schedules = gridToSchedules(grid)

      // Should produce equivalent schedule (might split by day)
      expect(schedules).toHaveLength(1)
      expect(schedules[0]).toEqual({
        days_of_week: ['MON'],
        start_time: '09:00:00',
        end_time: '17:00:00',
      })
    })

    it('should handle complex round-trip', () => {
      const original = new Set([
        // Mon morning
        'MON:36',
        'MON:37',
        'MON:38',
        'MON:39', // 09:00-10:00
        // Mon afternoon
        'MON:56',
        'MON:57',
        'MON:58',
        'MON:59', // 14:00-15:00
        // Tue all day
        'TUE:0',
        'TUE:1',
        'TUE:2',
        'TUE:3',
        'TUE:4',
        'TUE:5',
        'TUE:6',
        'TUE:7', // 00:00-02:00
      ])

      const schedules = gridToSchedules(original)
      const restored = schedulesToGrid(schedules)
      expect(restored).toEqual(original)
    })
  })
})
