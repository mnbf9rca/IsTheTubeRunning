
const line = require('../line')
jest.mock('../../services/tfl_api.query')
const validator = require('jsonschema')


const fs = require('fs')

const test_data = require('./line.test_data')

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
    const expected_response = test_data.line_stoppoints_victoria_true
    const actual_response = await line.stoppoints('victoria', true)
    test_actual_response(actual_response, expected_response)
  })
  test('calls mock TFL API to get Victoria line stoppoints, implicitly unordered', async () => {
    const expected_response = test_data.line_stoppoints_victoria_false
    const actual_response = await line.stoppoints('victoria')
    test_actual_response(actual_response, expected_response)
  })
  test('calls mock TFL API to get Victoria line stoppoints, explicitly unordered', async () => {
    const expected_response = test_data.line_stoppoints_victoria_false
    const actual_response = await line.stoppoints('victoria', false)
    test_actual_response(actual_response, expected_response)
  })
})
describe('get the valid lines for a given mode', () => {
  test('gets lines for tube', async () => {
    const expected_response = test_data.lines_for_mode_tube
    const actual_response = await line.get_lines_for_modes(['tube'])
    expect(actual_response).toMatchObject(expected_response)
  })
  test('gets lines for overground', async () => {
    const expected_response = test_data.lines_for_mode_overground
    const actual_response = await line.get_lines_for_modes(['tube'])
    expect(actual_response.data).toMatchObject(expected_response.data)
    expect(actual_response.ttl).toBeLessThanOrEqual(expected_response.ttl)
  })

  test('gets lines for tube,overground', async () => {
    const expected_response = test_data.lines_for_mode_tube_overground
    const actual_response = await line.get_lines_for_modes(['tube','overground'])
    expect(actual_response).toMatchObject(expected_response)
  })
  test('throws error if mode is not an array', async () => {
    await expect(line.get_lines_for_modes('tube')).rejects.toThrow('modes must be an array')
  })
})

describe('generate stoppoints from branch', () => {
  afterEach(() => {
    // restore the spy created with spyOn
    jest.restoreAllMocks()
  })
  test('for properly formed array of branches', () => {
    const expected_response = test_data.generate_stoppoints_from_branch_1_expected
    const input_data = test_data.branch_data_1
    const actual_response = line.generate_stoppoints_from_branch(input_data)
    expect(actual_response).toMatchObject(expected_response)
  })
  test('throws error if input doesnt match schema', () => {
    const v = require('jsonschema')
    const spy = jest.spyOn(v, 'validate')
    const input_data = 1
    expect(() => line.generate_stoppoints_from_branch(input_data)).toThrow(validator.ValidationError)
    expect(spy).toHaveBeenCalledTimes(1)
  })
  test('throws error if input is empty', () => {
    const input_data = {}
    expect(() => line.generate_stoppoints_from_branch(input_data)).toThrow(validator.ValidationError)
  })
})


describe('generate line for branch', () => {
  afterEach(() => {
    // restore the spy created with spyOn
    jest.restoreAllMocks()
  })
  test('for properly formed array of branches', () => {
    const expected_response = test_data.generate_line_for_branch_1_expected
    const input_data = test_data.branch_data_1
    const actual_response = line.generate_single_line_from_branch(input_data)
    expect(actual_response).toMatchObject(expected_response)
  })
  test('throws error if input doesnt match schema', () => {
    // using jsonvalidator to check input. We don't want to test jsonvalidator here
    // just check that it's being used
    const v = require('jsonschema')
    const spy = jest.spyOn(v, 'validate')
    const input_data = 1
    expect(() => line.generate_single_line_from_branch(input_data)).toThrow(validator.ValidationError)
    expect(spy).toHaveBeenCalledTimes(1)
  })
})