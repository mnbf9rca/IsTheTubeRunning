//const Stoppoint = require('../models/Stoppoint')
import config from '../utils/config'
import GraphExecute from './graphdb.execute'
import Gremlin from 'gremlin'
import * as NetworkTypes from '../network/NetworkTypes';
import logger from '../utils/logger';



export function getGraphClient(){
  const gremlin_db_string = `/dbs/${config.graph_database_name}/colls/${config.graph_stoppoint_colleciton}`
  const stoppoint_authenticator = new Gremlin.driver.auth.PlainTextSaslAuthenticator(gremlin_db_string, config.cosmos_primary_key)
    return new Gremlin.driver.Client(
      config.COSMOS_ENDPOINT,
      {
        authenticator: stoppoint_authenticator,
        traversalsource: 'g',
        rejectUnauthorized: true,
        mimeType: 'application/vnd.gremlin-v2.0+json'
      }
    )
}

export async function connectGraphClient(client: Gremlin.driver.Client): Promise<void> {
  /* connects to the database */
  try {
    await client.open();
    logger.info('Connected to GraphDB');
  } catch (err) {
    logger.error(err);
    throw err;  // This will return a rejected Promise
  }
}


export function escape_gremlin_special_characters(str: string): string {
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
  .replaceAll(/\cH/g, '\\b') // match backspace
  .replaceAll(/\cL/g, '\\f') // match formfeed
  .replaceAll(/\n/g, '\\n')  // match newline
  .replaceAll(/\cM/g, '\\r') // match carriage return
  .replaceAll(/\t/g, '\\t')  // match tab
  .replaceAll(/'/g, '\\\'')  // match single quote
  .replaceAll(/"/g, '\\"')   // match double quote
  return interim;
}


export function add_array_value(arr: any[], property_name: string): string {
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
export function escape_single_quotes(str: string) {
  return str.replace(/'/g, '\\\'')
}

export async function execute(client: Gremlin.driver.Client, query: string, params?: { [key: string]: string | number | boolean }): Promise<any> {
  /* executes a gremlin query */
  // TODO: move db retries to config
  const retries = 5
  try {
    await connectGraphClient(client);
    return await GraphExecute.execute_query(client, query, retries, params);
  } catch (error) {
    console.error(`Failed to execute query: ${error}`);
    throw error;
  }
}


export async function add_stoppoint(client: Gremlin.driver.Client, stoppoint: NetworkTypes.StopPoint, upsert = true) {
  /**
   * Adds a stoppoint to the graphdb.
   * a stoppoint is an object with teh following properties:
   * id, type, name, naptanId, stationNaptan, lat, lon, modes, lines
   *
   * @param {object} stoppoint - stoppoint object
   * @returns {Promise} - pending query to graphdb
   */

  // construct a query to add the stoppoint to the graphdb
  const add_query = `addV('${stoppoint.type}')
                      .property('id', '${stoppoint.id}')
                      .property('name', '${escape_single_quotes(stoppoint.name)}')
                      .property('naptanId', '${stoppoint.naptanId}')
                      .property('lat', '${stoppoint.lat}')
                      .property('lon', '${stoppoint.lon}')
                      ${add_array_value(stoppoint.modes, 'modes')}
                      ${add_array_value(stoppoint.lines, 'lines')}`

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
    const result = execute(client, query)
    // const result = await .execute(stoppoint_client, query, 5)
    return result
  }
  catch (err) {
    logger.error(err)
    return [{ success: false }]
  }

}