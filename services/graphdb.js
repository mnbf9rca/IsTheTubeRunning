const config = require('../utils/config')
const { execute_query } = require('./graphdb.execute')
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

const add_user = async (user, upsert = false) => {
  /**
   * Adds a user to the graphdb.
   * user has: email, hashed_password, password_salt, email_verified, active_user, and an array of [journeys]
   * they may optionally have last_login, firstname, lastname
   * @param {object} user - user object
   * @returns {Promise} - pending query to graphdb
   */
  if (upsert) {
    logger.warn('upsert not implemented for add_user')
    throw new Error('upsert not implemented for add_user')
  }
  // construct a query to add the user to the graphdb
  const add_query = `addV('user')
  .property('email', email)
  .property('hashed_password', hashed_password)
  .property('password_salt', password_salt)
  .property('email_verified', '${user['email_verified']}')
  .property('active_user', '${user['active_user']}')
  .property('firstname', firstname)
  .property('lastname', lastname)
  .property('email', email)
  ${add_array_value(user['journeys'], 'journeys')}
  ${user['last_login'] ? `.property('last_login', '${user['last_login']}')` : ''}`

  // as this contains user data, we need to pass these values as parameters
  const params =   {
    email: user['email'],
    firstname: user['firstname'],
    lastname: user['lastname'],
    hashed_password: user['hashed_password'],
    password_salt: user['password_salt']
  }

  const result = await execute_query(stoppoint_client, add_query, 5, params)
  return result

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



module.exports = {
  add_stoppoint,
  add_line,
  add_user,
  find_route_between_stops,
  escape_gremlin_special_characters,
  serializeProperties,
  serialize_stoppoint,
  serialize_line,
  safe_get_property}