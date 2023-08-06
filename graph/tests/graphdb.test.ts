import GraphDB from "../graphdb"

//const Stoppoint = require('../../models/Stoppoint')
const { describe, expect, test } = require('@jest/globals')
const config = require('../../utils/config')

import Gremlin from 'gremlin'
import { driver } from 'gremlin'

// set up a connection to the database
// TODO: move to a helper file for tests
const gremlin_db_string = `/dbs/${config.graph_database}/colls/${config.graph_stoppoint_colleciton}`
const stoppoint_authenticator = new Gremlin.driver.auth.PlainTextSaslAuthenticator(gremlin_db_string, config.cosmos_primary_key)

const graph_test_client: driver.Client = new Gremlin.driver.Client(
  config.COSMOS_ENDPOINT,
  {
    authenticator: stoppoint_authenticator,
    traversalsource: 'g',
    rejectUnauthorized: true,
    mimeType: 'application/vnd.gremlin-v2.0+json'
  }
)

// types for the test data
interface Vertex {
  id: string
  label: string
  naptanId: string
  string_property: string
  number_property: number
  array_property: string[]
}

interface VertexResult {
  id: string
  label: string
  type: string
  properties: {
    naptanId: VertexProperty[]
    string_property: VertexProperty[]
    number_property: VertexProperty[]
    array_property: VertexProperty[]
  }
}

interface VertexProperty {
  value: string | number | boolean
}

// note: edges don't support array-like properties
interface Edge {
  id: string
  label: string
  string_property: string
  number_property: number
  from: string
  to: string
}

interface EdgeResult {
  id: string
  label: string
  type: string
  outV: string
  inV: string
  properties: {
    string_property: string
    number_property: number
  }
}

interface iKnown_Graph {
  first: Vertex
  second: Vertex
  edge: Edge
}

function generate_vertex(): Vertex {
  const id = randomString()
  const vertex: Vertex = {
    id: `TEST-${id}`,
    label: 'known-vertex',
    naptanId: `TEST-${id}`,
    string_property: randomString(),
    number_property: Math.round(Math.random() * 10000) / 100,
    array_property: generate_random_array(5)
  }
  return vertex
}

function vertex_to_vertex_result(vertex: Vertex): VertexResult {
  const vertex_result = {
    id: vertex.id,
    label: vertex.label,
    type: 'vertex',
    properties: {
      naptanId: [{ value: vertex.naptanId }],
      string_property: [{ value: vertex.string_property }],
      number_property: [{ value: vertex.number_property }],
      array_property: vertex.array_property.map((value) => { return { value: value } })
    }
  }
  return vertex_result
}



function generate_edge(from: string, to: string): Edge {
  const id = randomString()
  const edge: Edge = {
    id: `TEST-${id}}`,
    label: 'known-edge-to',
    string_property: randomString(),
    number_property: Math.round(Math.random() * 10000) / 100,
    from: from,
    to: to
  }
  return edge
}

function edge_to_edge_result(edge: Edge): EdgeResult {
  const edge_result = {
    id: edge.id,
    label: edge.label,
    type: 'edge',
    outV: edge.from,
    inV: edge.to,
    properties: {
      string_property: edge.string_property,
      number_property: edge.number_property,
    }
  }
  return edge_result
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
  const edge_string = `g.addE('${edge.label}')
  .from(g.V('${edge.from}'))
  .to(g.V('${edge.to}'))
  .property('id', '${edge.id}')
  .property('string_property', '${edge.string_property}')
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
  describe('test static methods', () => {
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
  }),
    describe('test singleton', () => {
      test('can create instance', () => {
        const instance = GraphDB.getInstance()
        expect(instance).toBeInstanceOf(GraphDB)
      }),
        test('requesting instance twice returns same instance', () => {
          const instance1 = GraphDB.getInstance()
          const instance2 = GraphDB.getInstance()
          expect(instance1).toBe(instance2)
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
        if (await GraphDB.getInstance().isOpen === false) {
          await GraphDB.getInstance().connect()
        }

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
      test('can add a graph', async () => {
        const new_known_graph = create_known_graph()
        list_of_added_vertices.push(new_known_graph.first.id)
        list_of_added_vertices.push(new_known_graph.second.id)
        const first_query = create_gremlin_vertex(new_known_graph.first)
        const second_query = create_gremlin_vertex(new_known_graph.second)
        const edge_query = create_gremlin_edge(new_known_graph.edge)
        const first_result = await GraphDB.getInstance().execute(first_query)
        const second_result = await GraphDB.getInstance().execute(second_query)
        const edge_result = await GraphDB.getInstance().execute(edge_query)
        expect(first_result['success']).toBe(true)
        expect(second_result['success']).toBe(true)
        expect(edge_result['success']).toBe(true)
      })
      test('can query for a single vertex', async () => {
        const expected_result = vertex_to_vertex_result(known_graph.first)
        const query = `g.V('${known_graph.first.id}')`
        const actual_result = await GraphDB.getInstance().execute(query)
        expect(actual_result['success']).toBe(true)
        expect(actual_result['data']['_items'][0]).toMatchObject(expected_result)
      })
      test('can query for two vertices', async () => {
        const expected_result = [vertex_to_vertex_result(known_graph.first), vertex_to_vertex_result(known_graph.second)]
        const query = `g.V('${known_graph.first.id}', '${known_graph.second.id}')`
        const actual_result = await GraphDB.getInstance().execute(query)
        expect(actual_result['success']).toBe(true)
        expect(actual_result['data']['_items']).toMatchObject(expected_result)
      })
      test('add item with parameters', async () => {
        const new_vertex: Vertex = generate_vertex()
        list_of_added_vertices.push(new_vertex.id)
        const expected_result = [vertex_to_vertex_result(new_vertex)]
        const gremlin_vertex_query = create_gremlin_vertex(new_vertex)
        // replace the id with a parameter
        const parameterised_query = gremlin_vertex_query.replace(`'${new_vertex.id}')`, `id)`)// replace the label with a parameter
          .replace(`'${new_vertex.label}')`, `label)`)
          .replace(`'${new_vertex.naptanId}')`, `naptanId)`)// replace the naptanId with a parameter
        const params = {
          id: new_vertex.id,
          label: new_vertex.label,
          naptanId: new_vertex.naptanId
        }
        const actual_result = await GraphDB.getInstance().execute(parameterised_query, params)
        expect(actual_result['success']).toBe(true)
        expect(actual_result['data']['_items']).toMatchObject(expected_result)
      })
      test('fails to add item with missing parameters', async () => {
        const new_vertex: Vertex = generate_vertex()
        list_of_added_vertices.push(new_vertex.id)
        const gremlin_vertex_query = create_gremlin_vertex(new_vertex)
        // replace the id with a parameter
        const parameterised_query = gremlin_vertex_query.replace(`'${new_vertex.id}')`, `id)`)// replace the label with a parameter
          .replace(`'${new_vertex.label}')`, `label)`)
          .replace(`'${new_vertex.naptanId}')`, `naptanId)`)// replace the naptanId with a parameter
        const params = {
          id: new_vertex.id,
          label: new_vertex.label,
        }
        const actual_result = await GraphDB.getInstance().execute(parameterised_query, params)
        expect(actual_result['success']).toBe(false)
        expect(actual_result['error']).toEqual(expect.stringContaining('Gremlin Query Compilation Error: Unable to resolve symbol \'naptanId\' in the current context'))
      })

      test('can query for a single edge', async () => {
        const expected_result = edge_to_edge_result(known_graph.edge)
        const query = `g.E('${known_graph.edge.id}')`
        const actual_result = await GraphDB.getInstance().execute(query)
        expect(actual_result['success']).toBe(true)
        expect(actual_result['data']['_items'][0]).toMatchObject(expected_result)
      })
      test('reopens the connection if closed', async () => {
        const expected_result = edge_to_edge_result(known_graph.edge)
        const query = `g.E('${known_graph.edge.id}')`
        const actual_result = await GraphDB.getInstance().execute(query)
        expect(actual_result['success']).toBe(true)
        expect(actual_result['data']['_items'][0]).toMatchObject(expected_result)
        await GraphDB.getInstance().close()
        const is_open = await GraphDB.getInstance().isOpen
        expect(is_open).toBe(false)
        const actual_result2 = await GraphDB.getInstance().execute(query)
        expect(actual_result2['success']).toBe(true)
        expect(actual_result2['data']['_items'][0]).toMatchObject(expected_result)
        const is_open2 = await GraphDB.getInstance().isOpen
        expect(is_open2).toBe(true)
      })
    })
  })
})