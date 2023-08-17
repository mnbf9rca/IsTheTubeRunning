
import { MongoClient, Db, ClientSession, Document, Collection, ObjectId, InsertOneResult, UpdateResult } from 'mongodb';
import * as config from '../utils/config'
import * as logger from '../utils/logger'


import * as graphTypesZod from './GraphTypesZodManual';

import { z } from 'zod';


import * as mongoclient from './mongo.client';
import * as NetworkTypes from '../network/NetworkTypes';

// our edges can contain any properties we want that can be expressed in JSON


type ExistingVertices = { from: Document[]; to: Document[]; fromCount: number; toCount: number; }

// zod type for a Document
const mongoDocumentSchema = z.object({
  _id: z.instanceof(ObjectId),
}).nonstrict();


const ExistingVerticesSchema = z.object({
  from: z.array(mongoDocumentSchema),
  to: z.array(mongoDocumentSchema),
  fromCount: z.number(),
  toCount: z.number(),
});

let cachedClient: MongoClient


export async function getMongoDbFromClient(client: MongoClient, dbname: string): Promise<Db> {

  logger.debug(`getMongoDbFromClient: aquiring DB connection to db ${dbname}.`)
  try {
    // Connect to our MongoDB database wherever 'client' points us

    const c = await client.connect()
    // Specify which database we want to use


    return client.db(dbname)
  } catch (error) {

    logger.error("ERROR aquiring DB Connection in mongo.ts", error)
    throw error
  }
}

export async function getMongoClient() {

  if (!cachedClient) {
    console.debug("Creating new MongoClient")
    try {
      const uri = await mongoclient.getURI()
      cachedClient = new MongoClient(uri)
    } catch (error) {
      throw error
    }
  }
  console.log("returning cachced client")
  return cachedClient
}

export async function getUnderlyingURI(): Promise<string> {
  return mongoclient.getURI()
}


export async function close() {
  try {
    logger.debug("Closing DB connection....")
    if (cachedClient) {
      logger.debug("... requesting client to close")
      await cachedClient.close()
      logger.debug("... client close resolved")
    }
    return
  } catch (error) {
    logger.error("ERROR closing DB Connection!")
    throw error
  }

}

export async function verifyDbConnection(db: Db): Promise<void> {
  try {
    const returnedDoc = await db.command({ ping: 1 })
    console.log(returnedDoc)
  } catch (error) {
    throw error
  }
}

export async function add_edge(
  client: MongoClient,
  clientDatabase: Db,
  edge: z.infer<typeof graphTypesZod.genericEdgeSchema>
): Promise<ObjectId> {

  const session = client.startSession();


  try {
    // test edge using zod schema
    graphTypesZod.genericEdgeSchema.parse(edge);
    // Start the transaction
    session.startTransaction();

    // Step 1: Perform aggregation to find the existing vertices
    const { fromVertex, toVertex } = await getExistingVerticesForEdge(edge, clientDatabase, session);
    console.log("discovered fromVertex", fromVertex, "discovered toVertex", toVertex)
    const resolvedEdge: z.infer<typeof graphTypesZod.edgeWithObjectIdsSchema> = { ...edge as any, from: fromVertex._id, to: toVertex._id }
    // Step 2: Create the new edge
    const insertedEdge: InsertOneResult<Document> = await mongoclient
      .insertNewEdge(resolvedEdge,
        clientDatabase,
        session);
    if (!insertedEdge || !insertedEdge.acknowledged) {
      throw new Error(`failed to add edge: ${edge}`);
    }

    // Step 3: Update the existing vertices 'from' and 'to'
    const fromUpdate: UpdateResult<Document> = await clientDatabase.collection('vertices').updateOne(
      { _id: fromVertex._id },
      {
        $push: { 'out': insertedEdge.insertedId }
      },
      { session }
    );
    if (!fromUpdate || !fromUpdate.acknowledged) {
      throw new Error(`failed to update fromVertex: ${fromVertex}`);
    }

    const to_update: UpdateResult<Document> = await clientDatabase.collection('vertices').updateOne(
      { _id: toVertex._id },
      {
        $push: { 'in': insertedEdge.insertedId }
      },
      { session }
    );
    if (!to_update || !to_update.acknowledged) {
      throw new Error(`failed to update toVertex: ${toVertex}`);
    }

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


function checkFromAndToVerticesAreUnique(existingVertices: z.infer<typeof ExistingVerticesSchema>, edge: z.infer<typeof graphTypesZod.genericEdgeSchema>): { fromVertex: Document; toVertex: Document; } {
  const validatedEdge = graphTypesZod.genericEdgeSchema.parse(edge);
  if (existingVertices.fromCount !== 1 || existingVertices.toCount !== 1) {
    throw new Error(`Vertices referenced by the edge (${validatedEdge.from}, ${validatedEdge.to}) must be unique and found exactly once: ${JSON.stringify(existingVertices)}`);
  }

  const fromVertex = existingVertices.from[0];
  const toVertex = existingVertices.to[0];

  if (fromVertex._id === undefined || toVertex._id === undefined || fromVertex._id.equals(toVertex._id)) {
    throw new Error(`Invalid vertices referenced by the edge (${validatedEdge.from}, ${validatedEdge.to}): ${JSON.stringify(existingVertices)}`);
  }

  return { fromVertex, toVertex };
}

export async function getExistingVerticesForEdge(edge: z.infer<typeof graphTypesZod.genericEdgeSchema>, clientDatabase: Db, session: ClientSession) {

  try {
    const validatedEdge = graphTypesZod.genericEdgeSchema.parse(edge);

    const aggregationFindExistingVertices = [
      {
        $match: { id: { $in: [validatedEdge.from, validatedEdge.to] } }
      },
      {
        $facet: {
          from: [{ $match: { id: validatedEdge.from } }],
          to: [{ $match: { id: validatedEdge.to } }]
        }
      },
      {
        $addFields: {
          fromCount: { $size: '$from' },
          toCount: { $size: '$to' }
        }
      }
    ];
    // console.debug('aggregationFindExistingVertices', JSON.stringify(aggregationFindExistingVertices))
    const collection = clientDatabase.collection('vertices')
    const existingVerticesAggregationResult = await collection.aggregate(aggregationFindExistingVertices, { session }).toArray();

    // validate the aggregation result
    const existingVertices = validateAggregationSchema(existingVerticesAggregationResult)

    // Check if there is exactly one 'from' and one 'to' vertex
    const { fromVertex, toVertex } = checkFromAndToVerticesAreUnique(existingVertices, validatedEdge);
    return { fromVertex, toVertex };
    /*
    // this should be slower...
    const from_vertex = await clientDatabase.collection('vertices').find({ id: edge.from }, { session }).toArray();
    const to_vertex = await clientDatabase.collection('vertices').find({ id: edge.to }, { session }).toArray();

    if (from_vertex.length === 0) {
      throw new Error(`vertex not found: ${edge.from}`);
    }
    if (from_vertex.length > 1) {
      throw new Error(`multiple from vertices found: ${edge.from}`);
    }
    if (to_vertex.length === 0) {
      throw new Error(`vertex not found: ${edge.to}`);
    }
    if (to_vertex.length > 1) {
      throw new Error(`multiple to vertices found: ${edge.to}`);
    }

    return { fromVertex: from_vertex[0], toVertex: to_vertex[0] };
    */
  } catch (error) {
    console.error("unable to getExistingVerticesForEdge: ", error);
    throw error
  }

  function validateAggregationSchema(existingVerticesAggregationResult: Document[]) {
    try {
      return ExistingVerticesSchema.parse(existingVerticesAggregationResult[0]);
    }
    catch (error) {
      console.error("unable to validate aggregation schema: ", error);
      throw error
    }
  }
}




export async function add_stoppoint(client: Db, stoppoint: NetworkTypes.StopPoint, upsert = true) {
  const stoppoint_collection = client.collection("stoppoints")
  const query = { id: stoppoint.id }
  const update = { $set: stoppoint }
  const options = { upsert: upsert }
  const result = await stoppoint_collection.updateOne(query, update, options)
  return result
}
