const config = require('../utils/config')
const Gremlin = require('gremlin')
const logger = require('../utils/logger')
const helpers = require('../utils/helpers')

const fs = require('fs')

const gremlin_db_string = `/dbs/${config.graph_database}/colls/${config.graph_stoppoint_colleciton}`
const stoppoint_authenticator = new Gremlin.driver.auth.PlainTextSaslAuthenticator(gremlin_db_string, config.graph_primary_key)

const stoppoint_client = new Gremlin.driver.Client(
  config.GRAPH_DATABASE_ENDPOINT,
  {
    authenticator: stoppoint_authenticator,
    traversalsource: 'g',
    rejectUnauthorized: true,
    mimeType: 'application/vnd.gremlin-v2.0+json'
  }
)

async () => {
  const haveOpened = await stoppoint_client.open()
  logger.info('opened graphdb client: ', haveOpened)
}


function escape_gremlin_special_characters(str) {
  /**
   * Escapes special characters in a string for use in gremlin queries
   * from http://groovy-lang.org/syntax.html#_escaping_special_characters
   * @param {String} str - string to escape
   * @returns {String} - escaped string
   *
   *
   * Escape sequence	Character
   * \b -> backspace
   * \f -> formfeed
   * \n ->  newline
   * \r -> carriage return
   * \s -> single space
   * \t -> tabulation
   * \\ -> backslash
   * \' -> single quote within a single-quoted string (and optional for triple-single-quoted and double-quoted strings)
   * \" -> double quote within a double-quoted string (and optional for triple-double-quoted and single-quoted strings)
   *
   */
  let interim = str.replaceAll(/\\/g, '\\\\') // do this first so we don't escape the other escapes
  interim = interim.replaceAll(/\cH/g, '\\b') // match backspace
  interim = interim.replaceAll(/\cL/g, '\\f') // match formfeed
  interim = interim.replaceAll(/\n/g, '\\n')  // match newline
  interim = interim.replaceAll(/\cM/g, '\\r') // match carriage return
  interim = interim.replaceAll(/\t/g, '\\t')  // match tab
  interim = interim.replaceAll(/'/g, '\\\'')  // match single quote
  interim = interim.replaceAll(/"/g, '\\"')   // match double quote
  return interim
}


const add_array_value = (arr, property_name) => {
  /**
   * Converts an array to a string containing the same property
   * with each different value ('multi-properties')
   * see https://tinkerpop.apache.org/docs/current/reference/#vertex-properties
   * @param {Array} arr - array to convert
   * @returns {String} - list of .property entries
   */
  const items = arr.map((item) => `.property('${property_name}', '${escape_gremlin_special_characters(item)}')`).join('\n')

  return items
}

const add_stoppoint = async (stoppoint, upsert = true) => {
  /**
   * Adds a stoppoint to the graphdb.
   * a stoppoint is an object with teh following properties:
   * id, type, name, naptanId, stationNaptan, lat, lon, modes, lines
   *
   * @param {object} stoppoint - stoppoint object
   * @returns {Promise} - pending query to graphdb
   */

  // construct a query to add the stoppoint to the graphdb
  const add_query = `addV('${stoppoint['type']}')
  .property('id', '${stoppoint['id']}')
  .property('name', '${escape_gremlin_special_characters(stoppoint['name'])}')
  .property('naptanId', '${stoppoint['naptanId']}')
  .property('lat', '${stoppoint['lat']}')
  .property('lon', '${stoppoint['lon']}')
  ${add_array_value(stoppoint['modes'], 'modes')}
  ${add_array_value(stoppoint['lines'], 'lines')}`

  // if upsert is true, then we want to wrap the add_query in an upsert
  const with_upsert = `V('${stoppoint.id}')
  .fold()
  .coalesce(
    unfold(),
    ${add_query}
    )`

  // if upsert is false, then we just want to run the add_query
  const query = `g.${upsert ? with_upsert : add_query}`
  // log the query, removing the newlines
  // logger.debug(query.replace(/\n/g, ''))

  const result = await execute_query(stoppoint_client, query, 5)
  const serialized_items = serialize_stoppoint(result['data']['_items'])
  return { ...result, data: serialized_items }
}

const add_line = async (line_edge, upsert = true) => {
  // add a line to the graphdb
  // a line is an object with the following properties:
  // id, name, modeName, modeId, routeSections

  const line_id = line_edge['id']

  // logger.debug(`adding line ${line_id} to graphdb`)

  const add_query = `addE('TO')
                    .from(g.V('${line_edge['from']}'))
                    .to(g.V('${line_edge['to']}'))
                    .property('id', '${line_edge['id']}')
                    .property('line', '${line_edge['lineName']}')
                    .property('branch', '${line_edge['branchId']}')
                    .property('direction', '${line_edge['direction']}')`

  const with_upsert = `E('${line_edge['id']}')
                      .fold()
                      .coalesce(
                        unfold(),
                        ${add_query}
                        )`

  const query = `g.${upsert ? with_upsert : add_query}`

  // submit the query to the graphdb
  //logger.debug(query.replace(/\n/g, ''))
  const result = await execute_query(stoppoint_client, query, 5)
  const serialized_items = serialize_stoppoint(result['data']['_items'])
  return { ...result, data: serialized_items }

}

const find_route_between_stops = async (starting_stop, ending_stop, line) => {
  /**
   * Finds a route between two stops on a given line
   * @param {String} starting_stop - id of the starting stop
   * @param {String} ending_stop - id of the ending stop
   * @param {String} line - line to search on
   * @returns {Array} - array of stop ids
   * @returns {null} - if no route is found
   */

  // construct a query to find the route between the two stops
  const query = 'g.V(source).repeat(outE().has(\'line\', line).inV().as(\'v\').simplePath()).until(hasId(target)).path()'
  const params = {
    source: starting_stop,
    target: ending_stop,
    line: line
  }
  const result = await execute_query(stoppoint_client, query, 5, params)
  const simplified_routes = simplify_discovered_route(result)

return { ...result, data: simplified_routes }
}

const simplify_discovered_route = (route_result) => {
  /**
   * Simplifies the result of a route query
   * @param {Object} route_result - result of a route query
   * @returns {??} - array of stoppoints and lines
   */
  // there can be more than one route found
  const route_items = route_result['data']['_items']
  // logger.debug(`found ${route_items.length} routes`)
  // logger.debug(route_items)
  const simplified_routes = route_items.map((route) => {
    // each route is an array of vertices (stoppoints) and edges (lines)
    // we want to simplify the data that's returned
    // first, check if it's a stoppoint (label = 'stoppoint') or a line (label = 'TO')
    // if it's a stoppoint, use serialize_stoppoint
    // if it's a line, use serialize_line
    const simplified_route = route['objects'].map((item) => {
      if (item['label'] === 'stoppoint') {
        return serialize_stoppoint([item])[0]
      } else if (item['label'] === 'TO') {
        return serialize_line(item)
      }
    })
    return simplified_route
  })
  return simplified_routes
}

const serialize_line = (line) => {
  /**
   * Serializes a line object
   * @param {Object} line - line object
   * @returns {Object} - serialized line object
   */
  /*
              "id": "9ly2c-2-7u1eg-zlqov",
            "label": "TO",
            "type": "edge",
            "inVLabel": "stoppoint",
            "outVLabel": "stoppoint",
            "inV": "zlqov",
            "outV": "7u1eg",
            "properties": {
              "line": "9ly2c",
              "branch": "2",
              "direction": "o3942"
            }
            */
  const serialized_line = {
    id: line['id'],
    from: line['outV'],
    to: line['inV'],
    ...serializeProperties(line['properties'])
  }
  return serialized_line
}


const execute_query = async (client, query, maxAttempts, params = null) => {
  /**
   * Retry a function up to a maximum number of attempts
   * adapted from https://solutional.ee/blog/2020-11-19-Proper-Retry-in-JavaScript.html
   *
   * @param {String} query - query to execute
   * @param {Number} maxAttempts - maximum number of attempts to execute the query
   *
   * @returns {String} - result of the query
   */
  let retry_time = 1000
  const execute = async (attempt) => {
    if (attempt > 1) { logger.debug(`attempt ${attempt} of ${maxAttempts}`) }
    try {
      if (params) {
        logger.debug(`executing query with params: ${JSON.stringify(params)}`)
      }
      const client_result = await client.submit(query, params)
      // if we got the result, then we can return it
      const ms_status_code = client_result['statusAttributes'] ? client_result['statusAttributes']['x-ms-status-code'] : null

      // this is distinct to an ADD query, so move to that
      // const seralised_result = serializeGremlinResults(client_result['_items'])
      return { data: client_result, success: true, status_code: ms_status_code }
    } catch (err) {
      const ms_status_code = err['statusAttributes'] ? err['statusAttributes']['x-ms-status-code'] : null
      const ms_retry_after = err['statusAttributes'] ? err['statusAttributes']['x-ms-retry-after-ms'] : null
      // we need to retry after ms_retry_after ms
      if (ms_retry_after) { retry_time = stringToMilliseconds(ms_retry_after) }
      if ([429, 408, 449].includes(ms_status_code) && attempt <= maxAttempts - 1) {
        // other, recoverable codes which we can retry
        // https://learn.microsoft.com/en-us/rest/api/cosmos-db/http-status-codes-for-cosmosdb
        // 429, 408, 449
        const nextAttempt = attempt + 1
        const delayInMs = retry_time ? retry_time : Math.max(Math.min(Math.pow(2, nextAttempt) + randInt(-nextAttempt, nextAttempt), 5), 1)
        logger.error(`Retrying after ${delayInMs} ms due to:`, err)
        return delay(() => execute(nextAttempt), delayInMs)
      } else {
        // any other error
        // including non-recoverable codes
        // 400, 401, 403, 404, 409, 412, 413, 500, 503
        // if we dont have ms_status_code, then return the whole err object
        return { success: false, error: ms_status_code ? err['statusMessage'] : err, status_code: ms_status_code }
      }
    }
  }
  const final_result = await execute(1)
  return final_result
}

function serialize_stoppoint(results) {
  /**
   * Serialise the results of a gremlin query
   * return an array of objects.
   * The gremlin 'properties' key is flattened into the object
   * If a property has multiple values, then the value is an array
   * If a property has a single value, then the value is a string
   * @param {Array} results - results of a gremlin query
   * @returns {Array} - array of objects
   */

  let serializedResults = []
  results.forEach(result => {
    serializedResults.push({
      id: result.id,
      label: result.label,
      type: result.type,
      ...serializeProperties(result.properties)
    })
  })
  return serializedResults
}

function stringToMilliseconds(timeString) {
  /** 
   * Convert a string in the format HH:MM:SS.mmm to milliseconds
   * @param {String} timeString - string in the format HH:MM:SS.mmm
   * @returns {Number} - time in milliseconds
   */
  const [hours, minutes, seconds] = timeString.split(':');
  const milliseconds = Math.round(parseFloat(`0.${seconds.split('.')[1]}`) * 1000)
  return (hours * 3600 + minutes * 60 + parseInt(seconds, 10)) * 1000 + milliseconds;
}

function serializeProperties(properties) {
  let serializedProperties = {}
  Object.keys(properties).forEach(key => {
    const value = properties[key]
    if (Array.isArray(value)) {
      serializedProperties[key] = value.map(item => safe_get_property(item, 'value'))
      if (serializedProperties[key].length === 1) {
        serializedProperties[key] = serializedProperties[key][0]
      }
    } else {
      // not an array
      serializedProperties[key] = value
    }
  })
  return serializedProperties
}

function safe_get_property(obj, key) {
  return obj[key] ? obj[key] : null
}


const delay = (fn, ms) => new Promise((resolve) => setTimeout(() => resolve(fn()), ms))

const randInt = (min, max) => Math.floor(Math.random() * (max - min + 1) + min)

module.exports = {
  add_stoppoint,
  add_line,
  find_route_between_stops,
  escape_gremlin_special_characters,
  serializeProperties,
  serialize_stoppoint,
  serialize_line,
  stringToMilliseconds,
  safe_get_property,
  execute_query
}