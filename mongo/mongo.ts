
import { MongoClient, Db, Document, Collection } from 'mongodb';
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

export async function add_edge(client: Db, edge: GenericEdge): Promise<Document> {
  const edge_collection = client.collection("edges")
  const result = await edge_collection.insertOne(edge)
  return result
}


export async function add_stoppoint(client: Db, stoppoint: NetworkTypes.StopPoint, upsert = true) {
  const stoppoint_collection = client.collection("stoppoints")
  const query = { id: stoppoint.id }
  const update = { $set: stoppoint }
  const options = { upsert: upsert }
  const result = await stoppoint_collection.updateOne(query, update, options)
  return result
}