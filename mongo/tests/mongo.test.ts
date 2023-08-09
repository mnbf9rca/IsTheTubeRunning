import * as mongo from '../mongo';
import { MongoClient, Db, Document, Collection } from 'mongodb';
const config = require('../../utils/config')

// set up a connection to the database
// TODO: move to a helper file for tests
const mongo_endpoint = config.mongo_endpoint// "mongodb+srv://<username>:<password>@cluster0.yih6sor.mongodb.net/?retryWrites=true&w=majority"
const username = encodeURIComponent(config.mongo_username)
const password = encodeURIComponent(config.mongo_password)
const dbname = config.graph_database_name
const authMechanism = "DEFAULT"
const mongo_connection_string =
  `mongodb+srv://${username}:${password}@${mongo_endpoint}/?retryWrites=true&w=majority&authMechanism=${authMechanism}`




  interface Edge extends mongo.GenericEdge {
    label: string;
    string_property: string;
    number_property: number;
  }

interface Vertex {
  id: string
  label: string
  naptanId: string
  string_property: string
  number_property: number
  array_property: string[]
}

interface KnownGraph {
  first: Vertex
  second: Vertex
  edge: Edge
}

const randomString = () => Math.random().toString(36).slice(2, 7)

const generate_random_array = (number_of_strings: number) => {
  // return an array containing number_of_modes randomString()
  const random_strings = new Array(number_of_strings).fill(null).map(() => randomString())
  return random_strings
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

function create_known_graph(): KnownGraph {
  const first = generate_vertex()
  const second = generate_vertex()
  const edge = generate_edge(first.id, second.id)
  return { first, second, edge }
}


describe('mongo tests', () => {
  describe('test methods to return the db client', () => {
    test('Test getGraphClient returns a connection to the configured database', async () => {
      expect(mongo.getGraphClientDb()).resolves.toBeInstanceOf(Db)
      const clientdb = await mongo.getGraphClientDb()
      expect(clientdb.databaseName).toBe(config.graph_database_name)
    })
    test('Test connectGraphClient does not throw', async () => {
      const clientdb = await mongo.getGraphClientDb()
      const result = mongo.connectGraphClient(clientdb)
      expect(result).resolves.toBeUndefined()
    })
  })
  describe('test methods to add vertices (nodes)', () => {
    let list_of_added_vertices: String[] = []
    let list_of_added_edges: String[] = []

    let known_graph = create_known_graph()
    let test_client: MongoClient
    let test_vertex_collection: Collection
    let test_edge_collection: Collection
    let test_db: Db

    beforeAll(async () => {
      console.debug(`Aquiring independent DB connection to '${dbname}' for use in testing....`)
      try {
        // Connect to our MongoDB database hosted on MongoDB Atlas
        test_client = new MongoClient(mongo_connection_string, { tls: true })
        await test_client.connect()
        // Specify which database we want to use
        test_db = test_client.db(dbname)
        // Specify which collection we want to use
        test_vertex_collection = test_db.collection("vertices")
        test_edge_collection = test_db.collection("edges")
      } catch (error) {
        console.error("ERROR aquiring DB Connection!")
        throw error
      }
      console.debug("Populating a known graph in the DB for testing")

      try {
        console.log(await add_and_push_vertex(known_graph.first))
        console.log(await add_and_push_vertex(known_graph.second))
        console.log(await add_and_push_edge(known_graph.edge))

      } catch (error) {
        console.error("ERROR adding known graph to DB!")
        throw error
      }

      async function add_and_push_vertex(vertex: Vertex) {
        list_of_added_vertices.push(vertex['id'])
        return await test_vertex_collection.insertOne(vertex)
      }
      async function add_and_push_edge(edge: Edge) {
        //TODO: work out how to calculate the edge with references
        list_of_added_edges.push(edge['id'])
        return await test_edge_collection.insertOne(edge)
      }
    })
    test('can query for a single vertex', async () => {
      const vertex_collection = await mongo.getGraphClientDb().then(db => db.collection("vertices"))
      const expected_result = known_graph.first
      const query = {id: known_graph.first.id}

      const actual_result = await vertex_collection.find(query).toArray()
      expect(actual_result[0].id == expected_result.id).toBeTruthy()
    })

    test('can add an edge using add_edge', async () => {
      const expected_result = generate_edge("TEST-1", "TEST-2")
      list_of_added_edges.push(expected_result['id'])
      const query = {id: expected_result.id}
      const insert_result = await mongo.add_edge(test_db, expected_result)
      const actual_result = await test_edge_collection.find(query).toArray()
      expect(actual_result[0].id == expected_result.id).toBeTruthy()
    })

  })
})