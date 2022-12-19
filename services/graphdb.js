const Gremlin = require('gremlin')
const config = require('../utils/config')
const logger = require('../utils/logger')
const helpers = require('../utils/helpers')

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

function escape_string(str) {
  return str.replace(/'/g, '\\\'')
}

const add_stoppoint = async (stoppoint, upsert = false) => {
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
  .property('modes', '${stoppoint['modes']}')
  .property('lines', '${stoppoint['lines']}')`

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
  // submit the query to the graphdb
  //return await client.submit(query)
  // TODO - fix retry logic
  logger.debug('writing one StopPoint to graphdb')
  //return helpers.retry(function(){  stoppoint_client.submit(query) }, 5,2 )
  return execute_query(query, 5)

}



const add_line = async (line_edge, upsert = false) => {
  // add a line to the graphdb
  // a line is an object with the following properties:
  // id, name, modeName, modeId, routeSections
  logger.debug(`adding line ${line_edge.id} to graphdb`)


  const query = `g.E('${line_edge['id']}')
    .fold()
    .coalesce(
      unfold(),
      addE('TO')
      .from(g.V('${line_edge['from']}'))
      .to(g.V('${line_edge['to']}'))
      .property('id', '${line_edge['id']}')
      .property('line', '${line_edge['lineName']}')
      .property('branch', '${line_edge['branchId']}')
      .property('direction', '${line_edge['direction']}'))`
  // submit the query to the graphdb
  //logger.debug(query.replace(/\n/g, ''))

  return helpers.retry(function(){ stoppoint_client.submit(query)}, 5,2 )

}

const execute_query = async (query, maxAttempts) => {
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
    try {
      const result = await stoppoint_client.submit(query)
      if (Object.hasOwnProperty.call(result.attributes, 'x-ms-retry-after-ms') ) {
        retry_time = result.attributes['x-ms-retry-after-ms']
        throw new Error(`received x-ms-retry-after-ms - retrying after ${retry_time} ms`)
      }
    } catch (err) {
      if (attempt <= maxAttempts) {
        const nextAttempt = attempt + 1
        const delayInMs = retry_time ? retry_time : Math.max(Math.min(Math.pow(2, nextAttempt) + randInt(-nextAttempt, nextAttempt), 5), 1)
        console.error(`Retrying after ${delayInMs} seconds due to:`, err)
        return delay(() => execute(nextAttempt), delayInMs)
      } else {
        throw err
      }
    }
  }
  return execute(1)
}

const delay = (fn, ms) => new Promise((resolve) => setTimeout(() => resolve(fn()), ms))

const randInt = (min, max) => Math.floor(Math.random() * (max - min + 1) + min)

module.exports = { add_stoppoint, add_line }