const { describe, expect, test } = require('@jest/globals')

const graph = require('../graphdb')
jest.mock('../graphdb.execute')

const mockdata = require('../__mocks__/graphdb.execute.responses')

describe('graphdb.execute tests with mocked graph response', () => {
  describe('test add_line', () => {
    test('adding a line', async () => {
      const input_data = mockdata.add_line.input
      const expected_result = mockdata.add_line.expected
      const actual_result = await graph.add_line(input_data, false)
      expect(actual_result).toMatchObject(expected_result)
    })
    // TODO: add more tests: test invalid schema, check for upsert
  })
  describe('test add_stoppoint', () => {
    test('adding a stoppoint', async () => {
      const input_data = mockdata.add_stoppoint_simple.input
      const expected_result = mockdata.add_stoppoint_simple.expected
      const actual_result = await graph.add_stoppoint(input_data, false)
      expect(actual_result).toMatchObject(expected_result)
    })
  })
})
