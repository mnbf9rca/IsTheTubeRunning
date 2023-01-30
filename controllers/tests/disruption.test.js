const extended_tests = require('../../test_helpers/extendExpects')

const disruption = require('../disruption')
let tfl_query = require('../../services/tfl_api.query')
jest.mock('../../services/tfl_api.query')

const fs = require('fs')

//const expected_results = require('./disruption.expected')
expect.extend({
  ...extended_tests
})

describe('disruption controller', () => {
  describe('check for disruption', () => {
    test('reports "true" for disruption with default mock', async () => {
      const expected_response = {
        is_there_disruption: true,
        ttl: 60
      }
      const actual_response = await disruption.is_there_disruption()
      expect(actual_response).toMatchObject(expected_response)
    })
    test('(subfunction) reports "false" for disruption with custom mock', async () => {
      // const check_disruption_set_for_disruption = disruption.__get__('check_disruption_set_for_disruption')
      const disruption_set = JSON.parse('{"data":[{"id":"bakerloo","name":"Bakerloo","modeName":"tube","disruptions":[{"status":"Good Service","severity":10,"validityPeriods":[],"affectedRoutes":{}}]},{"id":"central","name":"Central","modeName":"tube","disruptions":[{"status":"Good Service","severity":10,"validityPeriods":[],"affectedRoutes":{}}]},{"id":"circle","name":"Circle","modeName":"tube","disruptions":[{"status":"Good Service","severity":10,"validityPeriods":[],"affectedRoutes":{}}]},{"id":"district","name":"District","modeName":"tube","disruptions":[{"status":"Good Service","severity":10,"validityPeriods":[],"affectedRoutes":{}}]},{"id":"london-overground","name":"London Overground","modeName":"overground","disruptions":[{"status":"Good Service","severity":10,"validityPeriods":[],"affectedRoutes":{}}]},{"id":"piccadilly","name":"Piccadilly","modeName":"tube","disruptions":[{"status":"Good Service","severity":10,"validityPeriods":[],"affectedRoutes":{}}]},{"id":"victoria","name":"Victoria","modeName":"tube","disruptions":[{"status":"Good Service","severity":10,"validityPeriods":[],"affectedRoutes":{}}]},{"id":"waterloo-city","name":"Waterloo & City","modeName":"tube","disruptions":[{"status":"Go'
        + 'od Service","severity":10,"validityPeriods":[],"affectedRoutes":{}}]}],"ttl":60}')
      const expected_response = false
      const actual_response = disruption.check_disruption_set_for_disruption(disruption_set.data)
      expect(actual_response).toBe(expected_response)
    })
  })
  describe('get disruption detail', () => {
    test('returns disruption detail', async () => {
      const expected_response = {}
      const actual_response = await disruption.disruption_detail()
      expect(actual_response).toMatchObject(expected_response)
    })
  })
})