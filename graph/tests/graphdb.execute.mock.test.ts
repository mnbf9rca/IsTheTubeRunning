
const { describe, expect, test } = require('@jest/globals')
import { driver } from "gremlin"
import GraphExecute from "../graphdb.execute"


describe('GraphDB.execute tests', () => {
  describe('tests with stubbed graph client', () => {
    //create a mocked client to allow us to throw an error

    // https://stackoverflow.com/a/64061583/104370
    let mockGremlinClient = jest.fn(() => { }) as unknown as driver.Client

    const process_query_and_mock_response = (query: any) => {
      const reject_error = (x_ms_status_code: number) => {
        return Promise.reject({
          name: 'ResponseError',
          statusCode: 500,
          statusMessage: 'xxx',
          statusAttributes: {
            'x-ms-retry-after-ms': '00:00:00.1040000',
            'x-ms-substatus-code': 3200,
            'x-ms-status-code': x_ms_status_code,
            'x-ms-activity-id': '969924e0-fdaf-40a6-ad9d-f0f75115dba8',
            'x-ms-request-charge': 2.79,
            'x-ms-total-request-charge': 2.79,
            'x-ms-server-time-ms': 103.5877,
            'x-ms-total-server-time-ms': 103.5877
          }
        })
      }
      const q = parseInt(query)
      if (!isNaN(q)) {
        return reject_error(q)
      } else {
        //TODO return the original query reformatted as a gremlin query
        return Promise.resolve('success')
      }
    }
    mockGremlinClient['submit'] = jest.fn((query) => process_query_and_mock_response(query))
    describe('test retry logic', () => {
      test('test 400 error', async () => {
        // increase jest timeout to 60 seconds
        const expected_result = { success: false, error: 'xxx', status_code: 400 }
        const actual_result = await GraphExecute.execute_query(mockGremlinClient, '400', 2)
        expect(mockGremlinClient.submit).toHaveBeenCalledTimes(1)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('test retriable 429 error', async () => {
        // increase jest timeout to 60 seconds
        const number_of_tries = 4
        const expected_result = { success: false, error: 'xxx', status_code: 429 }
        const actual_result = await GraphExecute.execute_query(mockGremlinClient, '429', number_of_tries)
        expect(mockGremlinClient.submit).toHaveBeenCalledTimes(number_of_tries)
        expect(actual_result).toMatchObject(expected_result)
      })
    })
  })

})
