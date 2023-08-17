//const config = require('../utils/config')
const logger = require('../utils/logger')
const tfl_query = require('./tfl_api.query')
const config = require('../utils/config')

import { z } from "zod";
import { DataWithTTL, APIResponse, TfLAPIQuery } from './tfl_service_types'



// importt the ManagedTfL_types types
// import TfLResponse from '../tfl_service/TfLResponse_types'

// import { TfLResponse.RouteSequenceSchema, TfLResponse.StopPointSequenceSchema, TfLResponse.MatchedStopSchema, TfLResponse.IdentifierSchema, , TfLResponse.StopPointArraySchema } from '../tfl_service/TfLResponseTypesZod'
import * as TfLResponse from '../tfl_service/TfLResponseTypesZod'


const query_cache = require('./cache')

const structure_cached_value = function (cached_value: Object, cache_ttl: number): DataWithTTL {
  /**
   * structures cached value for return
   *
   * @param {Object} cached_value - the cached value
   * @param {Number} cache_ttl - the cache key
   * @returns {Object} - the structured cached value with .data and .ttl properties
   *
   */

  const currentDate = new Date()
  let remaining_ttl = 0
  if (cache_ttl > 0) {
    remaining_ttl = Math.floor((cache_ttl - currentDate.getTime()) / 1000)
  }
  else {
    remaining_ttl = cache_ttl
  }
  return { data: cached_value, ttl: remaining_ttl }
}

const call_query_throw_on_error: TfLAPIQuery = async function (querystring, params): Promise<APIResponse> {
  /**
   * calls the query and catches errors
   * @param {Function} query - the query to call
   * @param {String} querystring - the querystring to pass to the query
   * @param {Object} params - the params to pass to the query
   * @returns {Object} - the response from the query
   * @throws {Error} - if the query fails
   * @throws {Error} - if the query returns an error
   * @throws {Error} - if the query returns a status code other than 200
   * */
  const tfl_response: APIResponse = await tfl_query.query(querystring, params)
  if (tfl_response.success === false) {
    throw new Error(`Error calling TfL API to query: ${tfl_response.error}`)
  }
  return tfl_response
}

function summarise_lineStatuses(line) {
  /**
   * summarises disruption data for a given line
   * @param {Object} linestatus - the line to summarise
   * @returns {Object} - the summarised disruption data
   *
   */
  //TODO: extract [lineStatuses] from line as a map
  return line.lineStatuses.map((lineStatus) => {
    const base_disruption = create_base_disruption(lineStatus)
    let disrupted_route = {}
    if (lineStatus.disruption !== undefined && lineStatus.disruption.affectedRoutes !== undefined && lineStatus.disruption.affectedRoutes.length > 0) {
      disrupted_route = summarise_disruption_routes(lineStatus.disruption.affectedRoutes)
    }
    return {
      ...base_disruption,
      // if disruption is not empty, return it, otherwise return false
      ...(disrupted_route !== {}) && { affectedRoutes: disrupted_route },
    }
  })

  function create_base_disruption(lineStatus) {
    return {
      status: lineStatus.statusSeverityDescription,
      reason: lineStatus.reason,
      severity: lineStatus.statusSeverity,
      validityPeriods: lineStatus.validityPeriods.map((validityPeriod) => {
        return {
          from: validityPeriod.fromDate,
          to: validityPeriod.toDate
        }
      })
    }
  }

  function summarise_disruption_routes(affected_routes) {
    /**
     * summarises teh affectedRoutes array
     * @param {Array} affected_routes - the affectedRoutes array
     * @returns {Array} - the summarised affectedRoutes array
     *
     */

    return affected_routes.map((affected_route) => {
      return {
        id: affected_route.id,
        name: affected_route.name,
        direction: affected_route.direction,
        originationName: affected_route.originationName,
        destinationName: affected_route.destinationName,
        isEntireRouteSection: affected_route.isEntireRouteSection,
        routeSections: affected_route.routeSectionNaptanEntrySequence.map((routeSection) => {
          return {
            ordinal: routeSection.ordinal,
            naptanId: routeSection.stopPoint.naptanId,
            name: routeSection.stopPoint.commonName
          }
        })
      }
    })
  }
}

function extract_disruption(tfl_response_data) {
  /**
   * extracts disruption data from tfl response
   *
   * @param {Object} tfl_response - the response from the tfl api
   * @returns {Object} - the disruption data from the tfl response
   */
  const disruption_data = tfl_response_data.map((line) => {
    return {
      id: line.id,
      name: line.name,
      modeName: line.modeName,
      disruptions: summarise_lineStatuses(line)
    }
  })
  return disruption_data
}

async function get_disruption(for_modes, detailed = false) {
  /**
   * fetches disruptions from tfl for given modes
   *
   * @param {Boolean} detailed - whether to fetch detailed disruption information
   * @param {Array} for_modes - array of modes to fetch disruptions for
   * @returns {Array} - array of lines with disruption data
   */
  if (!Array.isArray(for_modes)) {
    throw new Error('for_modes must be an array')
  }
  const modes = for_modes.join(',')
  const cache_key = `disruption-${modes}-${detailed}`
  const cached_value = query_cache.get(cache_key)

  if (cached_value) {
    logger.debug(`${cache_key} cache hit`)
    return structure_cached_value(cached_value, query_cache.getTtl(cache_key))
  } else {
    logger.debug(`${cache_key} cache miss`)
    const disruption_api_query = `Line/Mode/${modes}/Status`
    const api_response = await tfl_query.query(disruption_api_query, { detail: detailed })
    const disruption = {
      data: extract_disruption(api_response.data),
      ttl: api_response.ttl
    }
    query_cache.set(cache_key, disruption.data, disruption.ttl)
    return disruption
  }
}

async function get_line_stoppoints(line_id: string): Promise<DataWithTTL> {
  /**
   * fetches stoppoints for a given line in order
   *
   * @param {String} line_id - the line ID
   * @returns {Array} - line object with an array of stoppoints
   *
   */
  const cache_key = `line_stoppoints-${line_id}`
  const cached_value = query_cache.get(cache_key)
  if (cached_value) {
    logger.debug(`${cache_key} cache hit`)

    return structure_cached_value(cached_value, query_cache.getTtl(cache_key))
  }
  else {
    logger.debug(`${cache_key} cache miss`)
    const line_stoppoints_api_query = `Line/${line_id}/StopPoints`
    const tfl_response = await call_query_throw_on_error(line_stoppoints_api_query)
    const line_stoppoints = TfLResponse.stopPointArraySchema.parse(tfl_response.data)
    const stoppoint_data = extract_stoppoints_from_stoppoint_array(line_stoppoints)
    query_cache.set(cache_key, stoppoint_data, tfl_response.ttl)
    return { data: stoppoint_data, ttl: tfl_response.ttl }
  }
}


async function get_line_stoppoints_in_order(line_id: string): Promise<DataWithTTL> {
  /**
   * fetches stoppoints for a given line in order
   *
   * @param {String} line_id - the line ID
   * @returns {Array} - array of line object with an array of stoppoints and other metadata
   *
   */
  const cache_key = `line_stoppoints_ordered-${line_id}`
  const cached_value = query_cache.get(cache_key)
  if (cached_value) {
    logger.debug(`${cache_key} cache hit`)

    return structure_cached_value(cached_value, query_cache.getTtl(cache_key))
  }
  else {
    logger.debug(`${cache_key} cache miss`)
    const line_stoppoints_api_query = `Line/${line_id}/Route/Sequence/all`
    const line_stoppoints = await call_query_throw_on_error(line_stoppoints_api_query, { excludeCrowding: true })
    const tfl_response = TfLResponse.routeSequenceSchema.parse(line_stoppoints.data)
    const stoppoint_sequences = tfl_response.stopPointSequences
    const directional_points = stoppoint_sequences.map(sp => get_matchedStoppoints(sp))
    query_cache.set(cache_key, directional_points, line_stoppoints.ttl)
    return { data: directional_points, ttl: line_stoppoints.ttl }
  }
}

function get_matchedStoppoints(stoppoint: z.infer<typeof TfLResponse.stopPointSequenceSchema>) {

  return {
    id: stoppoint.lineId,
    lineName: stoppoint.lineName,
    branchId: stoppoint.branchId,
    nextBranchIds: stoppoint.nextBranchIds,
    prevBranchIds: stoppoint.prevBranchIds,
    direction: stoppoint.direction,
    points: extract_stoppoints_from_MatchedStop_array(stoppoint.stopPoint)
  }

}

function extract_stoppoints_from_MatchedStop_array(MatchedStop_array: z.infer<typeof TfLResponse.matchedStopSchema>[]) {
  return MatchedStop_array.map((sp) => {
    return {
      id: sp.id,
      type: 'StopPoint',
      name: sp.name, // ('name' in sp) ? sp['name'] : sp['commonName'],
      naptanId: sp.stationId === undefined ? null : sp.stationId, // ('stationId' in sp) ? sp['stationId'] : sp['naptanId'],
      lat: sp.lat, // ['lat'],
      lon: sp.lon, //['lon'],
      modes: sp.modes, //['modes'],
      lines: sp.lines.map((l) => l.id)
    }
  }
  )
}

function extract_stoppoints_from_stoppoint_array(stoppoint_array: z.infer<typeof TfLResponse.stopPointArraySchema>) {
  return stoppoint_array.map((sp) => {
    return {
      id: sp['id'],
      type: 'StopPoint',
      name: ('name' in sp) ? sp['name'] : sp['commonName'],
      naptanId: ('stationId' in sp) ? sp['stationId'] : sp['naptanId'],
      lat: sp['lat'],
      lon: sp['lon'],
      modes: sp['modes'],
      lines: get_lines_from_lineModeGroups(sp['lineModeGroups']) // sp['lines'].map(l => simplify_line(l))
    }
  }
  )
}

function get_lines_from_lineModeGroups(linemodegroups: z.infer<typeof TfLResponse.lineModeGroupSchema>[]) {
  return linemodegroups.map((lmg) => {
    const mode = lmg['modeName']
    if (!config.modes_of_transport.includes(mode)) {
      return []
    }
    return lmg['lineIdentifier'].map((line) => {
      return {
        id: line,
        mode: mode
      }
    })
  }).flat()
}


async function get_lines_for_mode(modes = ['tube', 'dlr', 'overground', 'elizabeth-line']): Promise<DataWithTTL> {
  /**
   * fetches lines from tfl for given modes
   *
   * @param {Array} modes - array of modes to fetch lines for
   * @returns {Array} - array of lines including the name and ID of the originating and terminating stations
   *
   */
  if (!Array.isArray(modes)) {
    throw new Error('modes must be an array')
  }

  const cache_key = `all_lines-${modes}`
  const cached_value = query_cache.get(cache_key)
  if (cached_value) {
    logger.debug(`${cache_key} cache hit`)

    return structure_cached_value(cached_value, query_cache.getTtl(cache_key))
  }
  else {
    logger.debug(`${cache_key} cache miss`)
    const all_lines_api_query = `Line/Mode/${modes}/Route`
    const tfl_response = await tfl_query.query(all_lines_api_query)
    const all_lines = TfLResponse.lineArraySchema.parse(tfl_response.data)
    const all_lines_summarised = all_lines.map((line) => {
      return {
        id: line.id,
        name: line.name,
        modeName: line.modeName,
        serviceTypes: line.serviceTypes.map((st) => st.name)
      }
    })

    query_cache.set(cache_key, all_lines_summarised, tfl_response.ttl)
    return { data: all_lines_summarised, ttl: tfl_response.ttl }
  }
}

module.exports = {
  structure_cached_value,
  get_disruption,
  get_line_stoppoints,
  get_lines_for_mode,
  get_line_stoppoints_in_order

}