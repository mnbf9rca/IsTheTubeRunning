const { describe, expect, test } = require('@jest/globals')
import Stoppoint from "../../models/Stoppoint"

const graph = require('../graphdb')
jest.mock('../graphdb.execute')
const validator = require('jsonschema')


const mockdata = require('../__mocks__/graphdb.execute.responses')

describe('graphdb.execute tests with mocked graph response', () => {
  describe('test add_line', () => {
    test('adding a line', async () => {
      const input_data = mockdata.add_line.input
      const expected_result = mockdata.add_line.expected
      const actual_result = await graph.add_line(input_data, false)
      expect(actual_result).toMatchObject(expected_result)
    })
    test.skip('throws on incorrect schema', async () => {
      // not using jsonschema at the moment
      const v = require('jsonschema')
      const spy = jest.spyOn(v, 'validate')
      const input_data = mockdata.add_stoppoint_simple.input
      await expect(graph.add_line(input_data, false)).rejects.toThrow(validator.ValidatorResultError)
      expect(spy).toHaveBeenCalledTimes(1)
    })
    test.skip('throws on missing key', async () => {
      // not using jsonschema at the moment
      const v = require('jsonschema')
      const spy = jest.spyOn(v, 'validate')
      let input_data = mockdata.add_line.input
      delete input_data.lineName
      await expect(graph.add_line(input_data, false)).rejects.toThrow(validator.ValidatorResultError)
      expect(spy).toHaveBeenCalledTimes(1)
    })
    // TODO: add more tests: test invalid schema, check for upsert
  })
  describe('test add_stoppoint', () => {
    test('adding a stoppoint', async () => {
      const input_data = mockdata.add_stoppoint_simple.input
      const expected_result = {...mockdata.add_stoppoint_simple.expected, data: mockdata.add_stoppoint_simple.expected.data}
      const actual_result = await graph.add_stoppoint(input_data, false)
      expect(actual_result).toMatchObject(expected_result)
    })

  })
})
