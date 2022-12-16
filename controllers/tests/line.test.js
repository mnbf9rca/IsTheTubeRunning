const line = require('../line')
jest.mock('../../services/tfl_api.query')

const fs = require('fs')

const expected_results = require('./line.expected')

expect.extend({
  toBeWithinNOf(actual, expected, n) {
    const pass = Math.abs(actual - expected) <= n
    if (pass) {
      return {
        message: () => `expected ${actual} not to be within ${n} of ${expected}`,
        pass: true
      }
    } else {
      return {
        message: () => `expected ${actual} to be within ${n} of ${expected}`,
        pass: false
      }
    }
  }
})

function test_actual_response(actual_response, expected_response) {
  expect(actual_response['data']).toMatchObject(expected_response['data'])
  expect(actual_response['ttl']).toBeLessThanOrEqual(expected_response['ttl'])
  expect(actual_response['ttl']).toBeWithinNOf(expected_response['ttl'], 1)
}

describe('line controller gets stoppoints', () => {

  test('calls TFL API to get ordered Victoria line stoppoints', async () => {
    const expected_response = expected_results.line_stoppoints_victoria_true
    const actual_response = await line.stoppoints('victoria', true)
    test_actual_response(actual_response, expected_response)
  })
  test('calls TFL API to get Victoria line stoppoints, implicitly unordered', async () => {
    const expected_response = expected_results.line_stoppoints_victoria_false
    const actual_response = await line.stoppoints('victoria')
    test_actual_response(actual_response, expected_response)
  })
  test('calls TFL API to get Victoria line stoppoints, explicitly unordered', async () => {
    const expected_response = expected_results.line_stoppoints_victoria_false
    const actual_response = await line.stoppoints('victoria', false)
    test_actual_response(actual_response, expected_response)
  })
})