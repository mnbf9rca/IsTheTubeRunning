const config = require('../utils/config')
const Gremlin = require('gremlin')
const logger = require('../utils/logger')
const helpers = require('../utils/helpers')

const fs = require('fs')

const gremlin_db_string = `/dbs/${config.graph_database}/colls/${config.graph_stoppoint_colleciton}`
const stoppoint_authenticator = new Gremlin.driver.auth.PlainTextSaslAuthenticator(gremlin_db_string, config.cosmos_primary_key)

const stoppoint_client = new Gremlin.driver.Client(
  config.COSMOS_ENDPOINT,
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

async function close() {
  await stoppoint_client.close()
  const haveClosed = !stoppoint_client.isOpen
  logger.info('closed graphdb client: ', haveClosed)
}

function escape_string(str) {
  return str.replace(/'/g, '\\\'')
}

const add_array_value = (arr, property_name) => {
  /**
   * Converts an array to a string containing the same property
   * with each different value ('multi-properties')
   * see https://tinkerpop.apache.org/docs/current/reference/#vertex-properties
   * @param {Array} arr - array to convert
   * @returns {String} - list of .property entries
   */
  const items = arr.map((item) => `.property('${property_name}', '${escape_string(item)}')`).join('\n')

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
                      .property('name', '${escape_string(stoppoint['name'])}')
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
  try {
    const result = await execute_query(stoppoint_client, query, 5)
    return result
  }
  catch (err) {
    logger.error(err)
    return [{ success: false }]
  }

}

const add_line = async (line_edge, upsert = true) => {
  // add a line to the graphdb
  // a line is an object with the following properties:
  // id, name, modeName, modeId, routeSections

  // if !(line_edge) then silently skip
  if (!(line_edge)){
    return
  }


  if (!(Object.prototype.hasOwnProperty.call(line_edge, 'id'))){
    logger.error('line_edge does not have an id')
    return [{ success: false }]
  }

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
  try {
    const result = await execute_query(stoppoint_client, query, 5)
    return result
  }
  catch (err) {
    logger.error(err)
    return [{ success: false }]
  }


}

const execute_query = async (client, query, maxAttempts) => {
  /**
   * Retry a function up to a maximum number of attempts
   * adapted from https://solutional.ee/blog/2020-11-19-Proper-Retry-in-JavaScript.html
   *
   * @param {String} query - query to execute
   * @param {Number} maxAttempts - maximum number of attempts to execute the query
   *
   * @returns {String} - result of the query
   */


  let retry_time_in_ms = 1000
  const execute = async (attempt) => {
    if (attempt > 1) {
      logger.debug(`attempt ${attempt} of ${maxAttempts}`)
    }
    try {
      return await call_client_submit_and_structure_results(client, query)
    } catch (err) {
      let ms_status_code
      ({ ms_status_code, retry_time: retry_time_in_ms } = get_status_code_and_retry_time(err))
      if ([429, 408, 449].includes(ms_status_code) && attempt <= maxAttempts - 1) {
        // recoverable codes which we can retry are 429, 408, 449
        // https://learn.microsoft.com/en-us/rest/api/cosmos-db/http-status-codes-for-cosmosdb
        const nextAttempt = attempt + 1
        const delayInMs = retry_time_in_ms ? retry_time_in_ms : Math.max(Math.min(Math.pow(2, nextAttempt) + randInt(-nextAttempt, nextAttempt), 5), 1)
        logger.error(`Retrying after ${delayInMs}`)// ms due to:`, err.statusMessage)
        return delay(() => execute(nextAttempt), delayInMs)
      } else {
        // any other error including non-recoverable codes
        // 400, 401, 403, 404, 409, 412, 413, 500, 503
        const newError = new Error(`Error executing query: '${query}'`)
        newError.originalError = err
        throw newError
      }
    }
  }
  //const final_result = await execute(1)
  return execute(1) //final_result
}

function get_status_code_and_retry_time(err) {
  const ms_status_code = Object.prototype.hasOwnProperty.call(err, 'statusAttributes') ? err['statusAttributes']['x-ms-status-code'] : null
  const ms_retry_after = (Object.prototype.hasOwnProperty.call(err, 'statusAttributes') && Object.prototype.hasOwnProperty.call(err.statusAttributes, 'x-ms-retry-after-ms')) ? err['statusAttributes']['x-ms-retry-after-ms'] : null
  // we need to convert ms_retry_after from a timestring to milliseconds
  let retry_time_in_ms
  ms_retry_after ?  retry_time_in_ms = stringToMilliseconds(ms_retry_after) : retry_time_in_ms = null
  return { ms_status_code, retry_time_in_ms }
}

async function call_client_submit_and_structure_results(client, query) {
  const client_result = await client.submit(query)
  // if we got the result, then we can return it
  const ms_status_code = Object.prototype.hasOwnProperty.call(client_result, 'statusAttributes') ? client_result['statusAttributes']['x-ms-status-code'] : client_result['attributes']['x-ms-status-code']

  const seralised_result = serializeGremlinResults(client_result['_items'])
  return { data: seralised_result, success: true, status_code: ms_status_code }
}

function serializeGremlinResults(results) {
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
    // might be a single value or an array of values
    if (!Array.isArray(value)) {
      serializedProperties[key] = value
    }
    else {
      serializedProperties[key] = value.map(item => item.value)
    }
    /*else if (value.length > 1) {
      serializedProperties[key] = value.map(item => item.value)
    } else {
      serializedProperties[key] = value[0].value
    }*/
  })
  return serializedProperties
}


const delay = (fn, ms) => new Promise((resolve) => setTimeout(() => resolve(fn()), ms))

const randInt = (min, max) => Math.floor(Math.random() * (max - min + 1) + min)

module.exports = { add_stoppoint, add_line, close }