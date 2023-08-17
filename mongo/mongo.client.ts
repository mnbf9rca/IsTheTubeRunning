
import { MongoClient, Db, Document, ClientSession, InsertOneResult, ObjectId } from 'mongodb'
import * as config from '../utils/config'
import * as logger from '../utils/logger'
import * as graphTypesZod from './GraphTypesZodManual';
import { z } from "zod";



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

/**
 * Inserts a new edge into the database.
 * @param edge The edge object to insert.
 * @param clientDatabase The MongoDB database instance.
 * @param session The MongoDB client session.
 * @returns The result of the insert operation.
 * @throws {Error} If the insertion is not acknowledged, ._id property is found, or other errors occur.
 */
export async function insertNewEdge(
  edge: z.infer<typeof graphTypesZod.edgeWithObjectIdsSchema>,
  clientDatabase: Db,
  session?: ClientSession
): Promise<InsertOneResult<Document>> {
  try {
    // Check if the edge object contains an ._id property
    if (edge.hasOwnProperty('_id')) {
      throw new Error("The edge object should not contain an ._id property");
    }

    // validate the .from and .to are ObectIds 
    // if they are not, then we will throw an error
    if (!(edge.from instanceof ObjectId) || !(edge.to instanceof ObjectId)) {
      throw new Error("The edge object should contain a .from and .to property that are ObjectIds");
    }
    
    // remove the from and to and validate the rest as valid JSON
    const {from, to, ...edgeWithoutFromTo } = edge as any;
    // Parse. Will throw an error if the edge object is invalid or can't be serialised
    const parsedEdge: any = graphTypesZod.jsonSerializable.parse(edgeWithoutFromTo)
    const finalEdge = { ...parsedEdge, from, to }

    // by now we know:
    // - from and to are ObjectIds
    // - the rest of the edge object is valid JSON
    // so we can use the object directly

    const insertedEdge = await clientDatabase
      .collection('edges')
      .insertOne(
        finalEdge,
        { session });

    if (insertedEdge.acknowledged === false) {
      throw new Error(`insertNewEdge couldn't add edge: ${JSON.stringify(finalEdge)}`);
    }

    return insertedEdge;
  } catch (error) {
    console.error("failed to insert new edge", error);
    throw error;
  }
}