
import { MongoClient, Db, ClientSession, Collection, ObjectId } from 'mongodb';
import config from '../utils/config'


import * as mongoclient from './mongo.client';
import * as NetworkTypes from '../network/NetworkTypes';

// our edges can contain any properties we want that can be expressed in JSON
type ValidJSONValue = string | number | boolean | null | ValidJSONObject | ValidJSONArray;
interface ValidJSONObject {
  [key: string]: ValidJSONValue;
}

interface ValidJSONArray extends Array<ValidJSONValue> { }

export interface GenericEdge extends ValidJSONObject {
  id: string;
  from: string;
  to: string;
}

export function getGraphClientDb(): Promise<Db> {
  return mongoclient.GetDbInstance()
}

export async function connectGraphClient(client: Db): Promise<void> {
  try {
    const returnedDoc = await client.command({ ping: 1 })
    console.log(returnedDoc)
  } catch (error) {
    throw error
  }
}

export async function add_edge_local(client_db: Db, edge: GenericEdge): Promise<ObjectId> {
  const edge_collection = client_db.collection("edges");
  const vertex_collection = client_db.collection("vertices");
  // need to find the existing vertices 
  const { from_vertex, to_vertex } = await find_from_and_to_vertex(vertex_collection, edge);
  // create a new GenericEdge which has the from and to fields as the vertex ids
  let new_edge = { ...edge, from: from_vertex._id, to: to_vertex._id };

  const result = await edge_collection.insertOne(new_edge);
  if (result.acknowledged === false) {
    throw new Error(`failed to add edge: ${new_edge}`);
  }
  return result.insertedId; // return the inserted document ID
}

export async function add_edge(client: MongoClient, clientDatabase: Db, databaseName: string, edge: GenericEdge): Promise<ObjectId> {
  const session = client.startSession();

  try {
    // Start the transaction
    session.startTransaction();

    // Step 1: Perform aggregation to find the existing vertices
    const aggregationFindExistingVertices = [
      {
        $match: { id: { $in: [edge.from, edge.to] } }
      },
      {
        $facet: {
          from: [{ $match: { id: edge.from } }],
          to: [{ $match: { id: edge.to } }]
        }
      },
      {
        $addFields: {
          fromCount: { $size: '$from' },
          toCount: { $size: '$to' }
        }
      }
    ];

    const existingVerticesAggregationResult = await clientDatabase.collection('vertices').aggregate(aggregationFindExistingVertices, { session }).toArray();

    const existingVertices = existingVerticesAggregationResult[0];

    // Check if there is exactly one 'from' and one 'to' vertex
    if (existingVertices.fromCount > 1 || existingVertices.toCount > 1) {
      throw new Error(`Vertices referenced by the edge are not unique: ${JSON.stringify(existingVertices)}`);
    }

    if (existingVertices.fromCount < 1 || existingVertices.toCount < 1) {
      throw new Error(`Vertices referenced by the edge (${edge.from}, ${edge.to}) are not found: ${JSON.stringify(existingVertices)}`);
    }

    const fromVertex = existingVertices.from[0];
    const toVertex = existingVertices.to[0];

    // Step 2: Create the new edge
    const newEdge = { ...edge, from: fromVertex._id, to: toVertex._id };
    const insertedEdge = await clientDatabase.collection('edges').insertOne(newEdge, { session });

    // Check if the insertion was successful
    if (insertedEdge.acknowledged === false) {
      throw new Error(`Failed to add edge: ${newEdge}`);
    }

    // Step 3: Update the existing vertices 'from' and 'to'
    await clientDatabase.collection('vertices').updateOne(
      { _id: fromVertex._id },
      {
        $push: { 'out': insertedEdge.insertedId }
      },
      { session }
    );

    await clientDatabase.collection('vertices').updateOne(
      { _id: toVertex._id },
      {
        $push: { 'in': insertedEdge.insertedId }
      },
      { session }
    );

    await session.commitTransaction();
    return insertedEdge.insertedId;

  } catch (error) {
    // If an error is thrown, abort the transaction
    await session.abortTransaction();
    console.error('Transaction failed:', error);
    throw error
  } finally {
    // Always end the session
    session.endSession();
  }
}



export function getMongoClient() {
  return mongoclient.getMongoClient()
}


async function find_from_and_to_vertex(vertex_collection: Collection, edge: GenericEdge) {
  const find_unique_vertex = async (vertex_id: string) => {
    const found_vertex = await vertex_collection.find({ id: vertex_id }).toArray();
    if (found_vertex.length === 0) {
      throw new Error(`vertex not found: ${vertex_id}`);
    }
    if (found_vertex.length > 1) {
      throw new Error(`multiple from vertices found: ${vertex_id}`);
    }
    return found_vertex[0];
  };

  const from_vertex = await find_unique_vertex(edge.from as string);
  const to_vertex = await find_unique_vertex(edge.to as string);

  return { from_vertex, to_vertex };
}


export async function add_stoppoint(client: Db, stoppoint: NetworkTypes.StopPoint, upsert = true) {
  const stoppoint_collection = client.collection("stoppoints")
  const query = { id: stoppoint.id }
  const update = { $set: stoppoint }
  const options = { upsert: upsert }
  const result = await stoppoint_collection.updateOne(query, update, options)
  return result
}