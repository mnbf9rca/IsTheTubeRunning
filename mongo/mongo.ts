
import { MongoClient, Db, Document, Collection, ObjectId } from 'mongodb';
import config from '../utils/config'


import * as mongoclient from './mongo.client';
import * as NetworkTypes from '../network/NetworkTypes';

// our edges can contain any properties we want that can be expressed in JSON
type ValidJSONValue = string | number | boolean | null | ValidJSONObject | ValidJSONArray;
interface ValidJSONObject {
  [key: string]: ValidJSONValue;
}

interface ValidJSONArray extends Array<ValidJSONValue> {}

export interface GenericEdge extends ValidJSONObject {
  id: string;
  from: string;
  to: string;
}

export function getGraphClientDb(): Promise<Db>{
  return mongoclient.GetInstance()
}

export async function connectGraphClient(client: Db): Promise<void> {
  try {
    const returnedDoc = await client.command({ ping: 1 })
    console.log(returnedDoc)
  } catch (error) {
    throw error
  }
}

export async function add_edge(client: Db, edge: GenericEdge): Promise<ObjectId> {
  const edge_collection = client.collection("edges");
  const vertex_collection = client.collection("vertices");
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