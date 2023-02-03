import GraphDB from "../graphdb"

//const Stoppoint = require('../../models/Stoppoint')
const { describe, expect, test } = require('@jest/globals')
const config = require('../../utils/config')

import Gremlin from 'gremlin'
import { driver } from 'gremlin'

const graph = require('../graphdb')
const graph_execute = require('../graphdb.execute')

const gremlin_db_string = `/dbs/${config.graph_database}/colls/${config.graph_stoppoint_colleciton}`
const stoppoint_authenticator = new Gremlin.driver.auth.PlainTextSaslAuthenticator(gremlin_db_string, config.graph_primary_key)

const graph_test_client: driver.Client = new Gremlin.driver.Client(
  config.GRAPH_DATABASE_ENDPOINT,
  {
    authenticator: stoppoint_authenticator,
    traversalsource: 'g',
    rejectUnauthorized: true,
    mimeType: 'application/vnd.gremlin-v2.0+json'
  }
)

interface Vertex {
  id: string
  label: string
  naptanId: string
  string_property: string
  number_property: number
  array_property: string[]
}

interface Edge {
  id: string
  label: string
  string_property: string
  number_property: number
  array_property: string[]
  from: string
  to: string
}


interface iKnown_Graph {
  first: Vertex
  second: Vertex
  edge: Edge
}

function generate_vertex(): Vertex {
  const id = randomString()
  const vertex: Vertex = {
    id: `TEST-${id}}`,
    label: 'known-vertex',
    naptanId: `TEST-${id}}`,
    string_property: randomString(),
    number_property: Math.random() * 1000,
    array_property: generate_random_array(5)
  }
  return vertex
}

function generate_edge(from: string, to: string): Edge {
  const id = randomString()
  const edge: Edge = {
    id: `TEST-${id}}`,
    label: 'known-edge-to',
    string_property: randomString(),
    number_property: Math.random() * 1000,
    array_property: generate_random_array(5),
    from: from,
    to: to
  }
  return edge
}

function create_known_graph(): iKnown_Graph {
  const first = generate_vertex()
  const second = generate_vertex()
  const edge = generate_edge(first.id, second.id)
  return { first, second, edge }
}

function create_gremlin_vertex(vertex: Vertex): string {
  const vertex_string = `g.addV('${vertex.label}')
  .property('id', '${vertex.id}')
  .property('string_property', '${vertex.string_property}')
  .property('naptanId', '${vertex.naptanId}')
  ${GraphDB.add_array_value(vertex.array_property, 'array_property')}
  .property('number_property', ${vertex.number_property})`
  console.info('vertex_string', vertex_string)
  return vertex_string
}

function create_gremlin_edge(edge: Edge): string {
  const edge_string = `g.V('${edge.from}')
  .addE('${edge.label}')
  .to(g.V('${edge.to}'))
  .property('id', '${edge.id}')
  .property('string_property', '${edge.string_property}')
  ${GraphDB.add_array_value(edge.array_property, 'array_property')}
  .property('number_property', ${edge.number_property})`
  console.info('edge_string', edge_string)
  return edge_string
}

const randomString = () => Math.random().toString(36).slice(2, 7)

const generate_random_array = (number_of_strings: number) => {
  // return an array containing number_of_modes randomString()
  const random_strings = new Array(number_of_strings).fill(null).map(() => randomString())
  return random_strings
}

const generate_random_lat_lon = () => {
  // generate a random lat and lon that are somewhere roughly inside London
  const lat = Math.random() * (51.5 - 51.0) + 51.0
  const lon = Math.random() * (-0.1 - -0.5) + -0.5
  return [lat, lon]
}


describe('GraphDB tests', () => {
  describe('test helper functions', () => {
    describe('test graph.escape_gremlin_special_characters', () => {
      test('with no single quote', () => {
        const input = 'test'
        const expected = 'test'
        const actual = GraphDB.escape_gremlin_special_characters(input)
        expect(actual).toBe(expected)
      })
      test('with single quote', () => {
        // eslint-disable-next-line quotes
        const input = "test'test"
        // eslint-disable-next-line quotes
        const expected = "test\\'test"
        const actual = GraphDB.escape_gremlin_special_characters(input)
        expect(actual).toBe(expected)
      })
      test('with single quote', () => {
        // eslint-disable-next-line quotes
        const input = "test''test"
        // eslint-disable-next-line quotes
        const expected = "test\\'\\'test"
        const actual = GraphDB.escape_gremlin_special_characters(input)
        expect(actual).toBe(expected)
      })
      test('with newline', () => {
        const input = `test
 newline`
        const expected = 'test\\n newline'
        const actual = GraphDB.escape_gremlin_special_characters(input)
        expect(actual).toBe(expected)
      })
    })
    describe.skip('test deserialize_stoppoint', () => {
      test('returns a properly formed object for a single result', () => {
        const input_value = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"4d89ef30-f815-42a1-8b7b-34b825959db1","value":"yboa6"}],"naptanId":[{"id":"28fjp|naptanId","value":"28fjp"}],"lat":[{"id":"dd1b087f-5b33-4076-9ab6-9262a9f2c17c","value":"51.39571760958728"}],"lon":[{"id":"18b1c07d-76fa-48ec-997e-4eb20c7bf235","value":"-0.14384083030070627"}],"modes":[{"id":"24767fe3-b142-4f29-b059-000c0838c413","value":"31t3i"},{"id":"1bda7368-b2f7-4913-8a94-8906de99a89d","value":"dx038"}],"lines":[{"id":"dadd01de-522c-41cd-b217-7329b8cf524e","value":"dqgm6"},{"id":"d5fdc72f-41ea-4277-a367-d1fc4da22a84","value":"n3nws"},{"id":"465966e9-939f-4bda-a40e-5565e487c50d","value":"2pnpi"}]}}]')
        const expected_result = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","lat":"51.39571760958728","lon":"-0.14384083030070627","name":"yboa6","modes":["31t3i","dx038"],"lines":["dqgm6","n3nws","2pnpi"],"naptanId":"28fjp"}]')
        const actual_result = graph.deserialize_stoppoint(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('returns a properly formed object for a multiple result', () => {
        const input_value = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"4d89ef30-f815-42a1-8b7b-34b825959db1","value":"yboa6"}],"naptanId":[{"id":"28fjp|naptanId","value":"28fjp"}],"lat":[{"id":"dd1b087f-5b33-4076-9ab6-9262a9f2c17c","value":"51.39571760958728"}],"lon":[{"id":"18b1c07d-76fa-48ec-997e-4eb20c7bf235","value":"-0.14384083030070627"}],"modes":[{"id":"24767fe3-b142-4f29-b059-000c0838c413","value":"31t3i"},{"id":"1bda7368-b2f7-4913-8a94-8906de99a89d","value":"dx038"}],"lines":[{"id":"dadd01de-522c-41cd-b217-7329b8cf524e","value":"dqgm6"},{"id":"d5fdc72f-41ea-4277-a367-d1fc4da22a84","value":"n3nws"},{"id":"465966e9-939f-4bda-a40e-5565e487c50d","value":"2pnpi"}]}},{"id":"gylob","label":"stoppoint","type":"vertex","properties":{"name":[{"id":"a1c44656-eb22-4e5d-8aae-33c5f17da296","value":"oh7m3"}],"naptanId":[{"id":"gylob|naptanId","value":"gylob"}],"lat":[{"id":"62051f9a-92ae-47ab-bbb5-06eb9244eb56","value":"51.21501641747709"}],"lon":[{"id":"827bcebb-fbd8-4190-83f4-faac94aec243","value":"-0.17557826765462625"}],"modes":[{"id":"34ffc77f-b10d-4e27-9764-8d0503e53e3d","value":"dzcpd"},{"id":"adba3358-2001-4cf0-bb64-526ed281546b","value":"you2p"}],"lines":[{"id":"6328afef-d6e4-4cd1-8c7e-ea7dfb400879","value":"15nl0"},{"id":"a4599095-c467-458c-9c9b-cb21bd63d44e","value":"9s3dt"},{"id":"ec512682-ffc1-40fd-9255-76917866362b","value":"xtcek"}]}}]')
        const expected_result = JSON.parse('[{"id":"28fjp","label":"stoppoint","type":"vertex","lat":"51.39571760958728","lon":"-0.14384083030070627","name":"yboa6","modes":["31t3i","dx038"],"lines":["dqgm6","n3nws","2pnpi"],"naptanId":"28fjp"},{"id":"gylob","label":"stoppoint","type":"vertex","lat":"51.21501641747709","lon":"-0.17557826765462625","name":"oh7m3","modes":["dzcpd","you2p"],"lines":["15nl0","9s3dt","xtcek"],"naptanId":"gylob"}]')
        const actual_result = graph.deserialize_stoppoint(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('returns a properly formed object for empty result', () => {
        const input_value: any[] = []
        const expected_result: any[] = []
        const actual_result = graph.deserialize_stoppoint(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
    })
    describe.skip('test flattenProperties', () => {
      test('array of property values', () => {
        const input_value = JSON.parse('{"value1": [{"id": "id1", "value": "valuea"}], "value2": [{"id": "id2", "value": "valueb"}]}')
        const expected_result = JSON.parse('{"value1": "valuea", "value2": "valueb"}')
        const actual_result = graph.flattenProperties(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('single property', () => {
        const input_value = JSON.parse('{"value1": [{"id": "id1", "value": "valuea"}]}')
        const expected_result = JSON.parse('{"value1": "valuea"}')
        const actual_result = graph.flattenProperties(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('empty object', () => {
        const input_value = {}
        const expected_result = {}
        const actual_result = graph.flattenProperties(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('property is a dict', () => {
        const input_value = JSON.parse('{"value1": "valueA"}')
        const expected_result = JSON.parse('{"value1": "valueA"}')
        const actual_result = graph.flattenProperties(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('mix of array and dict properties', () => {
        const input_value = JSON.parse('{"value1": [{"id": "id1", "value": "valuea"}], "value2": "valueb"}')
        const expected_result = JSON.parse('{"value1": "valuea", "value2": "valueb"}')
        const actual_result = graph.flattenProperties(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
      test('propery with array of dicts', () => {
        const input_value = JSON.parse('{"value1": [{"id": "id1", "value": "valuea"}, {"id": "id2", "value": "valueb"}]}')
        const expected_result = JSON.parse('{"value1": ["valuea", "valueb"]}')
        const actual_result = graph.flattenProperties(input_value)
        expect(actual_result).toMatchObject(expected_result)
      })
    })

  })

  // TODO: create second user to access graphdb
  describe('test graphdb queries', () => {
    afterAll(async () => {
      console.info('closing stoppoint_client')
      //const stoppoint_client = graph.__get__('stoppoint_client')
      await GraphDB.getInstance().close()
    })

    describe('tests with actual DB queries', () => {
      let list_of_added_vertices: string[] = []
      let known_graph = create_known_graph()

      beforeAll(async () => {
        await add_and_push_vertex(known_graph.first)
        await add_and_push_vertex(known_graph.second)
        await graph_test_client.submit(create_gremlin_edge(known_graph.edge))
      })

      async function add_and_push_vertex(vertex: Vertex) {
        list_of_added_vertices.push(vertex['id'])
        return await graph_test_client.submit(create_gremlin_vertex(vertex))
      }

      afterAll(async () => {
        const drop_query = `g.v('${list_of_added_vertices.join('\',\'')}').drop()`
        console.log('list of added stoppoints: ', list_of_added_vertices)
        console.log('calling drop query:', drop_query)
        // if delete_promise is rejected, catch the error

        const delete_promise = await graph_test_client.submit(drop_query)
          .catch((err: Error) => {
            console.error('unable to delete test data stoppoints')
            console.error(err)
            console.error(err.stack)
          })

        // TODO: report any that arent deleted
        console.log(`deleted ${list_of_added_vertices.length} stoppoints. Success?`, delete_promise !== undefined)
        await graph_test_client.close()
      })
      test('can connect to stoppoint_collection', async () => {
        // const stoppoint_client = graph.__get__('stoppoint_client')
        expect(GraphDB.getInstance()).toBeDefined()
        const actual_result = await GraphDB.getInstance().execute('g.V(\'no-object\').count()')
        expect(actual_result['data']['length']).toBeDefined()
        expect(actual_result['success']).toBe(true)
      })
      test('can tell whether client is open or closed', async () => {
        // const stoppoint_client = graph.__get__('stoppoint_client')
        expect(GraphDB.getInstance()).toBeDefined()
        const actual_result = await GraphDB.getInstance().isOpen
        expect(actual_result).toBe(true)
        await GraphDB.getInstance().close()
        const actual_result2 = await GraphDB.getInstance().isOpen
        expect(actual_result2).toBe(false)
      })

      test.skip('add a single stoppoint', async () => {
        jest.setTimeout(20000)
        const new_stoppoint = generate_random_Stoppoint(2, 3)
        // in the return value, the label is the same as the type and the type is the DB object type, vertex
        // TODO here, we need to cast to a new type, Graph_Stoppoint or something
        // as the spread syntax is exposing all of the private properties
        const expected_result = { ...(new_stoppoint.getObject()), 'lat': String(new_stoppoint.lat), 'lon': String(new_stoppoint.lon), 'label': new_stoppoint['type'], 'type': 'vertex' }
        const id = new_stoppoint['id']
        list_of_added_vertices.push(id)
        const actual_result = await graph.add_stoppoint(new_stoppoint, true)
        if (!actual_result['success']) {
          console.error('error result:', actual_result)
        }
        expect(actual_result['success']).toBe(true)
        expect(actual_result['data']).toHaveLength(1)
        expect(actual_result['data'][0]).toEqual(expected_result)

      })
      test.skip('find the route between our two known stoppoints', async () => {
        jest.setTimeout(20000)
        const expected_result = {
          data: [[{
            id: known_graph.first.id,
            label: 'stoppoint',
            type: 'vertex',
            name: known_graph.first.name,
            naptanId: known_graph.first.id,
            lat: String(known_graph.first.lat),
            lon: String(known_graph.first.lon),
            modes: known_graph.first.modes,
            lines: known_graph.first.lines
          },
          {
            id: known_graph.line.id,
            from: known_graph.line.from!.id,
            to: known_graph.line.to!.id,
            line: known_graph.line.lineName,
            branch: known_graph.line.branchId.toString(),
            direction: known_graph.line.direction,
          },
          {
            id: known_graph.second.id,
            label: 'stoppoint',
            type: 'vertex',
            name: known_graph.second.name,
            naptanId: known_graph.second.id,
            lat: String(known_graph.second.lat),
            lon: String(known_graph.second.lon),
            modes: known_graph.second.modes,
            lines: known_graph.second.lines
          }]],
          success: true,
          status_code: null
        }
        const actual_result = await graph.find_route_between_stops(known_graph.first['id'], known_graph.second['id'], known_graph.line.lineName)
        expect(actual_result).toMatchObject(expected_result)
      })

    })
    describe('tests with stubbed graph client', () => {
      //create a mocked client to allow us to throw an error

      interface MockedGremlinClient {
        submit: jest.Mock
      }

      // https://stackoverflow.com/a/64061583/104370
      let mockGremlinClient= jest.fn(() => { }) as unknown as jest.Mocked<MockedGremlinClient>

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
          const actual_result = await graph_execute.execute_query(mockGremlinClient, '400', 2)
          expect(actual_result).toMatchObject(expected_result)
          expect(mockGremlinClient.submit).toHaveBeenCalledTimes(1)
        })
        test('test retriable 429 error', async () => {
          // increase jest timeout to 60 seconds
          const number_of_tries = 2
          const expected_result = { success: false, error: 'xxx', status_code: 429 }
          const actual_result = await graph_execute.execute_query(mockGremlinClient, '429', number_of_tries)
          expect(actual_result).toMatchObject(expected_result)
          expect(mockGremlinClient.submit).toHaveBeenCalledTimes(number_of_tries)
        })
      })
    })

  })
})