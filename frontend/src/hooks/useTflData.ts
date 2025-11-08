import { useState, useEffect, useCallback } from 'react'
import {
  type LineResponse,
  type StationResponse,
  type NetworkGraph,
  ApiError,
  getLines as apiGetLines,
  getStations as apiGetStations,
  getNetworkGraph as apiGetNetworkGraph,
} from '../lib/api'

export interface UseTflDataReturn {
  // State
  lines: LineResponse[] | null
  stations: StationResponse[] | null
  networkGraph: NetworkGraph | null
  loading: boolean
  error: ApiError | null

  // Helper functions
  getStationsForLine: (lineTflId: string) => StationResponse[]
  getNextStations: (currentStationTflId: string, currentLineTflId: string) => StationResponse[]
  getLinesForStation: (stationTflId: string) => LineResponse[]
  getLineById: (lineId: string) => LineResponse | undefined
  getStationByTflId: (stationTflId: string) => StationResponse | undefined

  // Actions
  refresh: () => Promise<void>
}

/**
 * Hook for managing TfL data (lines, stations, network graph)
 *
 * This hook fetches and caches TfL reference data needed for route building.
 * It automatically loads all data on mount and provides helper functions for
 * filtering stations by line, finding connected stations, etc.
 *
 * @returns UseTflDataReturn object with state and helper methods
 *
 * @example
 * const { lines, stations, networkGraph, loading, getNextStations } = useTflData()
 *
 * // Get stations reachable from current station on a specific line
 * const nextStations = getNextStations('940GZZLUKSX', 'northern')
 *
 * // Get all stations on a line
 * const circleStations = getStationsForLine('circle')
 */
export function useTflData(): UseTflDataReturn {
  const [lines, setLines] = useState<LineResponse[] | null>(null)
  const [stations, setStations] = useState<StationResponse[] | null>(null)
  const [networkGraph, setNetworkGraph] = useState<NetworkGraph | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  /**
   * Fetch all TfL data from API
   */
  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch all data in parallel
      const [linesData, stationsData, graphData] = await Promise.all([
        apiGetLines(),
        apiGetStations(),
        apiGetNetworkGraph(),
      ])

      setLines(linesData)
      setStations(stationsData)
      setNetworkGraph(graphData)
    } catch (err) {
      setError(err as ApiError)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  /**
   * Initial fetch on mount
   */
  useEffect(() => {
    refresh().catch(() => {
      // Error already set in state
    })
  }, [refresh])

  /**
   * Get all stations that serve a specific line
   *
   * @param lineTflId The TfL ID of the line (e.g., 'northern', 'victoria')
   * @returns Array of stations on that line
   */
  const getStationsForLine = useCallback(
    (lineTflId: string): StationResponse[] => {
      if (!stations) return []
      return stations.filter((station) => station.lines.includes(lineTflId))
    },
    [stations]
  )

  /**
   * Get stations reachable from the current station on a specific line
   *
   * Uses the network graph to find connected stations. Filters connections
   * to only include those on the specified line.
   *
   * @param currentStationTflId TfL ID of current station
   * @param currentLineTflId TfL ID of current line
   * @returns Array of reachable stations on the specified line
   */
  const getNextStations = useCallback(
    (currentStationTflId: string, currentLineTflId: string): StationResponse[] => {
      if (!networkGraph || !stations) return []

      // Get connections from current station
      const connections = networkGraph[currentStationTflId] || []

      // Filter to connections on the current line
      const reachableStationTflIds = connections
        .filter((conn) => conn.line_tfl_id === currentLineTflId)
        .map((conn) => conn.station_tfl_id)

      // Return station details for reachable stations
      return stations.filter((station) => reachableStationTflIds.includes(station.tfl_id))
    },
    [networkGraph, stations]
  )

  /**
   * Get all lines that serve a specific station
   *
   * @param stationTflId The TfL ID of the station
   * @returns Array of lines serving that station
   */
  const getLinesForStation = useCallback(
    (stationTflId: string): LineResponse[] => {
      if (!stations || !lines) return []

      const station = stations.find((s) => s.tfl_id === stationTflId)
      if (!station) return []

      return lines.filter((line) => station.lines.includes(line.tfl_id))
    },
    [stations, lines]
  )

  /**
   * Get a line by its ID
   *
   * @param lineId The UUID of the line
   * @returns Line details or undefined if not found
   */
  const getLineById = useCallback(
    (lineId: string): LineResponse | undefined => {
      if (!lines) return undefined
      return lines.find((line) => line.id === lineId)
    },
    [lines]
  )

  /**
   * Get a station by its TfL ID
   *
   * @param stationTflId The TfL ID of the station
   * @returns Station details or undefined if not found
   */
  const getStationByTflId = useCallback(
    (stationTflId: string): StationResponse | undefined => {
      if (!stations) return undefined
      return stations.find((station) => station.tfl_id === stationTflId)
    },
    [stations]
  )

  return {
    lines,
    stations,
    networkGraph,
    loading,
    error,
    getStationsForLine,
    getNextStations,
    getLinesForStation,
    getLineById,
    getStationByTflId,
    refresh,
  }
}
