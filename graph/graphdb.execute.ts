
const logger = require('../utils/logger')
import { driver } from 'gremlin'

interface IGraphExecute {
  stringToMilliseconds?: (timeString: string) => number
  execute_query?: (client: driver.Client, query: string, maxAttempts: number, params: { [key: string]: string | number | boolean } | null) => Promise<any>
}

const delay = (fn: Function, ms: number) => new Promise((resolve) => setTimeout(() => resolve(fn()), ms))

const randInt = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1) + min)
export default class GraphExecute implements IGraphExecute {
  constructor() { }
  static stringToMilliseconds(timeString: string) {
    /** 
     * Convert a string in the format HH:MM:SS.mmm to milliseconds
     * @param {String} timeString - string in the format HH:MM:SS.mmm
     * @returns {Number} - time in milliseconds
     */
    const [hours, minutes, seconds] = timeString.split(':');
    const milliseconds = Math.round(parseFloat(`0.${seconds.split('.')[1]}`) * 1000)
    return (parseInt(hours) * 3600 + parseInt(minutes) * 60 + parseInt(seconds, 10)) * 1000 + milliseconds;
  }


  static execute_query = async (client: driver.Client, query: string, maxAttempts: number, params: { [key: string]: string | number | boolean } | null = null) => {
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
    const execute = async (attempt: number) => {
      if (attempt > 1) { logger.debug(`attempt ${attempt} of ${maxAttempts}`) }
      try {
        if (params) {
          logger.debug(`executing query with params: ${JSON.stringify(params)}`)
        }
        // not sure why these arent included in the Gremlin types
        interface IClientResult extends driver.ResultSet {
          attributes?: { [key: string]: string | number | boolean }
        }
        const client_result: IClientResult  = await client.submit(query, params)
        // if we got the result, then we can return it
        const ms_status_code = Object.prototype.hasOwnProperty('attributes') ? client_result.attributes!['x-ms-status-code'] : null

        // this is distinct to an ADD query, so move to that
        // const seralised_result = serializeGremlinResults(client_result['_items'])
        return { data: client_result, success: true, status_code: ms_status_code }
      } catch (err: any) {
        const ms_status_code: number | null = err['statusAttributes'] ? err['statusAttributes']['x-ms-status-code'] : null
        const ms_retry_after: string | null = err['statusAttributes'] ? err['statusAttributes']['x-ms-retry-after-ms'] : null
        // we need to retry after ms_retry_after ms
        if (ms_retry_after) { retry_time = this.stringToMilliseconds(ms_retry_after) }
        if (ms_status_code && [429, 408, 449].includes(ms_status_code) && attempt <= maxAttempts - 1) {
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
}
