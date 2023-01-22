
const line = require('../line')
jest.mock('../../services/tfl_api.query')

const fs = require('fs')

const expected_results = require('./line.expected')

const extended_tests = require('../../test_helpers/extendExpects')

expect.extend({
  ...extended_tests
})

function test_actual_response(actual_response, expected_response) {
  expect(actual_response['data']).toMatchObject(expected_response['data'])
  expect(actual_response['ttl']).toBeLessThanOrEqual(expected_response['ttl'])
  expect(actual_response['ttl']).toBeWithinNOf(expected_response['ttl'], 1)
}

describe('line controller gets stoppoints', () => {

  test('calls mock TFL API to get ordered Victoria line stoppoints', async () => {
    const expected_response = expected_results.line_stoppoints_victoria_true
    const actual_response = await line.stoppoints('victoria', true)
    test_actual_response(actual_response, expected_response)
  })
  test('calls mock TFL API to get Victoria line stoppoints, implicitly unordered', async () => {
    const expected_response = expected_results.line_stoppoints_victoria_false
    const actual_response = await line.stoppoints('victoria')
    test_actual_response(actual_response, expected_response)
  })
  test('calls mock TFL API to get Victoria line stoppoints, explicitly unordered', async () => {
    const expected_response = expected_results.line_stoppoints_victoria_false
    const actual_response = await line.stoppoints('victoria', false)
    test_actual_response(actual_response, expected_response)
  })
})
describe('get the valid lines for a given mode', () => {
  test('gets lines for tube', async () => {
    const expected_response = expected_results.lines_for_mode_tube
    const actual_response = await line.get_lines_for_modes(['tube'])
    expect(actual_response).toMatchObject(expected_response)
  })
  test('gets lines for overground', async () => {
    const expected_response = expected_results.lines_for_mode_overground
    const actual_response = await line.get_lines_for_modes(['tube'])
    expect(actual_response.data).toMatchObject(expected_response.data)
    expect(actual_response.ttl).toBeLessThanOrEqual(expected_response.ttl)
  })

  test('gets lines for tube,overground', async () => {
    const expected_response = expected_results.lines_for_mode_tube_overground
    const actual_response = await line.get_lines_for_modes(['tube','overground'])
    expect(actual_response).toMatchObject(expected_response)
  })
  test('throws error if mode is not an array', async () => {
    await expect(line.get_lines_for_modes('tube')).rejects.toThrow('modes must be an array')
  })
})