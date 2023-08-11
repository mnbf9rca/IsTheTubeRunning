
import { MongoClient, Db, MongoServerError, Document, ClientSession } from 'mongodb'
import * as config from '../utils/config'
import * as logger from '../utils/logger'
import * as graphTypes from './GraphTypes';


const mongo_endpoint = config.mongo_endpoint// "mongodb+srv://<username>:<password>@cluster0.yih6sor.mongodb.net/?retryWrites=true&w=majority"
const username = encodeURIComponent(config.mongo_username)
const password = encodeURIComponent(config.mongo_password)
const dbname = config.graph_database_name
const authMechanism = "DEFAULT"

let client: MongoClient
let cachedDb: Db | null = null
//https://www.mongodb.com/community/forums/t/mongo-isconnected-alternative-for-node-driver-v-4/117041/6


export async function getURI(): Promise<string> {
  console.debug("returning Atlas URI")
  // we use this so that we can mock the response and use mongodb-memory-server
  const uri = buildURI(username, password, mongo_endpoint, authMechanism)
  return Promise.resolve(uri)
}

export function buildURI(username: string,
  password: string,
  mongo_endpoint: string,
  authMechanism: string = "DEFAULT"): string {
  const uri = `mongodb+srv://${username}:${password}@${mongo_endpoint}/?retryWrites=true&w=majority&authMechanism=${authMechanism}`
  return uri
}



export async function insertNewEdge(edge: graphTypes.GenericEdge, fromVertex: Document, toVertex: Document, clientDatabase: Db, session: ClientSession) {
  const newEdge = { ...edge, from: fromVertex._id, to: toVertex._id };
  const insertedEdge = await clientDatabase.collection('edges').insertOne(newEdge, { session });

  // Check if the insertion was successful
  if (insertedEdge.acknowledged === false) {
    throw new Error(`Failed to add edge: ${newEdge}`);
  }
  return insertedEdge;
}