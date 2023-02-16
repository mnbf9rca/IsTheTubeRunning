import config from '../utils/config'
import axios from 'axios'
import logger from '../utils/logger'

interface ITfLResponse {
  data: any
  ttl: number
  status: number
  success: boolean
}

interface ITfLAPIQuery {
  query(querystring: string, params?: { [key: string]: number | string | boolean }): Promise<ITfLResponse>
}


export const query: (querystring: string, params?: { [key: string]: number | string | boolean }) => Promise<ITfLResponse>  = async function (querystring: string, params?: { [key: string]: number | string | boolean })  {
  /**
   * fetches data from tfl api
   *
   * @param {String} querystring - the query string to append to the base url
   * @param {Object} params - the query parameters to append to the url
   * @returns {Object} - the response from the api
   */
  if (!querystring) return Promise.reject({ error: 'no querystring', status: 500, success: false })

  const tfl_api_root = config.tfl_api_root
  const tfl_app_key = config.TFL_APP_KEY

  let tfl_api_url = new URL(querystring, tfl_api_root)
  // add params to tfl_api_url as search parameters
  if (params) tfl_api_url = add_search_params(tfl_api_url, params)

  const tfl_api_headers = {
    'Content-Type': 'application/json',
    'cache-control': 'no-cache',
    'Accept': 'application/json',
    'app_key': tfl_app_key
  }
  let tfl_api_response = null

  try {
    logger.debug(`fetching ${tfl_api_url.toString()}`)
    tfl_api_response = await axios.get(tfl_api_url.toString(), { headers: tfl_api_headers })
    const ttl = get_s_maxage(tfl_api_response.headers['cache-control'])
    const data = tfl_api_response.data
    const status = tfl_api_response.status
    const success = tfl_api_response.status === 200
    //logger.debug({ data, ttl })
    return Promise.resolve({ data, ttl, status, success })

  } catch (error) {
    let error_message = error instanceof Error ? error.message : JSON.stringify(error)
    logger.error(`Error fetching ${tfl_api_url.toString()} : ${error_message}`)
    throw Error(error_message)
    // return Promise.reject({ error: error_message, status: 500, success: false })
  }

  // extract s-maxage from cache-control header

}

export const get_s_maxage = (cache_control_header: string): number => {
  /**
   * extracts s-maxage from cache-control header
   *
   * @param {String} cache_control_header - the cache-control header
   * @returns {Number} - the s-maxage value
   *
  */
  //https://stackoverflow.com/questions/60154782/how-to-get-max-age-value-from-cache-control-header-using-request-in-nodejs
  const matches = cache_control_header.match(/s-maxage=(\d+)/)
  const maxAge = matches ? parseInt(matches[1], 10) : -1
  return maxAge
}

export const add_search_params = (url: URL, params: { [key: string]: number | string | boolean }) => {
  /**
   * adds search params to a url
   *
   * @param {URL} url - the url to add params to
   * @param {Object} params - the params to add
   * @returns {URL} - the url with params added
   *
   */
  let new_params = params
  // eslint-disable-next-line eqeqeq
  Object.keys(new_params).forEach((key) => ((new_params[key] == undefined) ? delete new_params[key] : {}))
  let new_url = url
  for (var p in new_params)
    if (Object.prototype.hasOwnProperty.call(new_params, p)) {
      new_url.searchParams.append(p, String(new_params[p]))
    }
  return new_url
}

/*
module.exports = {
  query,
  get_s_maxage,
  add_search_params
}*/