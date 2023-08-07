import { describe, expect, test } from '@jest/globals'
import fs from 'fs'
import path from 'node:path'
import helpers from '../../utils/helpers'
import {query} from '../tfl_api.query'


type t = typeof test
// https://stackoverflow.com/questions/44654210/logical-or-for-expected-results-in-jest
const expect_or = (...tests: t[]) => {
  try {
    TODO!!
    tests.shift()()
  } catch (e) {
    if (tests.length) expect_or(...tests)
    else throw e
  }
}

const load_file = (filename: string) => {
  return fs.readFileSync(path.resolve(__dirname, filename), 'utf8')
}

const get_data = (filename: string) => {
  return helpers.jsonParser(load_file(filename))
}

describe('test helper functions ', () => {
  const tfl_api_query = require('../tfl_api.query')
  describe('extract s-maxage from header', () => {
    // const tfl_api_query.get_s_maxage = tfl_api_query.__get__('get_s_maxage')

    test('s-maxage = 60', () => {
      const header = 'max-age=0, s-maxage=60'
      const expected = 60
      const actual = tfl_api_query.get_s_maxage(header)
      expect(actual).toBe(expected)
    })
    test('s-maxage = 100000', () => {
      const header = 'max-age=0, s-maxage=100000'
      const expected = 100000
      const actual = tfl_api_query.get_s_maxage(header)
      expect(actual).toBe(expected)
    })
    test('s-maxage on its own', () => {
      const header = 's-maxage=23423'
      const expected = 23423
      const actual = tfl_api_query.get_s_maxage(header)
      expect(actual).toBe(expected)
    })
    test('s-maxage in middle', () => {
      const header = 'public, max-age=43200, s-maxage=86400, must-revalidate'
      const expected = 86400
      const actual = tfl_api_query.get_s_maxage(header)
      expect(actual).toBe(expected)
    })
    test('missing s-maxage', () => {
      const header = 'max-age=0'
      const expected = -1
      const actual = tfl_api_query.get_s_maxage(header)
      expect(actual).toBe(expected)
    })
  })
  describe('test add_search_params', () => {
    //const add_search_params = tfl_api_query.__get__('add_search_params')
    test('add search params to url', () => {
      const url = new URL('https://api.tfl.gov.uk/Line/victoria/StopPoints')
      const params = {
        'app_id': '123',
        'app_key': 'abc'
      }
      let expected = new URL('https://api.tfl.gov.uk/Line/victoria/StopPoints')
      expected.searchParams.append('app_id', '123')
      expected.searchParams.append('app_key', 'abc')
      const actual = tfl_api_query.add_search_params(url, params)
      expect(actual).toStrictEqual(expected)
    })
    test('add search params to url with existing params', () => {
      const url = new URL('https://api.tfl.gov.uk/Line/victoria/StopPoints?app_id=123')
      const params = {
        'app_key': 'abc'
      }
      let expected = new URL('https://api.tfl.gov.uk/Line/victoria/StopPoints')
      expected.searchParams.append('app_id', '123')
      expected.searchParams.append('app_key', 'abc')
      const actual = tfl_api_query.add_search_params(url, params)
      expect(actual).toStrictEqual(expected)
    })
    test('add search params to url with null params', () => {
      const url = new URL('https://api.tfl.gov.uk/Line/victoria/StopPoints')
      const params = {
        'app_id': null
      }
      const expected = new URL('https://api.tfl.gov.uk/Line/victoria/StopPoints')
      const actual = tfl_api_query.add_search_params(url, params)
      expect(actual).toStrictEqual(expected)
    })
    test('add search params to url with empty params', () => {
      const url = new URL('https://api.tfl.gov.uk/Line/victoria/StopPoints')
      const params = {}
      const expected = new URL('https://api.tfl.gov.uk/Line/victoria/StopPoints')
      const actual = tfl_api_query.add_search_params(url, params)
      expect(actual).toStrictEqual(expected)
    })
  })
})

describe('test with a real query to TfL', () => {
  test('test with a valid query actually hits the TfL API', async () => {
    const expected_result = get_data('get_line_meta_modes.json')
    const actual_result = await query('/Line/Meta/Modes')
    // check if actual_result toMatchObject either expected_day or expected_night
    expect(actual_result).toMatchObject(expected_result)
  })
  test('throw error on invalid query', async () => {
    await expect(query('/invalidurl')).rejects.toThrowError('Request failed with status code 404')
  })
})
