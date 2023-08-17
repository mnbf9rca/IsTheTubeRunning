import * as mongo from '../mongo';
import { describe, expect, test } from '@jest/globals'
import { Mock } from 'jest-mock';
import { MongoClient, Db, Document, Collection, ObjectId, InsertOneResult, OptionalId, InsertOneOptions, ClientSession, CollectionOptions } from 'mongodb';
const config = require('../../utils/config')
import { performance } from 'perf_hooks';
import * as GraphTypes from '../GraphTypes'

jest.mock('../mongo.client')

const dbname = config.graph_database_name

interface Edge extends GraphTypes.GenericEdge {
  id: string;
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


async function add_and_push_vertex(vertex: Vertex[], vertex_collection: Collection) {
  try {
    const new_ids = vertex.map(v => v['id'])
    const insert_result = await vertex_collection.insertMany(vertex)

    return { new_ids, insert_result }
  } catch (error) {
    console.error('unable to add vertex to db', error)
    throw error
  }
}
async function findVertexById(vertexId: string, collection: Collection) {
  const vertex = await collection.find({ id: vertexId }).toArray();
  if (!vertex || vertex.length !== 1) {
    throw new Error(`Could not find unique vertex with id '${vertexId}'`);
  }
  return vertex[0];
}

async function updateVertexProperty(vertexId: ObjectId, property: string, value: any, collection: Collection, session: ClientSession) {
  await collection.updateOne(
    { _id: vertexId },
    { $push: { [property]: value } },
    { session }
  );
}

async function add_and_push_edge(client: MongoClient, edge: Edge, vertex_collection: Collection, edge_collection: Collection) {
  const session = client.startSession();
  try {
    console.log("starting transaction in add_and_push_edge")
    session.startTransaction();

    const fromVertex = await findVertexById(edge.from, vertex_collection);
    const toVertex = await findVertexById(edge.to, vertex_collection);

    const newEdge = { ...edge, from: fromVertex._id, to: toVertex._id };
    const insertedEdgeResult = await edge_collection.insertOne(newEdge, { session });
    if (!insertedEdgeResult.acknowledged) {
      throw new Error('Failed to insert edge.');
    }

    const edgeObjectId = insertedEdgeResult.insertedId;
    await updateVertexProperty(fromVertex._id, 'out', edgeObjectId, vertex_collection, session);
    await updateVertexProperty(toVertex._id, 'in', edgeObjectId, vertex_collection, session);

    await session.commitTransaction();
    return edgeObjectId;

  } catch (error) {
    await session.abortTransaction();
    console.error('Transaction failed:', error);
    throw error;
  } finally {
    console.log('ending session in add_and_push_edge')
    session.endSession();
  }
}

async function printCurrentSessions(client: MongoClient) {
  try {
    // Use the admin database as the currentOp command usually requires administrative access
    const db = client.db('admin');

    // Run the currentOp command with $ownOps and sessions filters
    const result = await db.command({ currentOp: true, $ownOps: true, sessions: [] });

    // Print the result to the console
    console.log("current sessions", result);
  } catch (error) {
    console.error('An error occurred while fetching current sessions:', error);
  }
}


describe('test with mocked mongo client', () => {
  describe('test methods to return the db client and db', () => {
    beforeAll(() => {
      // check that the db name is defined
      expect(dbname).toBeDefined()
    })
    test('getMongoClient returns a MongoClient', async () => {
      await expect(mongo.getMongoClient()).resolves.toBeInstanceOf(MongoClient)
    })
    test('getGraphClient returns a connection to the configured database', async () => {

      const client = await mongo.getMongoClient()
      await expect(mongo.getMongoDbFromClient(client, dbname)).resolves.toBeInstanceOf(Db)
      const clientdb = await mongo.getMongoDbFromClient(client, dbname)
      expect(clientdb.databaseName).toBe(dbname)
    }, 60000)
    test('verifyDbConnection does not throw when ping succeeds', async () => {
      const client = await mongo.getMongoClient()

      const clientdb = await mongo.getMongoDbFromClient(client, dbname)
      await expect(mongo.verifyDbConnection(clientdb)).resolves.toBeUndefined()
    })
    test('verifyDbConnection throws when ping fails', async () => {
      // Mock the client object and make the command method reject with an error
      const mockClient: Partial<Db> = {
        command: jest.fn().mockRejectedValue(new Error('Failed to ping'))
      };

      // Call connectGraphClient and expect it to throw the mocked error
      await expect(mongo.verifyDbConnection(mockClient as Db)).rejects.toThrow('Failed to ping');

      // Optionally, verify that the command method was called with the correct arguments
      expect(mockClient.command).toHaveBeenCalledWith({ ping: 1 });
    });
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
    let mongo_client: MongoClient
    let mongo_db: Db
    let mongo_vertex_collection: Collection
    let mongo_edge_collection: Collection

    async function get_graph_client() {
      try {
        mongo_client = await mongo.getMongoClient()
        mongo_db = await mongo.getMongoDbFromClient(mongo_client, dbname)
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
      console.debug(`Aquiring DB connection to '${dbname}' for use in testing....`)
      try {
        const uri = await mongo.getUnderlyingURI()
        // independent connection for our tests
        // incase the underlying connection is closed
        console.log('test_client will connect to:', uri)
        test_client = new MongoClient(uri)
        // Specify which database we want to use
        test_db = await mongo.getMongoDbFromClient(test_client, dbname)
        // Specify which collection we want to use
        test_vertex_collection = test_db.collection("vertices")
        test_edge_collection = test_db.collection("edges")
      } catch (error) {
        console.error("ERROR aquiring DB Connection!", error)
        throw error
      }
      console.debug("Populating a known graph in the DB for testing")

      try {
        const { new_ids, insert_result } = await add_and_push_vertex(
          [known_graph.first, known_graph.second, known_graph.third, known_graph.fourth],
          test_vertex_collection)
        list_of_added_vertices = [...list_of_added_vertices, ...new_ids]
        console.log(insert_result)

        console.log(await add_and_push_edge(test_client, known_graph.edge, test_vertex_collection, test_edge_collection))
        console.log(await add_and_push_edge(test_client, known_graph.edge_two_three, test_vertex_collection, test_edge_collection))
        console.log(await add_and_push_edge(test_client, known_graph.edge_three_four, test_vertex_collection, test_edge_collection))

      } catch (error) {
        console.error(`ERROR adding known graph ${known_graph} to DB: ${error}`)
        throw error
      }
      console.log("added known graph to DB")
    }, 30000)


    /*afterAll(async () => {
      console.debug("Cleaning up after tests")
      // delete the vertices we added
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
      // close the connection to the DB
      await mongo_client.close()
    }, 30000)*/
    describe.skip('Performance profiling for add_edge', () => {
      test('Profile add_edge function', async () => {
        const iterations = 100;
        let totalExecutionTime = 0;

        for (let i = 0; i < iterations; i++) {
          const additionalKnownGraph = create_known_graph();
          const testingEdge = additionalKnownGraph.edge;
          list_of_added_edges.push(testingEdge.id);
          const { new_ids, insert_result } = await add_and_push_vertex([additionalKnownGraph.first, additionalKnownGraph.second], test_vertex_collection);
          list_of_added_vertices = [...list_of_added_vertices, ...new_ids]

          const startTime = performance.now();
          await mongo.add_edge(mongo_client, mongo_db, testingEdge);
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
      const { new_ids, insert_result: added_vertex } = await add_and_push_vertex([additional_known_graph.first, additional_known_graph.second], test_vertex_collection)
      list_of_added_vertices = [...list_of_added_vertices, ...new_ids]

      const check_vertices_added = await test_vertex_collection.find({ id: { $in: [additional_known_graph.first.id, additional_known_graph.second.id] } }).toArray()
      expect(check_vertices_added.length).toBe(2)

      // add the edge using the module's connection to the DB
      const testing_edge = additional_known_graph.edge
      // store for cleanup
      list_of_added_edges.push(testing_edge.id)


      // add the edge using the module's connection to the DB
      const insert_result = await mongo.add_edge(mongo_client, mongo_db, testing_edge)
      expect(insert_result).toBeInstanceOf(ObjectId)

      // create the expected result
      const expected_result = {
        ...additional_known_graph.edge, // existing edge
        from: added_vertex.insertedIds[0], // new from reference
        to: added_vertex.insertedIds[1], // new to reference
        _id: insert_result // new _id from the insert
      }
      // check the insert result using our connection to the DB
      const query = { id: testing_edge.id }
      const actual_result = await test_edge_collection.find(query).toArray()
      // should only be 1
      expect(actual_result.length).toBe(1)
      // should be the object we inserted
      expect(actual_result[0]).toStrictEqual(expected_result)
    }, 25000)
    test('should throw an error if the vertices cant be found', async () => {
      const additional_known_graph = create_known_graph();

      await expect(mongo.add_edge(mongo_client, mongo_db, additional_known_graph.edge)).rejects.toThrowError('must be unique and found exactly once: {\"from\":[],\"to\":[],\"fromCount\":0,\"toCount\":0}');


    });
    describe('test for getExistingVerticesForEdge', () => {

      let session: ClientSession
      beforeEach(() => {  
        session = mongo_client.startSession();
      })
      afterEach(() => {
        session.endSession();
      })



      test('should throw if neither vertex exists', async () => {
        //const session = mongo_client.startSession();
        const edge = create_known_graph().edge;
        const expected_error = `Vertices referenced by the edge (${edge.from}, ${edge.to}) must be unique and found exactly once: {\"from\":[],\"to\":[],\"fromCount\":0,\"toCount\":0}`
        await expect(mongo.getExistingVerticesForEdge(edge, mongo_db, session)).rejects.toThrowError(expected_error);
        //session.endSession();
      })
      test('should throw if only from vertex exists', async () => {
        const known_graph = create_known_graph();
        const { new_ids, insert_result } = await add_and_push_vertex([known_graph.first], test_vertex_collection);
        list_of_added_vertices = [...list_of_added_vertices, ...new_ids]
        const inserted_vertex = {
          _id: insert_result.insertedIds[0],
          ...known_graph.first
        }
        const expected_find_result = {from: [inserted_vertex], to: [], fromCount: 1, toCount: 0}
        const edge = known_graph.edge;

        const expected_error = `Vertices referenced by the edge (${edge.from}, ${edge.to}) must be unique and found exactly once: ${JSON.stringify(expected_find_result)}`
        await expect(mongo.getExistingVerticesForEdge(edge, mongo_db, session)).rejects.toThrowError(expected_error);
      })
      test('should throw if only to vertex exists', async () => {
        const known_graph = create_known_graph();
        const { new_ids, insert_result } = await add_and_push_vertex([known_graph.second], test_vertex_collection);
        list_of_added_vertices = [...list_of_added_vertices, ...new_ids]
        const inserted_vertex = {
          _id: insert_result.insertedIds[0],
          ...known_graph.second
        }
        const expected_find_result = {from: [], to: [inserted_vertex], fromCount: 0, toCount: 1}
        const edge = known_graph.edge;

        const expected_error = `Vertices referenced by the edge (${edge.from}, ${edge.to}) must be unique and found exactly once: ${JSON.stringify(expected_find_result)}`
        await expect(mongo.getExistingVerticesForEdge(edge, mongo_db, session)).rejects.toThrowError(expected_error);
      })
      test('should throw if both vertices are the same', async () => {
        const known_graph = create_known_graph();
        const { new_ids, insert_result } = await add_and_push_vertex([known_graph.first], test_vertex_collection);
        list_of_added_vertices = [...list_of_added_vertices, ...new_ids]
        const inserted_vertex = {
          _id: insert_result.insertedIds[0],
          ...known_graph.first
        }
        const edge = known_graph.edge;

        const expected_find_result = {from: [inserted_vertex], to: [inserted_vertex], fromCount: 1, toCount: 1}
        const expected_error = `Invalid vertices referenced by the edge (${edge.from}, ${edge.from}): ${JSON.stringify(expected_find_result)}`
        edge.to = edge.from
        await expect(mongo.getExistingVerticesForEdge(edge, mongo_db, session)).rejects.toThrowError(expected_error);
      })
      test('should return the vertices if both exist', async () => {
        const known_graph = create_known_graph();
        const { new_ids, insert_result } = await add_and_push_vertex([known_graph.first, known_graph.second], test_vertex_collection);
        list_of_added_vertices = [...list_of_added_vertices, ...new_ids]
        const expected_result = {
          fromVertex: {
            _id: insert_result.insertedIds[0],
            ...known_graph.first
          },
          toVertex: {
            _id: insert_result.insertedIds[1],
            ...known_graph.second
          }
        }
        const edge = known_graph.edge;
        const actual_result = await mongo.getExistingVerticesForEdge(edge, mongo_db, session)
        expect(actual_result).toStrictEqual(expected_result)
      } )
      test.skip('should throw if from vertex exists more than once', async () => {
        // can't run this test - index requires .id to be unique
        const known_graph = create_known_graph();
        const { new_ids, insert_result } = await add_and_push_vertex([known_graph.first,  known_graph.first, known_graph.second], test_vertex_collection);
        list_of_added_vertices = [...list_of_added_vertices, ...new_ids]
        const inserted_vertices = {
          from: [{
            _id: insert_result.insertedIds[0],
            ...known_graph.first
          },
          {
            _id: insert_result.insertedIds[1],
            ...known_graph.first
          }],
          to: {
            _id: insert_result.insertedIds[2],
            ...known_graph.second
          }
        }
        const edge = known_graph.edge;
        const expected_find_result = {from: inserted_vertices.from, to: [inserted_vertices.to], fromCount: 2, toCount: 1}
        const expected_error = `Vertices referenced by the edge (${edge.from}, ${edge.to}) must be unique and found exactly once: ${JSON.stringify(expected_find_result)}`
        await expect(mongo.getExistingVerticesForEdge(edge, mongo_db, session)).rejects.toThrowError(expected_error);
      })
    })
  })
})
