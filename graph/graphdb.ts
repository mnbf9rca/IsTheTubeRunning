//const Stoppoint = require('../models/Stoppoint')
import config from '../utils/config'
import GraphExecute from './graphdb.execute'
import Gremlin from 'gremlin'


interface IGraphDB {
  execute: (query: string, params?: { [key: string]: string | number | boolean }) => Promise<any>
  connect: () => Promise<void>
  close: () => Promise<void>
  isOpen: Promise<boolean>
  // getInstance: () => GraphDB -> cant figure out how to get a static method defined in typescript interface
}

export default class GraphDB implements IGraphDB {
  private _gremlin_db_string = `/dbs/${config.graph_database}/colls/${config.graph_stoppoint_colleciton}`
  private _stoppoint_authenticator = new Gremlin.driver.auth.PlainTextSaslAuthenticator(this._gremlin_db_string, config.graph_primary_key)
  private static _instance: GraphDB = new GraphDB()
  private _gremlin_client = new Gremlin.driver.Client(
    config.GRAPH_DATABASE_ENDPOINT,
    {
      authenticator: this._stoppoint_authenticator,
      traversalsource: 'g',
      rejectUnauthorized: true,
      mimeType: 'application/vnd.gremlin-v2.0+json'
    }
  )
  private constructor() {
    if (GraphDB._instance) {
      throw new Error("Error: Instantiation failed: Use GraphDB.getInstance() instead of new.");
    }
    GraphDB._instance = this;
  }
  public async execute(query: string, params?: { [key: string]: string | number | boolean }): Promise<any> {
    /* executes a gremlin query */
    if (await this.isOpen === false) {
      await this.connect()
      console.log('reconnected to graphdb because a query was raised while the connection was closed')
    }
    return GraphExecute.execute_query(this._gremlin_client, query, 5, params)
  }
  public async close(): Promise<void> {
    /* closes the connection to the database */
    return this._gremlin_client.close()
  }
  public static getInstance(): GraphDB {
    /* returns the instance of the class */
    return GraphDB._instance
  }
  public get isOpen(): Promise<boolean> {
    /* returns true if the client is connected to the database */
    return this._gremlin_client.isOpen
  }
  public async connect(): Promise<void> {
    /* connects to the database */
    return this._gremlin_client.open()
  }
  public static escape_gremlin_special_characters(str: string): string {
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
    return interim
  }
  public static add_array_value = (arr: any[], property_name: string): string => {
    /**
     * Converts an array to a string containing the same property
     * with each different value ('multi-properties')
     * see https://tinkerpop.apache.org/docs/current/reference/#vertex-properties
     * @param {Array} arr - array to convert
     * @returns {String} - list of .property entries
     */
    const items = arr.map((item) => `.property('${property_name}', '${this.escape_gremlin_special_characters(item)}')`).join('\n')

    return items
  }
}
