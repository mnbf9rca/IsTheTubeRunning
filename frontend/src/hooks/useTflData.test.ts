import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useTflData } from './useTflData'
import { ApiError } from '../lib/api'
import type { LineResponse, StationResponse, NetworkGraph } from '../lib/api'

// Mock the API module
vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api')
  return {
    ...actual,
    getLines: vi.fn(),
    getStations: vi.fn(),
    getNetworkGraph: vi.fn(),
  }
})

// Import mocked functions
import * as api from '../lib/api'

describe('useTflData', () => {
  const mockLinesResponse: LineResponse[] = [
    {
      id: 'line-1',
      tfl_id: 'northern',
      name: 'Northern',
      color: '#000000',
      last_updated: '2025-01-01T00:00:00Z',
    },
    {
      id: 'line-2',
      tfl_id: 'victoria',
      name: 'Victoria',
      color: '#0098D8',
      last_updated: '2025-01-01T00:00:00Z',
    },
    {
      id: 'line-3',
      tfl_id: 'circle',
      name: 'Circle',
      color: '#FFD300',
      last_updated: '2025-01-01T00:00:00Z',
    },
  ]

  const mockStationsResponse: StationResponse[] = [
    {
      id: 'station-1',
      tfl_id: '940GZZLUKSX',
      name: "King's Cross St. Pancras",
      latitude: 51.5308,
      longitude: -0.1238,
      lines: ['northern', 'victoria', 'circle'],
      last_updated: '2025-01-01T00:00:00Z',
    },
    {
      id: 'station-2',
      tfl_id: '940GZZLUEUS',
      name: 'Euston',
      latitude: 51.5282,
      longitude: -0.1337,
      lines: ['northern', 'victoria'],
      last_updated: '2025-01-01T00:00:00Z',
    },
    {
      id: 'station-3',
      tfl_id: '940GZZLUEMB',
      name: 'Embankment',
      latitude: 51.5074,
      longitude: -0.1224,
      lines: ['northern', 'circle'],
      last_updated: '2025-01-01T00:00:00Z',
    },
  ]

  const mockNetworkGraph: NetworkGraph = {
    '940GZZLUKSX': [
      {
        station_id: 'station-2',
        station_tfl_id: '940GZZLUEUS',
        station_name: 'Euston',
        line_id: 'line-1',
        line_tfl_id: 'northern',
        line_name: 'Northern',
      },
      {
        station_id: 'station-3',
        station_tfl_id: '940GZZLUEMB',
        station_name: 'Embankment',
        line_id: 'line-3',
        line_tfl_id: 'circle',
        line_name: 'Circle',
      },
    ],
    '940GZZLUEUS': [
      {
        station_id: 'station-1',
        station_tfl_id: '940GZZLUKSX',
        station_name: "King's Cross St. Pancras",
        line_id: 'line-1',
        line_tfl_id: 'northern',
        line_name: 'Northern',
      },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementation
    vi.mocked(api.getLines).mockResolvedValue(mockLinesResponse)
    vi.mocked(api.getStations).mockResolvedValue(mockStationsResponse)
    vi.mocked(api.getNetworkGraph).mockResolvedValue(mockNetworkGraph)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('initialization', () => {
    it('should fetch all TfL data on mount', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      // Initially loading
      expect(result.current.loading).toBe(true)
      expect(result.current.lines).toBeNull()
      expect(result.current.stations).toBeNull()
      expect(result.current.networkGraph).toBeNull()

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.lines).toEqual(mockLinesResponse)
      expect(result.current.stations).toEqual(mockStationsResponse)
      expect(result.current.networkGraph).toEqual(mockNetworkGraph)
      expect(result.current.error).toBeNull()
      expect(api.getLines).toHaveBeenCalledTimes(1)
      expect(api.getStations).toHaveBeenCalledTimes(1)
      expect(api.getNetworkGraph).toHaveBeenCalledTimes(1)

      unmount()
    })

    it('should handle fetch error on mount', async () => {
      const mockError = new ApiError(500, 'Internal Server Error')
      vi.mocked(api.getLines).mockRejectedValue(mockError)

      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.lines).toBeNull()
      expect(result.current.stations).toBeNull()
      expect(result.current.networkGraph).toBeNull()
      expect(result.current.error).toEqual(mockError)

      unmount()
    })
  })

  describe('getStationsForLine', () => {
    it('should return stations for a specific line', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const northernStations = result.current.getStationsForLine('northern')
      expect(northernStations).toHaveLength(3) // All test stations serve Northern
      expect(northernStations.map((s) => s.tfl_id)).toEqual([
        '940GZZLUKSX',
        '940GZZLUEUS',
        '940GZZLUEMB',
      ])

      const victoriaStations = result.current.getStationsForLine('victoria')
      expect(victoriaStations).toHaveLength(2)
      expect(victoriaStations.map((s) => s.tfl_id)).toEqual(['940GZZLUKSX', '940GZZLUEUS'])

      unmount()
    })

    it('should return empty array for non-existent line', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const stations = result.current.getStationsForLine('non-existent')
      expect(stations).toEqual([])

      unmount()
    })

    it('should return empty array when stations not loaded', () => {
      vi.mocked(api.getStations).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      )

      const { result, unmount } = renderHook(() => useTflData())

      const stations = result.current.getStationsForLine('northern')
      expect(stations).toEqual([])

      unmount()
    })
  })

  describe('getNextStations', () => {
    it('should return connected stations on the specified line', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // From King's Cross on Northern line, should reach Euston
      const nextStations = result.current.getNextStations('940GZZLUKSX', 'northern')
      expect(nextStations).toHaveLength(1)
      expect(nextStations[0].tfl_id).toBe('940GZZLUEUS')
      expect(nextStations[0].name).toBe('Euston')

      unmount()
    })

    it('should return different stations for different lines', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // From King's Cross on Circle line, should reach Embankment
      const nextStations = result.current.getNextStations('940GZZLUKSX', 'circle')
      expect(nextStations).toHaveLength(1)
      expect(nextStations[0].tfl_id).toBe('940GZZLUEMB')

      unmount()
    })

    it('should return empty array for station with no connections', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Embankment has no connections in our mock graph
      const nextStations = result.current.getNextStations('940GZZLUEMB', 'northern')
      expect(nextStations).toEqual([])

      unmount()
    })

    it('should return empty array when data not loaded', () => {
      vi.mocked(api.getNetworkGraph).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      )

      const { result, unmount } = renderHook(() => useTflData())

      const nextStations = result.current.getNextStations('940GZZLUKSX', 'northern')
      expect(nextStations).toEqual([])

      unmount()
    })
  })

  describe('getLinesForStation', () => {
    it('should return lines serving a station', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const linesAtKingsCross = result.current.getLinesForStation('940GZZLUKSX')
      expect(linesAtKingsCross).toHaveLength(3)
      expect(linesAtKingsCross.map((l) => l.tfl_id)).toEqual(['northern', 'victoria', 'circle'])

      const linesAtEuston = result.current.getLinesForStation('940GZZLUEUS')
      expect(linesAtEuston).toHaveLength(2)
      expect(linesAtEuston.map((l) => l.tfl_id)).toEqual(['northern', 'victoria'])

      unmount()
    })

    it('should return empty array for non-existent station', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const lines = result.current.getLinesForStation('non-existent')
      expect(lines).toEqual([])

      unmount()
    })

    it('should return empty array when data not loaded', () => {
      vi.mocked(api.getStations).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      )

      const { result, unmount } = renderHook(() => useTflData())

      const lines = result.current.getLinesForStation('940GZZLUKSX')
      expect(lines).toEqual([])

      unmount()
    })
  })

  describe('getLineById', () => {
    it('should return line by UUID', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const line = result.current.getLineById('line-1')
      expect(line).toBeDefined()
      expect(line?.tfl_id).toBe('northern')
      expect(line?.name).toBe('Northern')

      unmount()
    })

    it('should return undefined for non-existent ID', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const line = result.current.getLineById('non-existent')
      expect(line).toBeUndefined()

      unmount()
    })
  })

  describe('getStationByTflId', () => {
    it('should return station by TfL ID', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const station = result.current.getStationByTflId('940GZZLUKSX')
      expect(station).toBeDefined()
      expect(station?.name).toBe("King's Cross St. Pancras")

      unmount()
    })

    it('should return undefined for non-existent TfL ID', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const station = result.current.getStationByTflId('non-existent')
      expect(station).toBeUndefined()

      unmount()
    })
  })

  describe('refresh', () => {
    it('should refetch all data', async () => {
      const { result, unmount } = renderHook(() => useTflData())

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(api.getLines).toHaveBeenCalledTimes(1)
      expect(api.getStations).toHaveBeenCalledTimes(1)
      expect(api.getNetworkGraph).toHaveBeenCalledTimes(1)

      // Manually refresh
      await act(async () => {
        await result.current.refresh()
      })

      expect(api.getLines).toHaveBeenCalledTimes(2)
      expect(api.getStations).toHaveBeenCalledTimes(2)
      expect(api.getNetworkGraph).toHaveBeenCalledTimes(2)

      unmount()
    })
  })
})
