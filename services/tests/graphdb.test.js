const { describe, expect, test } = require('@jest/globals')
const graph = require('../graphdb')
const fs = require('fs')

const randomString = () => Math.random().toString(36).slice(2, 7)

describe('GraphDB tests', () => {


  describe('test helper functions', () => {
    describe('test graph.escape_gremlin_special_characters', () => {
      test('with no single quote', () => {
        const input = 'test'
        const expected = 'test'
        const actual = graph.escape_gremlin_special_characters(input)
        expect(actual).toBe(expected)
      })
      test('with single quote', () => {
        // eslint-disable-next-line quotes
        const input = "test'test"
        // eslint-disable-next-line quotes
        const expected = "test\\'test"
        const actual = graph.escape_gremlin_special_characters(input)
        expect(actual).toBe(expected)
      })
      test('with single quote', () => {
        // eslint-disable-next-line quotes
        const input = "test''test"
        // eslint-disable-next-line quotes
        const expected = "test\\'\\'test"
        const actual = graph.escape_gremlin_special_characters(input)
        expect(actual).toBe(expected)
      })
    })
    describe('test serializeGremlinResults', () => {
      test('serializeGremlinResults returns a properly formed object for a single result', () => {
        const serializeGremlinResults = graph.__get__('serializeGremlinResults')
        const input_value = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"4d89ef30-f815-42a1-8b7b-34b825959db1","value":"yboa6"}],"naptanId":[{"id":"28fjp|naptanId","value":"28fjp"}],"lat":[{"id":"dd1b087f-5b33-4076-9ab6-9262a9f2c17c","value":"51.39571760958728"}],"lon":[{"id":"18b1c07d-76fa-48ec-997e-4eb20c7bf235","value":"-0.14384083030070627"}],"modes":[{"id":"24767fe3-b142-4f29-b059-000c0838c413","value":"31t3i"},{"id":"1bda7368-b2f7-4913-8a94-8906de99a89d","value":"dx038"}],"lines":[{"id":"dadd01de-522c-41cd-b217-7329b8cf524e","value":"dqgm6"},{"id":"d5fdc72f-41ea-4277-a367-d1fc4da22a84","value":"n3nws"},{"id":"465966e9-939f-4bda-a40e-5565e487c50d","value":"2pnpi"}]}}]')
        const expected_result = JSON.parse('[{"id": "28fjp","label": "stoppoint","type": "vertex","name": "yboa6","naptanId": "28fjp","lat": "51.39571760958728","lon": "-0.14384083030070627","modes": ["31t3i","dx038"],"lines": ["dqgm6","n3nws","2pnpi"]}]')
        const actual_result = serializeGremlinResults(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('serializeGremlinResults returns a properly formed object for a multiple result', () => {
        const serializeGremlinResults = graph.__get__('serializeGremlinResults')
        const input_value = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"4d89ef30-f815-42a1-8b7b-34b825959db1","value":"yboa6"}],"naptanId":[{"id":"28fjp|naptanId","value":"28fjp"}],"lat":[{"id":"dd1b087f-5b33-4076-9ab6-9262a9f2c17c","value":"51.39571760958728"}],"lon":[{"id":"18b1c07d-76fa-48ec-997e-4eb20c7bf235","value":"-0.14384083030070627"}],"modes":[{"id":"24767fe3-b142-4f29-b059-000c0838c413","value":"31t3i"},{"id":"1bda7368-b2f7-4913-8a94-8906de99a89d","value":"dx038"}],"lines":[{"id":"dadd01de-522c-41cd-b217-7329b8cf524e","value":"dqgm6"},{"id":"d5fdc72f-41ea-4277-a367-d1fc4da22a84","value":"n3nws"},{"id":"465966e9-939f-4bda-a40e-5565e487c50d","value":"2pnpi"}]}},{"id":"gylob","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"a1c44656-eb22-4e5d-8aae-33c5f17da296","value":"oh7m3"}],"naptanId":[{"id":"gylob|naptanId","value":"gylob"}],"lat":[{"id":"62051f9a-92ae-47ab-bbb5-06eb9244eb56","value":"51.21501641747709"}],"lon":[{"id":"827bcebb-fbd8-4190-83f4-faac94aec243","value":"-0.17557826765462625"}],"modes":[{"id":"34ffc77f-b10d-4e27-9764-8d0503e53e3d","value":"dzcpd"},{"id":"adba3358-2001-4cf0-bb64-526ed281546b","value":"you2p"}],"lines":[{"id":"6328afef-d6e4-4cd1-8c7e-ea7dfb400879","value":"15nl0"},{"id":"a4599095-c467-458c-9c9b-cb21bd63d44e","value":"9s3dt"},{"id":"ec512682-ffc1-40fd-9255-76917866362b","value":"xtcek"}]}}]')
        const expected_result = JSON.parse('[{"id": "28fjp","label": "stoppoint","type": "vertex","name": "yboa6","naptanId": "28fjp","lat": "51.39571760958728","lon": "-0.14384083030070627","modes": ["31t3i","dx038"],"lines": ["dqgm6","n3nws","2pnpi"]},{"id":"gylob","label":"stoppoint","type":"vertex","name":"oh7m3","naptanId":"gylob","lat":"51.21501641747709","lon":"-0.17557826765462625","modes":["dzcpd","you2p"],"lines":["15nl0","9s3dt","xtcek"]}]')
        const actual_result = serializeGremlinResults(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('serializeGremlinResults returns a properly formed object for empty result', () => {
        const serializeGremlinResults = graph.__get__('serializeGremlinResults')
        const input_value = []
        const expected_result = []
        const actual_result = serializeGremlinResults(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
    })
    describe('test stringToMilliseconds', () => {
      const stringToMilliseconds = graph.__get__('stringToMilliseconds')
      test('stringToMilliseconds returns ms when only ms given', () => {
        const input_value = '00:00:00.1040000'
        const expected_result = 104
        const actual_result = stringToMilliseconds(input_value)
        expect(actual_result).toEqual(expected_result)
      })
      test('stringToMilliseconds returns ms with seconds, hours, minutes', () => {
        const input_value = '01:02:03.1040000'
        const expected_result = 3723104
        const actual_result = stringToMilliseconds(input_value)
        expect(actual_result).toEqual(expected_result)
      })
      test('stringToMilliseconds returns ms when longer ms given', () => {
        const input_value = '00:00:00.1044678'
        const expected_result = 104
        const actual_result = stringToMilliseconds(input_value)
        expect(actual_result).toEqual(expected_result)
      })
    })

  })
  describe('test connecting to graphdb', () => {
    test('stoppoint_authenticator is defined', () => {
      expect(graph.__get__('stoppoint_authenticator')).toBeDefined()
    })


  })
  // TODO: create second user to access graphdb
  describe('test graphdb queries', () => {
    afterAll(async () => {
      console.info('closing stoppoint_client')
      const stoppoint_client = graph.__get__('stoppoint_client')
      await stoppoint_client.close()
    })

    describe('tests with actual DB queries', () => {
      let list_of_added_stoppoints = []
      test('can connect to stoppoint_collection', async () => {
        const stoppoint_client = graph.__get__('stoppoint_client')
        expect(stoppoint_client).toBeDefined()
        const actual_result = await stoppoint_client.submit('g.V().count()')
        expect(actual_result['length']).toBeDefined()
      })
      afterAll(async () => {
        //TODO: move this to independent code i.e. not dependent on graphdb.js
        const client = graph.__get__('stoppoint_client')
        const execute_query = graph.__get__('execute_query')
        const delete_promises = await Promise.all(list_of_added_stoppoints.map(stoppoint_id => execute_query(client, `g.V('${stoppoint_id}').drop()`, 3)))
        const delete_results = delete_promises.every(result => result['success'] === true)
        console.log(`deleted ${list_of_added_stoppoints.length} stoppoints: ${delete_results}`)
      })
      test('add a single stoppoint', async () => {
        jest.setTimeout(20000)
        const new_stoppoint = generate_random_stoppoint(2, 3)
        list_of_added_stoppoints.push(new_stoppoint['id'])
        const actual_result = await graph.add_stoppoint(new_stoppoint, true)
        if (!actual_result['success']) {
          console.error('error result:' , actual_result)
        }
        expect(actual_result['success']).toBe(true)
        expect(actual_result['data']).toHaveLength(1)
        const added_stoppoint = actual_result['data'][0]
        expect(added_stoppoint['label']).toBe(new_stoppoint['type'])
        expect(added_stoppoint['id']).toBe(new_stoppoint['id'])
        expect(added_stoppoint['name']).toBe(new_stoppoint['name'])
        expect(added_stoppoint['naptanId']).toBe(new_stoppoint['naptanId'])
        expect(added_stoppoint['lat']).toBe(new_stoppoint['lat'])
        expect(added_stoppoint['lon']).toBe(new_stoppoint['lon'])
        expect(added_stoppoint['modes']).toEqual(new_stoppoint['modes'])
        expect(added_stoppoint['lines']).toEqual(new_stoppoint['lines'])
      })

    })
    describe('tests with stubbed client', () => {
      //create a mocked client to allow us to throw an error
      const execute_query = graph.__get__('execute_query')

      let mockGremlinClient = jest.fn(() => {})
      const process_query = (query) => {
        const reject_error = (x_ms_status_code) => {
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
      mockGremlinClient['submit'] = jest.fn((query) => process_query(query))
      test('test 400 error', async () => {
        // increase jest timeout to 60 seconds
        const expected_result = { success: false, error: 'xxx', status_code: 400 }
        const actual_result = await execute_query(mockGremlinClient, '400', 2)
        expect(actual_result).toMatchObject(expected_result)
        expect(mockGremlinClient.submit).toHaveBeenCalledTimes(1)
      })
      test('test retriable 429 error', async () => {
        // increase jest timeout to 60 seconds
        const number_of_tries = 2
        const expected_result = { success: false, error: 'xxx', status_code: 429 }
        const actual_result = await execute_query(mockGremlinClient, '429', number_of_tries)
        expect(actual_result).toMatchObject(expected_result)
        expect(mockGremlinClient.submit).toHaveBeenCalledTimes(number_of_tries)
      })
    })

  })
})

const generate_random_stoppoint = (number_of_modes, number_of_lines) => {
  const new_object_id = randomString()
  const [lat, lon] = generate_random_lat_lon()
  const stoppoint = {
    type: 'stoppoint',
    id: new_object_id,
    name: randomString(),
    naptanId: new_object_id,
    lat: lat.toString(),
    lon: lon.toString(),
    modes: generate_random_array(number_of_modes),
    lines: generate_random_array(number_of_lines)
  }
  return stoppoint
}

const generate_random_array = (number_of_modes) => {
  // return an array containing number_of_modes randomString()
  const modes = new Array(number_of_modes).fill(null).map(() => randomString())
  return modes
}

const generate_random_lat_lon = () => {
  // generate a random lat and lon that are somewhere roughly inside London
  const lat = Math.random() * (51.5 - 51.0) + 51.0
  const lon = Math.random() * (-0.1 - -0.5) + -0.5
  return [lat, lon]
}