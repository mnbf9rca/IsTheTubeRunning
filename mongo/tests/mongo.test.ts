import * as mongo from '../mongo';
import { MongoClient, Db, Document, Collection, ObjectId } from 'mongodb';
const config = require('../../utils/config')
import { performance } from 'perf_hooks';

jest.mock('../mongo.client')

// set up a connection to the database
// TODO: move to a helper file for tests
//const mongo_endpoint = config.mongo_endpoint// "mongodb+srv://<username>:<password>@cluster0.yih6sor.mongodb.net/?retryWrites=true&w=majority"
//const username = encodeURIComponent(config.mongo_username)
//const password = encodeURIComponent(config.mongo_password)
const dbname = config.graph_database_name
//const authMechanism = "DEFAULT"
//const mongo_connection_string =
//  `mongodb+srv://${username}:${password}@${mongo_endpoint}/?retryWrites=true&w=majority&authMechanism=${authMechanism}`




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
  edge: Edge
  second: Vertex
  edge_two_three?: Edge
  third?: Vertex
  edge_three_four?: Edge
  fourth?: Vertex
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
    id: `TEST-${id}`,
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


describe('mongo client wrapper', () => {
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
  
  describe('test direct graph methods', () => {
    let list_of_added_vertices: String[] = []
    let list_of_added_edges: String[] = []

    const first_graph = create_known_graph()
    const second_graph = create_known_graph()
    let known_graph = {
      ...first_graph, // first, edge, second
      edge_two_three: generate_edge(first_graph.second.id, second_graph.first.id),
      third: second_graph.first, // third is vertex first in graph 2
      edge_three_four: second_graph.edge, // edge from third to fourth is edge from second to third in graph 2
      fourth: second_graph.second // fourth is vertex second in graph 2
    }
    // independent database connections for our tests
    let test_client: MongoClient
    let test_vertex_collection: Collection
    let test_edge_collection: Collection
    let test_db: Db

    // database connection via the graph client
    let mongo_db: Db
    let mongo_vertex_collection: Collection
    let mongo_edge_collection: Collection

    async function get_graph_client() {
      try {
        mongo_db = await mongo.getGraphClientDb()
        mongo_vertex_collection = mongo_db.collection("vertices")
        mongo_edge_collection = mongo_db.collection("edges")
      } catch (error) {
        throw error
      }
    }
    beforeEach(async () => {
      await get_graph_client()
    })

    beforeAll(async () => {
      console.debug(`Aquiring independent DB connection to '${dbname}' for use in testing....`)
      try {
        // Connect to our MongoDB database hosted on MongoDB Atlas
        test_client = mongo.getMongoClient() //dont use this - we're mocking Mongo nownew MongoClient(mongo_connection_string, { tls: true })
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
        console.log(await add_and_push_vertex([known_graph.first, known_graph.second, known_graph.third, known_graph.fourth]))

        console.log(await add_and_push_edge(known_graph.edge))
        console.log(await add_and_push_edge(known_graph.edge_two_three))
        console.log(await add_and_push_edge(known_graph.edge_three_four))

      } catch (error) {
        console.error(`ERROR adding known graph ${known_graph} to DB: ${error}`)
        throw error
      }

    }, 30000)
    async function add_and_push_vertex(vertex: Vertex[]) {
      vertex.map(v => list_of_added_vertices.push(v['id']))
      return await test_vertex_collection.insertMany(vertex)
      //return await test_vertex_collection.insertOne(vertex)
    }
    async function add_and_push_edge(edge: Edge) {
      const from_edge = await test_vertex_collection.find({ id: edge.from }).toArray()
      const to_edge = await test_vertex_collection.find({ id: edge.to }).toArray()
      if (!from_edge || from_edge.length !== 1) {
        throw new Error(`Could not find unique vertex with id '${edge.from}' generating test edge`)
      }
      if (!to_edge || to_edge.length !== 1) {
        throw new Error(`Could not find unique vertex with id '${edge.to}' generating test edge`)
      }
      const new_edge = { ...edge, from: from_edge, to: to_edge }
      list_of_added_edges.push(edge['id'])
      return await test_edge_collection.insertOne(new_edge)
    }
    afterAll(async () => {
      console.debug("Cleaning up after tests")
      // delete the vertices we added
      /*
      const vertex_delete_result = await test_vertex_collection.deleteMany({ id: { $in: list_of_added_vertices } })
      if (vertex_delete_result.deletedCount !== list_of_added_vertices.length) {
        console.error(`Failed to delete all vertices added to the test DB!`)
        // TODO: show the IDs of the items that failed to delete
      }
      const edge_delete_result = await test_edge_collection.deleteMany({ id: { $in: list_of_added_edges } })
      if (edge_delete_result.deletedCount !== list_of_added_edges.length) {
        console.error(`Failed to delete all edges added to the test DB!`)
        // TODO: show the IDs of the items that failed to delete
      }
      */
      // close the connection to the DB
      await test_client.close()
    }, 30000)
    describe.skip('Performance profiling for add_edge', () => {
      test('Profile add_edge function', async () => {
        const iterations = 100;
        let totalExecutionTime = 0;
    
        for (let i = 0; i < iterations; i++) {
          const additionalKnownGraph = create_known_graph();
          const testingEdge = additionalKnownGraph.edge;
          list_of_added_edges.push(testingEdge.id);
          await add_and_push_vertex([additionalKnownGraph.first, additionalKnownGraph.second]);
    
          const startTime = performance.now();
          const mongoClient = mongo.getMongoClient();
          await mongo.add_edge(mongoClient, mongo_db, test_db.databaseName, testingEdge);
          const endTime = performance.now();
    
          const executionTime = endTime - startTime;
          totalExecutionTime += executionTime;
        }
    
        const averageExecutionTime = totalExecutionTime / iterations;
        console.log(`Average execution time for add_edge over ${iterations} iterations: ${averageExecutionTime.toFixed(2)} ms`);
      }, 30000 * 100); // Extended timeout for 100 iterations
    });
    test('can query for a single vertex', async () => {
      const expected_result = known_graph.first
      const query = { id: known_graph.first.id }

      const actual_result = await mongo_vertex_collection.find(query).toArray()
      expect(actual_result[0].id == expected_result.id).toBeTruthy()
    }, 30000)

    test('can add an edge using add_edge', async () => {
      // add two vertices to the DB
      const additional_known_graph = create_known_graph()
      const added_vertex = await add_and_push_vertex([additional_known_graph.first, additional_known_graph.second])
      const check_vertices_added = await test_vertex_collection.find({ id: { $in: [additional_known_graph.first.id, additional_known_graph.second.id] } }).toArray()
      expect(check_vertices_added.length).toBe(2)

      // add the edge using the module's connection to the DB
      const testing_edge = additional_known_graph.edge
      // store for cleanup
      list_of_added_edges.push(testing_edge.id)

      const query = { id: testing_edge.id }
      // add the edge using the module's connection to the DB
      const mongo_client = mongo.getMongoClient()
      const insert_result = await mongo.add_edge(mongo_client, mongo_db, test_db.databaseName, testing_edge)
      expect(insert_result).toBeInstanceOf(ObjectId)

      // create the expected result
      const expected_result = {
        ...additional_known_graph.edge, // existing edge
        from: added_vertex.insertedIds[0], // new from reference
        to: added_vertex.insertedIds[1], // new to reference
        _id: insert_result // new _id from the insert
      }
      // check the insert result using our connection to the DB
      const actual_result = await test_edge_collection.find(query).toArray()
      // should only be 1
      expect(actual_result.length).toBe(1)
      // should be the object we inserted
      expect(actual_result[0]).toStrictEqual(expected_result)
    }, 25000)

  })
})