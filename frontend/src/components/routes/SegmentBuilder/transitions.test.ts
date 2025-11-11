import { describe, it, expect } from 'vitest'
import {
  transitionToSelectStation,
  transitionToSelectLine,
  transitionToSelectNextStation,
  transitionToChooseAction,
  transitionBackFromChooseAction,
  transitionToResumeFromSegments,
  computeStateAfterStationSelect,
  computeStateAfterSegmentUpdate,
  transitionWithError,
  transitionClearError,
  isValidTransition,
  logTransition,
} from './transitions'
import type { StationResponse, LineResponse } from '@/lib/api'
import type { CoreSegmentBuilderState } from './types'

describe('SegmentBuilder transitions', () => {
  // Mock stations
  const mockStationA: StationResponse = {
    id: '123e4567-e89b-12d3-a456-426614174000',
    tfl_id: 'station-a',
    name: 'Station A',
    latitude: 51.5,
    longitude: -0.1,
    lines: ['northern'],
    last_updated: '2025-01-01T00:00:00Z',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  const mockStationB: StationResponse = {
    id: '123e4567-e89b-12d3-a456-426614174001',
    tfl_id: 'station-b',
    name: 'Station B',
    latitude: 51.51,
    longitude: -0.11,
    lines: ['northern'],
    last_updated: '2025-01-01T00:00:00Z',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  const mockStationC: StationResponse = {
    id: '123e4567-e89b-12d3-a456-426614174002',
    tfl_id: 'station-c',
    name: 'Station C',
    latitude: 51.52,
    longitude: -0.12,
    lines: ['northern', 'victoria'],
    last_updated: '2025-01-01T00:00:00Z',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  // Mock lines
  const mockLineNorthern: LineResponse = {
    id: '223e4567-e89b-12d3-a456-426614174000',
    tfl_id: 'northern',
    name: 'Northern',
    mode: 'tube',
    last_updated: '2025-01-01T00:00:00Z',
  }

  const mockLineVictoria: LineResponse = {
    id: '223e4567-e89b-12d3-a456-426614174001',
    tfl_id: 'victoria',
    name: 'Victoria',
    mode: 'tube',
    last_updated: '2025-01-01T00:00:00Z',
  }

  describe('transitionToSelectStation', () => {
    it('should return complete initial state', () => {
      const state = transitionToSelectStation()

      expect(state.currentStation).toBeNull()
      expect(state.selectedLine).toBeNull()
      expect(state.nextStation).toBeNull()
      expect(state.step).toBe('select-station')
      expect(state.error).toBeNull()
    })

    it('should clear all previous state', () => {
      // Verify it returns exactly 5 fields
      const state = transitionToSelectStation()
      expect(Object.keys(state)).toEqual([
        'currentStation',
        'selectedLine',
        'nextStation',
        'step',
        'error',
      ])
    })
  })

  describe('transitionToSelectLine', () => {
    it('should set correct state for line selection', () => {
      const state = transitionToSelectLine(mockStationA)

      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBeNull()
      expect(state.nextStation).toBeNull()
      expect(state.step).toBe('select-line')
      expect(state.error).toBeNull()
    })

    it('should preserve station reference', () => {
      const state = transitionToSelectLine(mockStationB)
      expect(state.currentStation).toBe(mockStationB)
    })
  })

  describe('transitionToSelectNextStation', () => {
    it('should set correct state for next station selection', () => {
      const state = transitionToSelectNextStation(mockStationA, mockLineNorthern)

      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineNorthern)
      expect(state.nextStation).toBeNull()
      expect(state.step).toBe('select-next-station')
      expect(state.error).toBeNull()
    })

    it('should preserve station and line references', () => {
      const state = transitionToSelectNextStation(mockStationC, mockLineVictoria)
      expect(state.currentStation).toBe(mockStationC)
      expect(state.selectedLine).toBe(mockLineVictoria)
    })
  })

  describe('transitionToChooseAction', () => {
    it('should set correct state for action choice', () => {
      const state = transitionToChooseAction(mockStationA, mockLineNorthern, mockStationB)

      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineNorthern)
      expect(state.nextStation).toBe(mockStationB)
      expect(state.step).toBe('choose-action')
      expect(state.error).toBeNull()
    })

    it('should preserve all three station/line references', () => {
      const state = transitionToChooseAction(mockStationA, mockLineVictoria, mockStationC)
      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineVictoria)
      expect(state.nextStation).toBe(mockStationC)
    })
  })

  describe('transitionBackFromChooseAction', () => {
    it('should transition back to select-next-station', () => {
      const state = transitionBackFromChooseAction(mockStationA, mockLineNorthern)

      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineNorthern)
      expect(state.nextStation).toBeNull()
      expect(state.step).toBe('select-next-station')
      expect(state.error).toBeNull()
    })

    it('should clear nextStation', () => {
      const state = transitionBackFromChooseAction(mockStationB, mockLineVictoria)
      expect(state.nextStation).toBeNull()
    })
  })

  describe('transitionToResumeFromSegments', () => {
    it('should transition to select-next-station when station and line provided', () => {
      const state = transitionToResumeFromSegments(mockStationA, mockLineNorthern)

      expect(state.step).toBe('select-next-station')
      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineNorthern)
      expect(state.nextStation).toBeNull()
      expect(state.error).toBeNull()
    })

    it('should transition to select-station when no station provided', () => {
      const state = transitionToResumeFromSegments(null, mockLineNorthern)

      expect(state.step).toBe('select-station')
      expect(state.currentStation).toBeNull()
      expect(state.selectedLine).toBeNull()
      expect(state.nextStation).toBeNull()
    })

    it('should transition to select-station when no line provided', () => {
      const state = transitionToResumeFromSegments(mockStationA, null)

      expect(state.step).toBe('select-station')
    })

    it('should transition to select-station when both null', () => {
      const state = transitionToResumeFromSegments(null, null)

      expect(state.step).toBe('select-station')
      expect(state.currentStation).toBeNull()
      expect(state.selectedLine).toBeNull()
    })
  })

  describe('computeStateAfterStationSelect', () => {
    it('should return error state when no lines available', () => {
      const state = computeStateAfterStationSelect(mockStationA, [])

      expect(state.step).toBe('select-line')
      expect(state.currentStation).toBe(mockStationA)
      expect(state.error).toBe('Selected station has no lines available')
    })

    it('should auto-select line and advance when only one line', () => {
      const state = computeStateAfterStationSelect(mockStationA, [mockLineNorthern])

      expect(state.step).toBe('select-next-station')
      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineNorthern)
      expect(state.error).toBeNull()
    })

    it('should transition to select-line when multiple lines available', () => {
      const state = computeStateAfterStationSelect(mockStationC, [
        mockLineNorthern,
        mockLineVictoria,
      ])

      expect(state.step).toBe('select-line')
      expect(state.currentStation).toBe(mockStationC)
      expect(state.selectedLine).toBeNull()
      expect(state.error).toBeNull()
    })

    it('should handle three or more lines', () => {
      const mockLine3: LineResponse = {
        id: 'line-3',
        tfl_id: 'jubilee',
        name: 'Jubilee',
        mode: 'tube',
        last_updated: '2025-01-01T00:00:00Z',
      }

      const state = computeStateAfterStationSelect(mockStationC, [
        mockLineNorthern,
        mockLineVictoria,
        mockLine3,
      ])

      expect(state.step).toBe('select-line')
    })
  })

  describe('computeStateAfterSegmentUpdate', () => {
    it('should stay at choose-action if at choose-action with segments', () => {
      const currentState: CoreSegmentBuilderState = {
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        nextStation: mockStationB,
        step: 'choose-action',
        error: null,
      }

      const state = computeStateAfterSegmentUpdate(currentState, true)

      expect(state.step).toBe('choose-action')
      expect(state).toBe(currentState) // Should return same reference
    })

    it('should transition to select-next-station if has segments and station/line set', () => {
      const currentState: CoreSegmentBuilderState = {
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        nextStation: null,
        step: 'select-line',
        error: null,
      }

      const state = computeStateAfterSegmentUpdate(currentState, true)

      expect(state.step).toBe('select-next-station')
      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineNorthern)
    })

    it('should reset to select-station if no segments', () => {
      const currentState: CoreSegmentBuilderState = {
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        nextStation: mockStationB,
        step: 'choose-action',
        error: null,
      }

      const state = computeStateAfterSegmentUpdate(currentState, false)

      expect(state.step).toBe('select-station')
      expect(state.currentStation).toBeNull()
    })

    it('should reset to select-station if has segments but no current station', () => {
      const currentState: CoreSegmentBuilderState = {
        currentStation: null,
        selectedLine: mockLineNorthern,
        nextStation: null,
        step: 'select-line',
        error: null,
      }

      const state = computeStateAfterSegmentUpdate(currentState, true)

      expect(state.step).toBe('select-station')
    })

    it('should reset to select-station if has segments but no selected line', () => {
      const currentState: CoreSegmentBuilderState = {
        currentStation: mockStationA,
        selectedLine: null,
        nextStation: null,
        step: 'select-line',
        error: null,
      }

      const state = computeStateAfterSegmentUpdate(currentState, true)

      expect(state.step).toBe('select-station')
    })
  })

  describe('transitionWithError', () => {
    it('should preserve state and add error', () => {
      const currentState = transitionToSelectStation()
      const state = transitionWithError(currentState, 'Test error')

      expect(state.currentStation).toBeNull()
      expect(state.selectedLine).toBeNull()
      expect(state.nextStation).toBeNull()
      expect(state.step).toBe('select-station')
      expect(state.error).toBe('Test error')
    })

    it('should preserve complex state', () => {
      const currentState = transitionToSelectNextStation(mockStationA, mockLineNorthern)
      const state = transitionWithError(currentState, 'Error message')

      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineNorthern)
      expect(state.error).toBe('Error message')
    })

    it('should preserve choose-action state', () => {
      const currentState = transitionToChooseAction(mockStationA, mockLineNorthern, mockStationB)
      const state = transitionWithError(currentState, 'Validation failed')

      expect(state.step).toBe('choose-action')
      expect(state.nextStation).toBe(mockStationB)
      expect(state.error).toBe('Validation failed')
    })

    it('should overwrite previous error', () => {
      const currentState: CoreSegmentBuilderState = {
        currentStation: mockStationA,
        selectedLine: null,
        nextStation: null,
        step: 'select-line',
        error: 'Old error',
      }

      const state = transitionWithError(currentState, 'New error')
      expect(state.error).toBe('New error')
    })
  })

  describe('transitionClearError', () => {
    it('should clear error while preserving state', () => {
      const stateWithError: CoreSegmentBuilderState = {
        currentStation: mockStationA,
        selectedLine: null,
        nextStation: null,
        step: 'select-station',
        error: 'Some error',
      }

      const state = transitionClearError(stateWithError)

      expect(state.error).toBeNull()
      expect(state.currentStation).toBe(mockStationA)
      expect(state.step).toBe('select-station')
    })

    it('should preserve all fields except error', () => {
      const stateWithError = transitionWithError(
        transitionToChooseAction(mockStationA, mockLineNorthern, mockStationB),
        'Error'
      )

      const state = transitionClearError(stateWithError)

      expect(state.error).toBeNull()
      expect(state.currentStation).toBe(mockStationA)
      expect(state.selectedLine).toBe(mockLineNorthern)
      expect(state.nextStation).toBe(mockStationB)
      expect(state.step).toBe('choose-action')
    })

    it('should work when error is already null', () => {
      const stateWithoutError = transitionToSelectStation()
      const state = transitionClearError(stateWithoutError)

      expect(state.error).toBeNull()
    })
  })

  describe('isValidTransition', () => {
    it('should allow valid transitions from select-station', () => {
      expect(isValidTransition('select-station', 'select-line')).toBe(true)
      expect(isValidTransition('select-station', 'select-next-station')).toBe(true)
    })

    it('should allow valid transition from select-line', () => {
      expect(isValidTransition('select-line', 'select-next-station')).toBe(true)
    })

    it('should allow valid transition from select-next-station', () => {
      expect(isValidTransition('select-next-station', 'choose-action')).toBe(true)
    })

    it('should allow valid transitions from choose-action', () => {
      expect(isValidTransition('choose-action', 'select-next-station')).toBe(true)
      expect(isValidTransition('choose-action', 'select-station')).toBe(true)
    })

    it('should reject invalid transition from select-line to select-station', () => {
      expect(isValidTransition('select-line', 'select-station')).toBe(false)
    })

    it('should reject invalid transition from select-next-station to select-line', () => {
      expect(isValidTransition('select-next-station', 'select-line')).toBe(false)
    })

    it('should reject invalid transition from select-line to choose-action', () => {
      expect(isValidTransition('select-line', 'choose-action')).toBe(false)
    })

    it('should reject invalid transition from select-next-station to select-station', () => {
      expect(isValidTransition('select-next-station', 'select-station')).toBe(false)
    })

    it('should reject invalid transition from choose-action to select-line', () => {
      expect(isValidTransition('choose-action', 'select-line')).toBe(false)
    })
  })

  describe('logTransition', () => {
    it('should not throw when called with valid states', () => {
      const from = transitionToSelectStation()
      const to = transitionToSelectLine(mockStationA)

      expect(() => logTransition(from, to, 'test action')).not.toThrow()
    })

    it('should handle states with all fields populated', () => {
      const from = transitionToChooseAction(mockStationA, mockLineNorthern, mockStationB)
      const to = transitionToSelectNextStation(mockStationB, mockLineNorthern)

      expect(() => logTransition(from, to, 'continue journey')).not.toThrow()
    })

    it('should handle states with errors', () => {
      const from = transitionWithError(transitionToSelectStation(), 'Test error')
      const to = transitionClearError(from)

      expect(() => logTransition(from, to, 'clear error')).not.toThrow()
    })
  })
})
